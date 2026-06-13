"""Reactor — keeps 5 slots alive. Slot 1 = comms_operator (fixed). Slots 2-5 = dynamic."""
from __future__ import annotations
import json
import os
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
_breed_scores: dict[str, dict[str, Any]] = {}
_slot_survivors: dict[int, str] = {}
_elite_archive: dict[str, dict[str, Any]] = {}


def spawn(slot_id: int, persona: str, goal: str = "", priority: int = config.PRI_MAINTENANCE) -> int:
    """Spawn a persona in a slot. Returns PID."""
    ef = os.path.join(BASE, f"events-child-s{slot_id}.jsonl")
    for path in (ef, os.path.join(_session_dir, f"events-child-s{slot_id}.jsonl") if _session_dir else ""):
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
    if not goal:
        pfile = os.path.join(BASE, "prompts", "personalities", f"{persona}.txt")
        if os.path.exists(pfile):
            goal = open(pfile, encoding="utf-8").read().strip()
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
    """Kill a slot's process."""
    info = slots.pop(slot_id, None)
    if info:
        os.system(f"taskkill /F /T /PID {info['pid']} >nul 2>&1")


_STILL_ACTIVE = 259
_PROCESS_QUERY = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION


def is_alive(slot_id: int) -> bool:
    info = slots.get(slot_id)
    if not info:
        return False
    pid = info["pid"]
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_QUERY, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == _STILL_ACTIVE
    except (OSError, AttributeError):
        return False


def reassign(slot_id: int, persona: str, goal: str = "", priority: int = config.PRI_NORMAL) -> int:
    """Kill slot and respawn with new persona/goal."""
    kill_slot(slot_id)
    time.sleep(0.5)
    return spawn(slot_id, persona, goal, priority)


def status() -> dict[int, dict[str, Any]]:
    """Current slot status."""
    return {sid: {**info, "alive": is_alive(sid)} for sid, info in slots.items()}


def _candidate_slot(entry: dict[str, Any], payload: dict[str, Any], target: str) -> int:
    try:
        sid = int(payload.get("slot", entry.get("slot", 0)) or 0)
    except (TypeError, ValueError):
        sid = 0
    if 2 <= sid <= config.SLOTS:
        return sid
    for slot_id, info in slots.items():
        if info.get("persona") == target:
            return slot_id
    return int(config.PERSONA_SLOTS.get(target, 0) or 0)


