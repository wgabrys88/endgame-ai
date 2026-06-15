"""Reactor — keeps 5 slots alive. MAP-Elites breeder for persona selection."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import config
import comms
import log

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 5
slots: dict[int, dict[str, Any]] = {}
_model_profile: str = ""
_session_dir: str = ""
_last_evolve_id: int = 0


# --- MAP-Elites (Mouret 2015): archive[niche] = best solution per niche ---

@dataclass
class Breeder:
    """Minimal MAP-Elites: archive[niche] = {target, fitness, slot, ts}."""
    archive: dict[str, dict[str, Any]] = field(default_factory=dict)

    def replace_if_better(self, niche: str, target: str, fitness: float, slot: int) -> bool:
        prev = self.archive.get(niche)
        if prev and fitness <= float(prev.get("fitness", 0)):
            return False
        self.archive[niche] = {"target": target, "fitness": fitness, "slot": slot, "ts": time.time()}
        while len(self.archive) > config.BREED_ELITE_MAX_NICHES:
            worst = min(self.archive, key=lambda n: self.archive[n]["fitness"])
            self.archive.pop(worst)
        return True

    def best_for_slot(self, slot_id: int) -> tuple[str, float]:
        best_t, best_f = "", 0.0
        for elite in self.archive.values():
            f = float(elite.get("fitness", 0))
            if f > best_f and elite.get("target") in config.WORKER_PERSONAS:
                if int(elite.get("slot", 0)) == slot_id or best_f == 0.0:
                    best_t, best_f = elite["target"], f
        return best_t, best_f

    def save(self) -> None:
        path = config.BREED_ARCHIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"v": 1, "archive": self.archive}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)

    def load(self) -> None:
        path = config.BREED_ARCHIVE_PATH
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("archive", {}) if isinstance(data, dict) else {}
            for niche, elite in raw.items():
                if isinstance(elite, dict) and elite.get("target") in config.WORKER_PERSONAS:
                    self.archive[niche] = elite
        except (OSError, json.JSONDecodeError):
            pass


_breeder = Breeder()


# --- Slot management ---

def spawn(slot_id: int, persona: str, goal: str = "", priority: int = config.PRI_MAINTENANCE) -> int:
    ef = os.path.join(BASE, f"events-child-s{slot_id}.jsonl")
    for path in (ef, os.path.join(_session_dir, f"events-child-s{slot_id}.jsonl") if _session_dir else ""):
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
    loaded = config.Personality.load(persona, slot_id, goal)
    goal = loaded.mission
    env = os.environ.copy()
    env["ENDGAME_PERSONALITY"] = persona
    env["ENDGAME_SLOT"] = str(slot_id)
    env["ENDGAME_SESSION_DIR"] = _session_dir
    cmd = [sys.executable, "main.py", goal, "--backend", env.get("ENDGAME_BACKEND", "lmstudio"),
           "--event-budget", "999999", "--events-path", ef, "--priority", str(priority)]
    if _model_profile:
        cmd += ["--model-profile", _model_profile]
    proc = subprocess.Popen(cmd, cwd=BASE, env=env, creationflags=0x08000000)
    slots[slot_id] = {"pid": proc.pid, "persona": persona, "goal": goal[:80], "priority": priority}
    return proc.pid


def kill_slot(slot_id: int) -> None:
    info = slots.pop(slot_id, None)
    if info:
        os.system(f"taskkill /F /T /PID {info['pid']} >nul 2>&1")


_STILL_ACTIVE = 259
_PROCESS_QUERY = 0x1000


def is_alive(slot_id: int) -> bool:
    info = slots.get(slot_id)
    if not info:
        return False
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_QUERY, False, info["pid"])
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == _STILL_ACTIVE
    except (OSError, AttributeError):
        return False


def reassign(slot_id: int, persona: str, goal: str = "", priority: int = config.PRI_NORMAL) -> int:
    kill_slot(slot_id)
    time.sleep(0.5)
    return spawn(slot_id, persona, goal, priority)


def status() -> dict[int, dict[str, Any]]:
    return {sid: {**info, "alive": is_alive(sid)} for sid, info in slots.items()}


# --- Breeder: process evolve candidates from bus (MAP-Elites selection) ---

def _niche_key(payload: dict[str, Any], action: str) -> str:
    niche = str(payload.get("niche", "")).strip()[:80]
    if niche:
        return niche
    behavior = str(payload.get("behavior", "")).strip() or action
    band = str(payload.get("pressure_band", "")).strip() or "unknown"
    return f"{behavior[:40]}:{band[:30]}"


def process_evolve_candidates() -> None:
    global _last_evolve_id
    for entry in comms.evolve_candidates(after_id=_last_evolve_id, limit=50):
        eid = int(entry.get("id", 0) or 0)
        _last_evolve_id = max(_last_evolve_id, eid)
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        target = comms.canonical(str(payload.get("target") or entry.get("to") or entry.get("from", "")))
        if target not in config.WORKER_PERSONAS:
            continue
        action = str(payload.get("action", "")).lower()
        fitness = max(0.0, min(1.0, float(payload.get("fitness", 0) or 0)))
        slot = int(payload.get("slot", 0) or 0)
        if action in ("retain", "patch_plugin"):
            niche = _niche_key(payload, action)
            if _breeder.replace_if_better(niche, target, fitness, slot):
                _breeder.save()
                log.emit("breed.elite", {"target": target, "niche": niche, "fitness": round(fitness, 4)})


def select_respawn_persona(slot_id: int, fallback: str) -> str:
    target, fitness = _breeder.best_for_slot(slot_id)
    if target and fitness >= config.BREED_RETAIN_MIN:
        return target
    fb = comms.canonical(fallback)
    if fb in config.WORKER_PERSONAS:
        return fb
    return config.SLOT_DEFAULTS.get(slot_id, config.WORKER_PERSONAS[0])


# --- Main ---

if __name__ == "__main__":
    _colony_goal = os.environ.get("ENDGAME_COLONY_GOAL", "").strip()
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--model-profile" and i + 1 < len(argv):
            _model_profile = argv[i + 1]; i += 2; continue
        elif arg.startswith("--model-profile="):
            _model_profile = arg.split("=", 1)[1]
        elif arg == "--goal" and i + 1 < len(argv):
            _colony_goal = argv[i + 1].strip(); i += 2; continue
        elif arg.startswith("--goal="):
            _colony_goal = arg.split("=", 1)[1].strip()
        i += 1
    if _model_profile:
        config.apply_model_profile(_model_profile)

    if not os.environ.get("ENDGAME_BOOTSTRAPPED"):
        log.cleanup_runtime()

    _session_dir = str(log.session_dir())
    log.init("events-reactor.jsonl", config.EVENT_BUDGET)
    if _colony_goal:
        comms.set_colony_goal(_colony_goal, source="reactor")
    _breeder.load()
    log.emit("reactor.start", {"slots": config.SLOTS, "profile": _model_profile or "auto"})
    print(f"REACTOR | {config.SLOTS} slots | profile={_model_profile or 'auto'}")
    if _colony_goal:
        print(f"  goal: {_colony_goal[:100]}")
    print(f"  session: {_session_dir}")

    pid = spawn(1, "comms_operator", priority=config.PRI_NORMAL)
    print(f"  s1: comms_operator PID={pid}")

    defaults = ["architect", "implementor", "reviewer", "devops"]
    for i, persona in enumerate(defaults, 2):
        pid = spawn(i, persona, priority=config.PRI_MAINTENANCE)
        print(f"  s{i}: {persona} PID={pid}")
        time.sleep(1.0)

    print(f"\nREACTOR ONLINE. {len(slots)} slots loaded.\n")

    while True:
        time.sleep(CONTROL_INTERVAL)
        process_evolve_candidates()
        for cmd in comms.drain_control():
            action = str(cmd.get("action", ""))
            if action == "reassign":
                sid = int(cmd.get("slot", 0) or 0)
                persona = str(cmd.get("persona", ""))
                if sid >= 2 and sid <= config.SLOTS and persona in config.WORKER_PERSONAS:
                    print(f"  MOE REASSIGN s{sid} -> {persona}")
                    reassign(sid, persona, priority=int(cmd.get("priority", config.PRI_NORMAL)))
        for sid in list(slots):
            if not is_alive(sid):
                info = slots.pop(sid)
                persona = select_respawn_persona(sid, str(info.get("persona", "")))
                print(f"  RESPAWN s{sid} ({persona})")
                spawn(sid, persona, info.get("goal", ""), info.get("priority", 0))
