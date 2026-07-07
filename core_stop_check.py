from __future__ import annotations

import json
import os
import pathlib
import signal
import sys
import time

ROOT = pathlib.Path(__file__).parent.resolve()
STOP_FILE = ROOT / "runtime_stop.json"
SELF_EVOLUTION_FILE = ROOT / "runtime_self_evolution_enabled.json"


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


def self_evolution_enabled() -> bool:
    return SELF_EVOLUTION_FILE.exists()


def ensure_self_evolution_enabled(*, source: str = "reset") -> None:
    payload = {
        "schema": "endgame-ai.self-evolution.v1",
        "enabled": True,
        "created_at": time.time(),
        "created_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "source": source,
        "contract": "Delete this file to disable node_self_modify apply/commit/push until the next reset recreates it.",
        "pid": os.getpid(),
    }
    SELF_EVOLUTION_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stop_check] {SELF_EVOLUTION_FILE.name} enabled", flush=True)


def kill_all_pids() -> None:
    for pid_file in ROOT.glob("runtime_*.pid"):
        try:
            raw = pid_file.read_text(encoding="utf-8").strip()
            try:
                obj = json.loads(raw)
                pid = int(obj.get("pid"))
            except json.JSONDecodeError:
                pid = int(raw)
            if pid != os.getpid():
                os.kill(pid, signal.SIGTERM)
                print(f"[stop_check] terminated PID {pid} ({pid_file.name})", flush=True)
        except (ValueError, OSError, PermissionError):
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
