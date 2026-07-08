import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent.resolve()
STOP_FILE = ROOT / "runtime_stop.json"


def _pid_file(name: str) -> pathlib.Path:
    return ROOT / f"runtime_{name}.pid"


def register_pid(name: str) -> pathlib.Path:
    pid_file = _pid_file(name)
    payload = {
        "pid": os.getpid(),
        "name": name,
        "started_at": time.time(),
        "started_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    }
    pid_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return pid_file


def unregister_pid(name: str) -> None:
    pid_file = _pid_file(name)
    if pid_file.exists():
        pid_file.unlink()


def stop_requested() -> bool:
    return STOP_FILE.exists()


def check_stop(name: str = "process") -> None:
    if stop_requested():
        print(f"[{name}] {STOP_FILE.name} detected, exiting", flush=True)
        unregister_pid(name)
        sys.exit(0)


def request_stop(reason: str = "", *, source: str = "manual") -> None:
    payload = {
        "schema": "endgame-ai.stop.v1",
        "created_at": time.time(),
        "created_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "source": source,
        "reason": reason,
        "pid": os.getpid(),
    }
    STOP_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stop_check] {STOP_FILE.name} created: {reason}", flush=True)


def clear_stop() -> None:
    if stop_requested():
        STOP_FILE.unlink()
        print(f"[stop_check] {STOP_FILE.name} cleared", flush=True)
