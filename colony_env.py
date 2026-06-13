"""Runtime environment injected into every agent Python script."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR: Path = Path(__file__).parent.resolve()
COMMS_DIR: Path = BASE_DIR / "runtime" / "comms"
PLUGINS_DIR: Path = BASE_DIR / "plugins"
COMMS_DIR.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR.mkdir(exist_ok=True)

from comms import (  # noqa: E402
    post as bus_post, agent_id as bus_id, request as bus_request, route as bus_route,
)


def enable_gui() -> None:
    (BASE_DIR / "gui_mode").write_text("1", encoding="utf-8")


def pause_reactor() -> None:
    import log
    log.set_paused(True)


def spawn_main(goal: str = "", budget: int = 20) -> int:
    child_events = f"events-child-{os.getpid()}.jsonl"
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal or "print('spawned')", "--backend", "lmstudio",
         "--event-budget", str(budget), "--events-path", child_events],
        cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    return proc.pid
