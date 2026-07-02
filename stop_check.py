"""Stop check mechanism for endgame-ai.

Every process (organism, workbench, subprocesses) should:
1. Call stop_check.check_stop() periodically (or at chokepoints)
2. Call stop_check.register_pid() at startup to create pid file

When stop.txt exists in the workspace root, all processes exit immediately.
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent.resolve()
STOP_FILE = ROOT / "stop.txt"
PID_DIR = ROOT / "pids"
PID_DIR.mkdir(exist_ok=True)


def register_pid(name: str) -> pathlib.Path:
    """Register this process by writing its PID to pids/{name}.pid."""
    pid_file = PID_DIR / f"{name}.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    return pid_file


def unregister_pid(name: str) -> None:
    """Remove PID file for this process."""
    pid_file = PID_DIR / f"{name}.pid"
    if pid_file.exists():
        pid_file.unlink()


def check_stop(name: str = "process") -> None:
    """Check for stop.txt and exit immediately if found.
    
    Call this at chokepoints in long-running loops.
    """
    if STOP_FILE.exists():
        print(f"[{name}] stop.txt detected, exiting", flush=True)
        unregister_pid(name)
        sys.exit(0)


def request_stop(reason: str = "") -> None:
    """Create stop.txt to signal all processes to stop."""
    STOP_FILE.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}: {reason}\n", encoding="utf-8")
    print(f"[stop_check] stop.txt created: {reason}", flush=True)


def clear_stop() -> None:
    """Remove stop.txt to allow new runs."""
    if STOP_FILE.exists():
        STOP_FILE.unlink()
        print("[stop_check] stop.txt cleared", flush=True)


def kill_all_pids() -> None:
    """Kill all registered PIDs (fallback if stop.txt is ignored)."""
    import psutil
    for pid_file in PID_DIR.glob("*.pid"):
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=2)
                print(f"[stop_check] terminated PID {pid} ({pid_file.stem})", flush=True)
        except (ValueError, psutil.NoSuchProcess, psutil.TimeoutExpired, PermissionError):
            pass
        finally:
            pid_file.unlink(missing_ok=True)


def wait_for_stop(timeout: float = 0, poll_interval: float = 0.5) -> bool:
    """Wait for stop.txt to appear. Returns True if stop requested."""
    start = time.time()
    while True:
        if STOP_FILE.exists():
            return True
        if timeout and time.time() - start >= timeout:
            return False
        time.sleep(poll_interval)