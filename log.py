"""Event log — append-only JSONL, process lock, pause gate, bus mirroring."""
from __future__ import annotations
import atexit
import ctypes
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

import config

_handle: TextIO | None = None
_events_path: Path = config.EVENTS_PATH
_lock_fd: int | None = None
_counter: int = 0
_work: int = 0
_budget: int = 20

_MATH_PHASES: frozenset[str] = frozenset({"math", "stagnation", "lorenz", "pid"})
_QUIET_REASONS: frozenset[str] = frozenset({"plan_cooldown"})
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
    try:
        return int(config.LOG_LOCK_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def clean_stale_lock() -> bool:
    pid = _lock_pid()
    if pid is None or _pid_alive(pid):
        return False
    config.LOG_LOCK_PATH.unlink(missing_ok=True)
    return True


def stop_reactor_tree() -> bool:
    pid = _lock_pid()
    if pid is None or not _pid_alive(pid):
        clean_stale_lock()
        return False
    os.system(f"taskkill /F /T /PID {pid} >nul 2>&1")
    time.sleep(1)
    clean_stale_lock()
    return True


def cleanup_runtime(*, kill_reactor: bool = True) -> None:
    global _handle, _counter, _work
    if kill_reactor:
        stop_reactor_tree()
    close()
    _release_log_lock()
    _counter = _work = 0
    base = config.BASE_DIR
    for name in ("events.jsonl", "snapshot.json", "respawn.json", "goal.txt", "child_pids.json"):
        (base / name).unlink(missing_ok=True)
    for path in base.glob("events*.jsonl"):
        path.unlink(missing_ok=True)
    for flag in (config.PAUSE_PATH, config.GUI_MODE_PATH):
        flag.unlink(missing_ok=True)
    # Trim lessons
    lessons = base / "lessons.jsonl"
    if lessons.exists():
        try:
            lines = [ln for ln in lessons.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if len(lines) > 60:
                lessons.write_text("\n".join(lines[-60:]) + "\n", encoding="utf-8")
        except OSError:
            pass
    for tmp in base.glob("tmp*.py"):
        tmp.unlink(missing_ok=True)
    for dirname in ("reactor_colony_data", "terminals"):
        p = base / dirname
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    config.LOG_LOCK_PATH.unlink(missing_ok=True)
    runtime = base / "runtime"
    if runtime.is_dir():
        shutil.rmtree(runtime, ignore_errors=True)
    # Seed comms
    config.BUS_DIR.mkdir(parents=True, exist_ok=True)
    config.BUS_CHAT_PATH.write_text("[]\n", encoding="utf-8")
    config.BUS_EVENTS_PATH.write_text("", encoding="utf-8")
    config.BUS_INJECT_PATH.write_text("", encoding="utf-8")
    time.sleep(0.1)


def paused() -> bool:
    return config.PAUSE_PATH.exists()


def set_paused(on: bool) -> None:
    if on:
        config.PAUSE_PATH.write_text("", encoding="utf-8")
    else:
        config.PAUSE_PATH.unlink(missing_ok=True)


def reactor_running() -> bool:
    pid = _lock_pid()
    return pid is not None and _pid_alive(pid)


def _release_log_lock() -> None:
    global _lock_fd
    if _lock_fd is not None:
        try:
            os.close(_lock_fd)
        except OSError:
            pass
        _lock_fd = None
    config.LOG_LOCK_PATH.unlink(missing_ok=True)


def _acquire_log_lock() -> Path:
    global _lock_fd
    # In reactor mode (per-agent events file), skip the shared lock entirely
    if config.EVENTS_PATH != (config.BASE_DIR / "events.jsonl"):
        return config.EVENTS_PATH
    clean_stale_lock()
    config.EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _lock_fd = os.open(str(config.LOG_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_lock_fd, str(os.getpid()).encode())
        atexit.register(_release_log_lock)
    except FileExistsError:
        pass
    return config.EVENTS_PATH


def init(budget: int) -> Path:
    global _handle, _counter, _work, _budget, _events_path
    _counter = _work = 0
    _budget = budget
    _events_path = _acquire_log_lock()
    _handle = _events_path.open("a", encoding="utf-8", newline="\n")
    return _events_path


def emit(phase: str, data: Any = None) -> int:
    global _counter, _work
    if phase == "schedule" and isinstance(data, dict) and str(data.get("reason", "")) in _QUIET_REASONS:
        return _counter
    if paused() and phase not in _MATH_PHASES:
        return _counter
    _counter += 1
    if phase not in _MATH_PHASES:
        _work += 1
    if _handle is None:
        return _counter
    record: dict[str, Any] = {"n": _counter, "t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "phase": phase}
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
