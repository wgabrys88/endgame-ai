from __future__ import annotations
import atexit
import ctypes
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from config import BASE_DIR, EVENTS_PATH, LOG_LOCK_PATH, PAUSE_PATH

_handle: TextIO | None = None
_events_path: Path = EVENTS_PATH
_lock_fd: int | None = None
_counter: int = 0
_work: int = 0
_budget: int = 20

# Math heartbeat is telemetry — does not consume work budget.
_MATH_PHASES: frozenset[str] = frozenset({"stagnation", "lorenz", "pid"})

_STILL_ACTIVE = 259
_PROCESS_SYNCHRONIZE = 0x00100000


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_SYNCHRONIZE, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return bool(ok) and code.value == _STILL_ACTIVE


def _lock_pid() -> int | None:
    if not LOG_LOCK_PATH.exists():
        return None
    try:
        return int(LOG_LOCK_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def clean_stale_lock() -> bool:
    """Remove lock file when holder process is gone. Returns True if removed."""
    pid = _lock_pid()
    if pid is None:
        return False
    if _pid_alive(pid):
        return False
    try:
        LOG_LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def paused() -> bool:
    return PAUSE_PATH.exists()


def set_paused(on: bool) -> None:
    if on:
        PAUSE_PATH.write_text("", encoding="utf-8")
    else:
        PAUSE_PATH.unlink(missing_ok=True)


def active_events_path() -> Path:
    """Resolve the events file the live reactor is writing."""
    clean_stale_lock()
    pid = _lock_pid()
    if pid is not None and _pid_alive(pid):
        return EVENTS_PATH
    best = EVENTS_PATH
    best_mtime = best.stat().st_mtime if best.exists() else 0.0
    for path in BASE_DIR.glob("events-*.jsonl"):
        try:
            mt = path.stat().st_mtime
        except OSError:
            continue
        if mt > best_mtime:
            best, best_mtime = path, mt
    return best


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
    clean_stale_lock()
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