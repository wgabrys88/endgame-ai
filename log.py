"""Event log — append-only JSONL per process."""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

import config

_handle: TextIO | None = None
_events_path: Path = config.EVENTS_PATH
_counter: int = 0
_budget: int = 999999


def init(events_path: str | None = None, budget: int = 999999) -> Path:
    global _handle, _counter, _budget, _events_path
    _counter = 0
    _budget = budget
    if events_path:
        _events_path = config.BASE_DIR / events_path
    else:
        _events_path = config.EVENTS_PATH
    _events_path.parent.mkdir(parents=True, exist_ok=True)
    _handle = _events_path.open("a", encoding="utf-8", newline="\n")
    return _events_path


def emit(phase: str, data: Any = None) -> int:
    global _counter
    _counter += 1
    if _handle is None:
        return _counter
    record: dict[str, Any] = {
        "n": _counter,
        "t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "phase": phase,
    }
    if data is not None:
        record["d"] = data
    _handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    _handle.flush()
    try:
        import comms
        comms.mirror_event(phase, data, source=comms.agent_id())
    except Exception:
        pass
    return _counter


def exhausted() -> bool:
    return _counter >= _budget


def paused() -> bool:
    return (config.BASE_DIR / "pause").exists()


def cleanup_runtime(kill_reactor: bool = False) -> None:
    """Wipe session data for fresh start."""
    import glob
    if kill_reactor:
        os.system("taskkill /F /IM python.exe >nul 2>&1")
    for pat in ["events-child-*.jsonl", "events.jsonl", "snapshot.json", ".endgame.lock"]:
        for f in glob.glob(str(config.BASE_DIR / pat)):
            try:
                os.remove(f)
            except OSError:
                pass
    config.BUS_DIR.mkdir(parents=True, exist_ok=True)
    config.BUS_CHAT_PATH.write_text("[]\n", encoding="utf-8")
    if config.BUS_EVENTS_PATH.exists():
        config.BUS_EVENTS_PATH.write_text("", encoding="utf-8")
