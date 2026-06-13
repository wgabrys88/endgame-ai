"""Event log — append-only JSONL per process, session-based folders."""
from __future__ import annotations
import glob
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
_session_dir: Path | None = None


def session_dir() -> Path:
    """Return or create the session directory (timestamped)."""
    global _session_dir
    if _session_dir is None:
        # Use env if set (reactor passes this to all slots)
        env_sd = os.environ.get("ENDGAME_SESSION_DIR", "")
        if env_sd:
            _session_dir = Path(env_sd)
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            _session_dir = config.BASE_DIR / "sessions" / ts
        _session_dir.mkdir(parents=True, exist_ok=True)
    return _session_dir


def init(events_path: str | None = None, budget: int = 999999) -> Path:
    global _handle, _counter, _budget, _events_path
    _counter = 0
    _budget = budget
    sd = session_dir()
    if events_path:
        # Per-slot events file goes into session dir
        fname = Path(events_path).name
        _events_path = sd / fname
    else:
        _events_path = sd / "events.jsonl"
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


def cleanup_runtime() -> None:
    """Wipe runtime data for fresh start (bus only, sessions preserved)."""
    config.BUS_DIR.mkdir(parents=True, exist_ok=True)
    config.BUS_CHAT_PATH.write_text("[]\n", encoding="utf-8")
    if config.BUS_EVENTS_PATH.exists():
        config.BUS_EVENTS_PATH.write_text("", encoding="utf-8")
    if config.BUS_INJECT_PATH.exists():
        config.BUS_INJECT_PATH.write_text("", encoding="utf-8")
