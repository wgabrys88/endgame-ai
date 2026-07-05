from __future__ import annotations

import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent.resolve()
STOP_FILE = ROOT / "runtime_stop.txt"


def _pid_file(name: str) -> pathlib.Path:
    return ROOT / f"runtime_{name}.pid"


def register_pid(name: str) -> pathlib.Path:
    pid_file = _pid_file(name)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    return pid_file


def unregister_pid(name: str) -> None:
    pid_file = _pid_file(name)
    if pid_file.exists():
        pid_file.unlink()


def check_stop(name: str = "process") -> None:
    if STOP_FILE.exists():
        print(f"[{name}] runtime_stop.txt detected, exiting", flush=True)
        unregister_pid(name)
        sys.exit(0)


def request_stop(reason: str = "") -> None:
    STOP_FILE.write_text(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}: {reason}\n", encoding="utf-8")
    print(f"[stop_check] runtime_stop.txt created: {reason}", flush=True)


def clear_stop() -> None:
    if STOP_FILE.exists():
        STOP_FILE.unlink()
        print("[stop_check] runtime_stop.txt cleared", flush=True)


def kill_all_pids() -> None:
    import psutil
    for pid_file in ROOT.glob("runtime_*.pid"):
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=2)
                print(f"[stop_check] terminated PID {pid} ({pid_file.name})", flush=True)
        except (ValueError, psutil.NoSuchProcess, psutil.TimeoutExpired, PermissionError):
            pass
        finally:
            pid_file.unlink(missing_ok=True)


def wait_for_stop(timeout: float = 0, poll_interval: float = 0.5) -> bool:
    start = time.time()
    while True:
        if STOP_FILE.exists():
            return True
        if timeout and time.time() - start >= timeout:
            return False
        time.sleep(poll_interval)
