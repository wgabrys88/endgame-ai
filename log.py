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


def cleanup_runtime(*, deep: bool = True) -> None:
    """Wipe runtime state for a fresh colony start."""
    config.BUS_DIR.mkdir(parents=True, exist_ok=True)
    config.BUS_CHAT_PATH.write_text("[]\n", encoding="utf-8")
    for path in (
        config.BUS_EVENTS_PATH,
        config.BUS_INJECT_PATH,
        config.BUS_CONTROL_PATH,
    ):
        if path.exists():
            path.write_text("", encoding="utf-8")
    for flag in (
        config.GUI_MODE_PATH,
        config.UNCONSTRAINED_MODE_PATH,
        config.COLONY_GOAL_PATH,
        config.BASE_DIR / "pause",
        config.LMS_GLOBAL_LOCK_PATH,
    ):
        try:
            flag.unlink(missing_ok=True)
        except OSError:
            pass
    if not deep:
        return
    _runtime_keep = frozenset({
        "comms",
        "BENCH_CAMPAIGN_20260614.md",
        "bench_profiles.example.json",
    })
    runtime = config.BASE_DIR / "runtime"
    if runtime.is_dir():
        for path in runtime.iterdir():
            if path.name in _runtime_keep:
                continue
            try:
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass
    try:
        config.BREED_ARCHIVE_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    for pattern in ("events*.jsonl", "events-reactor.jsonl"):
        for path in glob.glob(str(config.BASE_DIR / pattern)):
            try:
                os.remove(path)
            except OSError:
                pass
