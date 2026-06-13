"""Reactor — keeps 5 slots alive. Slot 1 = comms_operator (fixed). Slots 2-5 = dynamic."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from typing import Any

import config
import log

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 5
slots: dict[int, dict[str, Any]] = {}
_model_profile: str = ""
_session_dir: str = ""


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

    # Control loop: respawn dead slots
    while True:
        time.sleep(CONTROL_INTERVAL)
        for sid in list(slots):
            if not is_alive(sid):
                info = slots.pop(sid)
                print(f"  RESPAWN s{sid} ({info['persona']})")
                spawn(sid, info["persona"], info.get("goal", ""), info.get("priority", 0))
