"""Runtime environment injected into every agent Python script."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR: Path = Path(__file__).parent.resolve()
COMMS_DIR: Path = BASE_DIR / "runtime" / "comms"
PLUGINS_DIR: Path = BASE_DIR / "plugins"
COMMS_DIR.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR.mkdir(exist_ok=True)

from comms import post as bus_post, agent_id as bus_id, request as bus_request  # noqa: E402

_spawn_counter = 0


def enable_gui() -> None:
    (BASE_DIR / "gui_mode").write_text("1", encoding="utf-8")


def pause_reactor() -> None:
    import log
    log.set_paused(True)


def spawn_main(goal: str = "", budget: int = 20) -> int:
    global _spawn_counter
    _spawn_counter += 1
    child_events = f"events-child-{os.getpid()}-{_spawn_counter}.jsonl"
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal or "print('spawned')", "--backend", "lmstudio",
         "--event-budget", str(budget), "--events-path", child_events],
        cwd=str(BASE_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    return int(proc.pid)