def _candidate_fitness(payload: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float(payload.get("fitness", 0.0) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _post_breed_status(
    action: str,
    target: str,
    slot_id: int,
    fitness: float,
    *,
    niche: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        data = {
            "action": f"breed.{action}",
            "target": target,
            "slot": slot_id,
            "fitness": round(fitness, 4),
        }
        if niche:
            data["niche"] = niche[:80]
            data["elite_count"] = len(_elite_archive)
        if detail:
            data.update(detail)
        comms.post(
            "reactor",
            "reactor",
            f"breed {action} @{target} s{slot_id} fitness={fitness:.3f}"
            + (f" niche={niche[:80]}" if niche else ""),
            kind=comms.KIND_STATUS,
            data=data,
        )
    except Exception:
        pass


def _candidate_niche(payload: dict[str, Any], action: str) -> str:
    niche = str(payload.get("niche", "")).strip()[:80]
    if niche:
        return niche
    behavior = str(payload.get("behavior", "")).strip()
    band = str(payload.get("pressure_band", "")).strip()
    if behavior and band:
        return f"{behavior[:40]}:{band[:30]}"
    if action == "patch_plugin":
        return "plugin_patch:unknown_pressure"
    if action == "evict":
        return "verify_denial:unknown_pressure"
    return "general_task:unknown_pressure"


def _trim_elite_archive() -> None:
    while len(_elite_archive) > config.BREED_ELITE_MAX_NICHES:
        worst = min(
            _elite_archive,
            key=lambda n: float(_elite_archive[n].get("fitness", 0.0) or 0.0),
        )
        _elite_archive.pop(worst, None)


def _evict_elites_for(target: str) -> None:
    for niche, elite in list(_elite_archive.items()):
        if elite.get("target") == target:
            _elite_archive.pop(niche, None)


def _update_elite_archive(
    target: str,
    action: str,
    slot_id: int,
    fitness: float,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    niche = _candidate_niche(payload, action)
    previous = _elite_archive.get(niche)
    prev_fit = float(previous.get("fitness", -1.0) or -1.0) if previous else -1.0
    if previous and fitness < prev_fit + config.BREED_ELITE_MIN_DELTA:
        return False, niche
    _elite_archive[niche] = {
        "target": target,
        "action": action,
        "slot": slot_id,
        "fitness": fitness,
        "completed": str(payload.get("completed", ""))[:120],
        "behavior": str(payload.get("behavior", ""))[:60],
        "pressure_band": str(payload.get("pressure_band", ""))[:40],
        "ts": time.time(),
    }
    _trim_elite_archive()
    return True, niche


def process_evolve_candidates() -> None:
    """Select retained personas from fission-backed AgentBreeder candidates."""
    global _last_evolve_id
    for entry in comms.evolve_candidates(after_id=_last_evolve_id, limit=50):
        eid = int(entry.get("id", 0) or 0)
        _last_evolve_id = max(_last_evolve_id, eid)
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        target = comms.canonical(str(payload.get("target") or entry.get("to") or entry.get("from", "")))
        if target not in config.WORKER_PERSONAS:
            continue
        action = str(payload.get("action", "")).lower()
        slot_id = _candidate_slot(entry, payload, target)
        fitness = _candidate_fitness(payload)

        if action == "evict":
            _breed_scores.pop(target, None)
            _evict_elites_for(target)
            for sid, persona in list(_slot_survivors.items()):
                if persona == target:
                    _slot_survivors.pop(sid, None)
            _post_breed_status("evict", target, slot_id, fitness,
                               niche=_candidate_niche(payload, action))
            continue
        if action == "patch_plugin":
            is_elite, niche = _update_elite_archive(target, action, slot_id, fitness, payload)
            if is_elite:
                _post_breed_status("elite", target, slot_id, fitness, niche=niche,
                                   detail={"elite_action": action})
            continue
        if action != "retain":
            continue

        is_elite, niche = _update_elite_archive(target, action, slot_id, fitness, payload)
        if is_elite:
            _post_breed_status("elite", target, slot_id, fitness, niche=niche,
                               detail={"elite_action": action})
        previous = _breed_scores.get(target, {})
        if previous and fitness < float(previous.get("fitness", 0.0) or 0.0):
            continue
        _breed_scores[target] = {
            "fitness": fitness,
            "slot": slot_id,
            "completed": str(payload.get("completed", ""))[:120],
            "fissions": int(payload.get("fissions", 0) or 0),
        }
        if 2 <= slot_id <= config.SLOTS and fitness >= config.BREED_RETAIN_MIN:
            incumbent = _slot_survivors.get(slot_id, "")
            incumbent_fit = float(_breed_scores.get(incumbent, {}).get("fitness", -1.0) or -1.0)
            if fitness >= incumbent_fit:
                _slot_survivors[slot_id] = target
                print(f"  BREED RETAIN s{slot_id} -> {target} fitness={fitness:.3f}")
                _post_breed_status("retain", target, slot_id, fitness, niche=niche)


def select_respawn_persona(slot_id: int, fallback: str) -> str:
    """Choose the persona that survives into a worker respawn."""
    if slot_id < 2:
        return fallback
    retained = _slot_survivors.get(slot_id, "")
    if retained in config.WORKER_PERSONAS:
        fitness = float(_breed_scores.get(retained, {}).get("fitness", 0.0) or 0.0)
        if fitness >= config.BREED_RETAIN_MIN:
            return retained
    if fallback in config.WORKER_PERSONAS:
        return fallback
    return config.SLOT_DEFAULTS.get(slot_id, fallback)


if __name__ == "__main__":
    # Parse CLI
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--model-profile" and i < len(sys.argv) - 1:
            _model_profile = sys.argv[i + 1]
        elif arg.startswith("--model-profile="):
            _model_profile = arg.split("=", 1)[1]
    if _model_profile:
        config.apply_model_profile(_model_profile)

    if not os.environ.get("ENDGAME_BOOTSTRAPPED"):
        log.cleanup_runtime()

    # Create session directory for this run
    _session_dir = str(log.session_dir())
    print(f"REACTOR | {config.SLOTS} slots | profile={_model_profile or 'auto'}")
    print(f"  session: {_session_dir}")

    # Slot 1: comms_operator (always)
    pid = spawn(1, "comms_operator", priority=config.PRI_NORMAL)
    print(f"  s1: comms_operator PID={pid}")

    # Slots 2-5: start with default personas doing maintenance
    defaults = ["architect", "implementor", "reviewer", "devops"]
    for i, persona in enumerate(defaults, 2):
        pid = spawn(i, persona, priority=config.PRI_MAINTENANCE)
        print(f"  s{i}: {persona} PID={pid}")
        time.sleep(1.0)  # stagger — avoid 4 parallel LLM cold-starts

    print(f"\nREACTOR ONLINE. {len(slots)} slots loaded.\n")

    # Control loop: MoE reassign + respawn dead slots
    while True:
        time.sleep(CONTROL_INTERVAL)
        process_evolve_candidates()
        for cmd in comms.drain_control():
            action = str(cmd.get("action", ""))
            if action == "reassign":
                sid = int(cmd.get("slot", 0) or 0)
                persona = str(cmd.get("persona", ""))
                if sid < 2 and persona:
                    for s, info in slots.items():
                        if info.get("persona") == str(cmd.get("from_persona", "")):
                            sid = s
                            break
                if sid >= 2 and sid <= config.SLOTS and persona in config.WORKER_PERSONAS:
                    pri = int(cmd.get("priority", config.PRI_NORMAL))
                    print(f"  MOE REASSIGN s{sid} -> {persona} ({cmd.get('reason', '')[:60]})")
                    reassign(sid, persona, priority=pri)
        for sid in list(slots):
            if not is_alive(sid):
                info = slots.pop(sid)
                persona = select_respawn_persona(sid, str(info.get("persona", "")))
                print(f"  RESPAWN s{sid} ({persona})")
                spawn(sid, persona, info.get("goal", ""), info.get("priority", 0))
