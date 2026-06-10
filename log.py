from __future__ import annotations
import atexit
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from config import EVENTS_PATH, LOG_LOCK_PATH, PAUSE_PATH

_handle: TextIO | None = None
_events_path: Path = EVENTS_PATH
_lock_fd: int | None = None
_counter: int = 0
_work: int = 0
_budget: int = 20

# Math heartbeat is telemetry — does not consume work budget.
_MATH_PHASES: frozenset[str] = frozenset({"stagnation", "lorenz", "pid"})


def paused() -> bool:
    return PAUSE_PATH.exists()


def set_paused(on: bool) -> None:
    if on:
        PAUSE_PATH.write_text("", encoding="utf-8")
    else:
        PAUSE_PATH.unlink(missing_ok=True)


def _release_log_lock() -> None:
    global _lock_fd
    if _lock_fd is not None:
        try:
            os.close(_lock_fd)
        except OSError:
            pass
        _lock_fd = None
    try:
        LOG_LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _acquire_log_lock() -> Path:
    global _events_path, _lock_fd
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _lock_fd = os.open(str(LOG_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_lock_fd, str(os.getpid()).encode())
        atexit.register(_release_log_lock)
        return EVENTS_PATH
    except FileExistsError:
        return EVENTS_PATH.parent / f"events-{os.getpid()}.jsonl"


def init(budget: int) -> Path:
    global _handle, _counter, _work, _budget, _events_path
    _counter = 0
    _work = 0
    _budget = budget
    _events_path = _acquire_log_lock()
    _handle = _events_path.open("a", encoding="utf-8", newline="\n")
    return _events_path


def emit(phase: str, data: Any = None) -> int:
    """Single event bus. When paused, events sink to null — no write, no budget."""
    global _counter, _work
    if paused():
        return _counter
    _counter += 1
    if phase not in _MATH_PHASES:
        _work += 1
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
    return _counter


def exhausted() -> bool:
    return _work >= _budget


def count() -> int:
    return _counter


def work_count() -> int:
    return _work


def budget() -> int:
    return _budget


def close() -> None:
    global _handle
    if _handle:
        _handle.close()
        _handle = None
    _release_log_lock()