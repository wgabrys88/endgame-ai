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
_file_lines: int = 0
_emits_since_trim: int = 0

# Math heartbeat is telemetry - does not consume work budget.
_MATH_PHASES: frozenset[str] = frozenset({"math", "stagnation", "lorenz", "pid"})
# Scheduler cooldown ticks are idle waits, not work.
_QUIET_SCHEDULE_REASONS: frozenset[str] = frozenset({"plan_cooldown"})

_DROP_LOG_KEYS: frozenset[str] = frozenset({"tokens"})

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
    if not config.LOG_LOCK_PATH.exists():
        return None
    try:
        return int(config.LOG_LOCK_PATH.read_text(encoding="utf-8").strip())
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
        config.LOG_LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def stop_reactor_tree() -> bool:
    """Kill the live reactor process tree (reactor + child agents). Returns True if signalled."""
    pid = _lock_pid()
    if pid is None or not _pid_alive(pid):
        clean_stale_lock()
        return False
    os.system(f"taskkill /F /T /PID {pid} >nul 2>&1")
    time.sleep(1)
    clean_stale_lock()
    return True


_RUNTIME_FILES: tuple[str, ...] = (
    "events.jsonl",
    "events_log_files.txt",
    "snapshot.json",
    "report.md",
    "status.log",
    "monitor.log",
    "colony_snapshot.json",
    "respawn.json",
    "disabled.json",
    "child_pids.json",
    "goal.txt",
)

_RUNTIME_DIRS: tuple[str, ...] = (
    "reactor_colony_data",
    "terminals",
)

_LESSONS_KEEP: int = 60


