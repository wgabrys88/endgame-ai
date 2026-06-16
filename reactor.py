"""Reactor â€” keeps 5 slots alive. MAP-Elites breeder for persona selection."""
from __future__ import annotations
import argparse
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
import ablation

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 5
ABLATION_SUMMARY_INTERVAL = 30
slots: dict[int, dict[str, Any]] = {}
_model_profile: str = ""
_session_dir: str = ""
_run_mode: str = config.DEFAULT_RUN_MODE
_ablation_run_dir: str = ""
_last_evolve_id: int = 0
_last_ablation_summary: float = 0.0


# --- MAP-Elites (Mouret 2015): archive[niche] = best solution per niche ---

@dataclass
class Breeder:
    """Minimal MAP-Elites: archive[niche] = {target, fitness, slot, ts}."""
    archive: dict[str, dict[str, Any]] = field(default_factory=dict)

    def replace_if_better(self, niche: str, target: str, fitness: float, slot: int) -> bool:
        prev = self.archive.get(niche)
        if prev and fitness <= float(prev.get("fitness", 0)):
            return False
        prompt_dna = ""
        try:
            pfile = config.PROMPTS_DIR / "personalities" / f"{target}.txt"
            if pfile.exists():
                prompt_dna = pfile.read_text(encoding="utf-8").strip()[:2000]
        except OSError:
            pass
        self.archive[niche] = {"target": target, "fitness": fitness, "slot": slot,
                               "ts": time.time(), "prompt_dna": prompt_dna}
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
    env["ENDGAME_RUN_MODE"] = _run_mode
    if _ablation_run_dir:
        env["ENDGAME_ABLATION_DIR"] = _ablation_run_dir
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
        _restore_elite_dna(slot_id, target)
        return target
    fb = comms.canonical(fallback)
    if fb in config.WORKER_PERSONAS:
        return fb
    return config.SLOT_DEFAULTS.get(slot_id, config.WORKER_PERSONAS[0])


def _restore_elite_dna(slot_id: int, target: str) -> None:
    for elite in _breeder.archive.values():
        if elite.get("target") == target and int(elite.get("slot", 0)) == slot_id:
            dna = str(elite.get("prompt_dna", "")).strip()
            if not dna:
                return
            pfile = config.PROMPTS_DIR / "personalities" / f"{target}.txt"
            try:
                current = pfile.read_text(encoding="utf-8").strip() if pfile.exists() else ""
                if current != dna:
                    pfile.write_text(dna, encoding="utf-8")
                    log.emit("breed.restore_dna", {"target": target, "slot": slot_id, "chars": len(dna)})
            except OSError:
                pass
            return



# --- Main ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="endgame-ai reactor supervisor")
    parser.add_argument("--mode", choices=config.RUN_MODES, default=config.DEFAULT_RUN_MODE)
    parser.add_argument("--model-profile", type=str, default=None)
    parser.add_argument("--goal", type=str, default=os.environ.get("ENDGAME_COLONY_GOAL", "").strip())
    parser.add_argument("--unicore-persona", type=str, default=config.UNICORE_DEFAULT_PERSONA)
    parser.add_argument("--ablation-task-id", type=str, default="")
    args = parser.parse_args()

    _run_mode = config.normalize_run_mode(args.mode)
    _colony_goal = ablation.task_goal(args.ablation_task_id, args.goal.strip())
    _model_profile = args.model_profile or config.default_model_profile_for_mode(_run_mode)
    if _model_profile:
        config.apply_model_profile(_model_profile)

    if not os.environ.get("ENDGAME_BOOTSTRAPPED"):
        log.cleanup_runtime()

    _session_dir = str(log.session_dir())
    log.init("events-reactor.jsonl", config.EVENT_BUDGET)
    if _colony_goal:
        comms.set_colony_goal(_colony_goal, source="reactor")
    _breeder.load()
    slots_expected = 1 if _run_mode == "unicore" else config.SLOTS
    baseline_persona = args.unicore_persona.strip() or config.UNICORE_DEFAULT_PERSONA
    run = ablation.start_run(
        mode=_run_mode,
        goal=_colony_goal,
        model_profile=_model_profile,
        session_dir=_session_dir,
        persona=baseline_persona if _run_mode == "unicore" else "colony",
        task_id=args.ablation_task_id.strip(),
        slots_expected=slots_expected,
    )
    _ablation_run_dir = str(run["run_dir"])
    os.environ["ENDGAME_ABLATION_RUN_ID"] = str(run["run_id"])
    os.environ["ENDGAME_ABLATION_DIR"] = _ablation_run_dir
    log.emit("reactor.start", {"mode": _run_mode, "slots": slots_expected,
                                "profile": _model_profile or "auto",
                                "ablation_run_id": run["run_id"]})
    print(f"REACTOR | mode={_run_mode} | {slots_expected} slot(s) | profile={_model_profile or 'auto'}")
    if _colony_goal:
        print(f"  goal: {_colony_goal[:100]}")
    print(f"  session: {_session_dir}")
    print(f"  ablation: {_ablation_run_dir}")

    if _run_mode == "unicore":
        pid = spawn(1, baseline_persona, _colony_goal, priority=config.PRI_NORMAL)
        print(f"  s1: {baseline_persona} PID={pid}")
    else:
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
        if time.time() - _last_ablation_summary >= ABLATION_SUMMARY_INTERVAL:
            _last_ablation_summary = time.time()
            try:
                ablation.summarize_session(_session_dir, run_dir=_ablation_run_dir, status="running")
            except Exception as exc:
                log.emit("ablation.summary_error", {"error": str(exc)[:200]})
        if _run_mode == "colony":
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
                if _run_mode == "unicore":
                    persona = str(info.get("persona", "")) or baseline_persona
                else:
                    persona = select_respawn_persona(sid, str(info.get("persona", "")))
                print(f"  RESPAWN s{sid} ({persona})")
                log.emit("reactor.respawn", {"slot": sid, "persona": persona, "mode": _run_mode})
                spawn(sid, persona, info.get("goal", ""), info.get("priority", 0))