def cleanup_runtime(*, kill_reactor: bool = True) -> None:
    """Wipe session artifacts. Call before a fresh boot."""
    global _handle, _counter, _work, _file_lines, _emits_since_trim
    if kill_reactor:
        stop_reactor_tree()
    close()
    _release_log_lock()
    _counter = 0
    _work = 0
    _file_lines = 0
    _emits_since_trim = 0
    base = config.BASE_DIR
    for name in _RUNTIME_FILES:
        try:
            (base / name).unlink(missing_ok=True)
        except OSError:
            pass
    for path in base.glob("events*.jsonl"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    for flag in (config.PAUSE_PATH, config.GUI_MODE_PATH):
        try:
            flag.unlink(missing_ok=True)
        except OSError:
            pass
    lessons = base / "lessons.jsonl"
    if lessons.exists():
        try:
            lines = [ln for ln in lessons.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if len(lines) > _LESSONS_KEEP:
                lessons.write_text("\n".join(lines[-_LESSONS_KEEP:]) + "\n", encoding="utf-8")
        except OSError:
            pass
    for tmp in base.glob("tmp*.py"):
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    for dirname in _RUNTIME_DIRS:
        path = base / dirname
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    try:
        config.LOG_LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    runtime = base / "runtime"
    if runtime.is_dir():
        shutil.rmtree(runtime, ignore_errors=True)
    (base / "runtime" / "comms").mkdir(parents=True, exist_ok=True)
    comms = base / "runtime" / "comms"
    for seed_name, seed_content in (
        ("messages.json", "[]\n"),
        ("inject.jsonl", ""),
    ):
        seed = comms / seed_name
        seed.write_text(seed_content, encoding="utf-8")
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


def active_events_path() -> Path:
    """Resolve the events file the live reactor is writing."""
    clean_stale_lock()
    pid = _lock_pid()
    if pid is not None and _pid_alive(pid):
        return config.EVENTS_PATH
    best = config.EVENTS_PATH
    best_mtime = best.stat().st_mtime if best.exists() else 0.0
    for path in config.BASE_DIR.glob("events-*.jsonl"):
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
        config.LOG_LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _acquire_log_lock() -> Path:
    global _events_path, _lock_fd
    clean_stale_lock()
    config.EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _lock_fd = os.open(str(config.LOG_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_lock_fd, str(os.getpid()).encode())
        atexit.register(_release_log_lock)
    except FileExistsError:
        pass
    return config.EVENTS_PATH


def _count_file_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def trim_events_file(path: Path | None = None, max_lines: int | None = None) -> int:
    """Keep only the most recent max_lines in an events jsonl file. Returns lines kept."""
    global _handle, _file_lines, _emits_since_trim
    target = path or _events_path
    limit = max_lines if max_lines is not None else config.EVENT_ROLLING_MAX_LINES
    if limit <= 0 or not target.exists():
        return _file_lines if target == _events_path else 0
    close_own = path is None and _handle is not None
    if close_own:
        _handle.flush()
        _handle.close()
        _handle = None
    try:
        with target.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        if target == _events_path:
            _file_lines = 0
            _emits_since_trim = 0
        if close_own:
            _handle = target.open("a", encoding="utf-8", newline="\n")
        return 0
    if len(lines) > limit:
        lines = lines[-limit:]
        try:
            with target.open("w", encoding="utf-8", newline="\n") as fh:
                fh.writelines(lines)
        except OSError:
            if close_own:
                _handle = target.open("a", encoding="utf-8", newline="\n")
            return _file_lines if target == _events_path else 0
    kept = len(lines)
    if target == _events_path:
        _file_lines = kept
        _emits_since_trim = 0
        if close_own:
            _handle = target.open("a", encoding="utf-8", newline="\n")
    return kept


def trim_all_event_logs(max_lines: int | None = None) -> None:
    """Trim every events*.jsonl in the project root (skips the active write handle)."""
    own = _events_path
    for path in sorted(config.BASE_DIR.glob("events*.jsonl")):
        if path == own:
            continue
        trim_events_file(path, max_lines=max_lines)


def _maybe_trim() -> None:
    global _emits_since_trim
    limit = config.EVENT_ROLLING_MAX_LINES
    if limit <= 0 or _file_lines <= limit:
        return
    _emits_since_trim += 1
    if _emits_since_trim < config.EVENT_ROLLING_TRIM_CHECK:
        return
    trim_events_file()


def init(budget: int) -> Path:
    global _handle, _counter, _work, _budget, _events_path, _file_lines, _emits_since_trim
    _counter = 0
    _work = 0
    _budget = budget
    _emits_since_trim = 0
    _events_path = _acquire_log_lock()
    if _events_path.exists() and _events_path.stat().st_size > 0:
        _file_lines = _count_file_lines(_events_path)
        if config.EVENT_ROLLING_MAX_LINES > 0 and _file_lines > config.EVENT_ROLLING_MAX_LINES:
            trim_events_file()
    else:
        _file_lines = 0
    _handle = _events_path.open("a", encoding="utf-8", newline="\n")
    return _events_path


def _clip_text(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + "..."


def _compact_data(phase: str, data: Any) -> Any:
    if data is None:
        return None
    if not isinstance(data, dict):
        return data
    compact: dict[str, Any] = {}
    for key, value in data.items():
        if key in _DROP_LOG_KEYS:
            continue
        if key == "obs" and isinstance(value, str):
            compact[key] = _clip_text(value, config.LOG_OBS_MAX)
        elif key == "goal" and isinstance(value, str):
            compact[key] = _clip_text(value, config.LOG_GOAL_MAX)
        elif key in ("from", "to") and isinstance(value, str):
            compact[key] = _clip_text(value, config.LOG_GOAL_MAX)
        elif key == "error" and isinstance(value, str):
            compact[key] = _clip_text(value, config.LOG_OBS_MAX)
        elif key == "evidence" and isinstance(value, str):
            compact[key] = _clip_text(value, config.LOG_OBS_MAX)
        else:
            compact[key] = value
    return compact


def emit(phase: str, data: Any = None) -> int:
    """Single event bus. When paused, only math telemetry flows - work events sink."""
    global _counter, _work, _file_lines
    if (
        phase == "schedule"
        and isinstance(data, dict)
        and str(data.get("reason", "")) in _QUIET_SCHEDULE_REASONS
    ):
        return _counter
    if paused() and phase not in _MATH_PHASES:
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
    compact = _compact_data(phase, data)
    if compact is not None:
        record["d"] = compact
    _handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    _handle.flush()
    _file_lines += 1
    _maybe_trim()
    try:
        import comms
        comms.mirror_event(phase, compact if compact is not None else data, source=comms.agent_id())
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