"""Shared harness utilities for Slot 1 server + file-proxy cognition."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SCRATCH = Path(r"C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer")
SLOT_PORT = 9078
BASE = f"http://127.0.0.1:{SLOT_PORT}"
REQ = ROOT / "comms" / "slot1_cognition" / "request.json"
RESP = ROOT / "comms" / "slot1_cognition" / "response.json"
STATE = ROOT / "state.slot1.json"


def kill_port(port: int = SLOT_PORT) -> None:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return
    pids: set[int] = set()
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            try:
                pids.add(int(line.split()[-1]))
            except (ValueError, IndexError):
                continue
    for pid in pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if pids:
        time.sleep(1.0)


def clear_comms(archive_stale: bool = True) -> None:
    """Remove cognition queue files and optional fresh-run state. Call before server start."""
    REQ.parent.mkdir(parents=True, exist_ok=True)
    archive = REQ.parent / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    for path in (REQ, RESP):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                if archive_stale:
                    stamp = int(time.time() * 1000)
                    try:
                        path.rename(archive / f"stale.{path.name}.{stamp}")
                    except OSError:
                        pass
    for path in (ROOT / "state.json", STATE, ROOT / "bus.json"):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def clear_proxy_only() -> None:
    """Clear pending cognition files without touching saved run state."""
    for path in (REQ, RESP):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def http_json(method: str, path: str, body: dict | None = None, timeout: int = 15) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def start_slot1_server() -> subprocess.Popen:
    env = os.environ.copy()
    env["ENDGAME_SLOT"] = "1"
    env["ENDGAME_STATE"] = str(STATE)
    env["ENDGAME_WIRING"] = str(ROOT / "prompts" / "wiring.json")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    kill_port(SLOT_PORT)


def wait_health(timeout_s: float = 30.0) -> dict:
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        try:
            health = http_json("GET", "/health", timeout=3)
            if health.get("ok"):
                return health
        except Exception as exc:
            last_err = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"Slot 1 not healthy on {BASE}: {last_err}")


def ensure_proxy_clear() -> None:
    try:
        http_json("POST", "/llm-proxy/clear", {"confirm": True}, timeout=5)
    except Exception:
        clear_proxy_only()


def wait_run_idle(goal: str, timeout_s: int = 300) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        try:
            health = http_json("GET", "/health", timeout=5)
            last = http_json("GET", "/state", timeout=5)
            run_info = health.get("run") or {}
            running = bool(run_info.get("running"))
            queued = int(run_info.get("queued", 0) or 0)
            if not running and queued == 0:
                if last.get("goal") == goal:
                    if last.get("history") or last.get("satisfied") is not None:
                        break
                    if last.get("plan_failed") or last.get("self_modify_exhausted"):
                        break
                    if str(last.get("last_error", "")).startswith("planner:"):
                        break
        except Exception:
            pass
        time.sleep(1.0)
    return last


def _label_value(user: str, label: str) -> str:
    prefix = f"{label}:"
    for line in user.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _match_step_index(text: str, steps: list) -> int:
    if not steps:
        return 0
    needle = (text or "").strip()
    needle_l = needle.lower()
    if not needle_l:
        return 0
    for i, step in enumerate(steps):
        desc = str(step.get("description", "")).strip()
        if desc == needle or desc.lower() == needle_l:
            return i
    for i, step in enumerate(steps):
        desc = str(step.get("description", "")).lower()
        if desc and (desc in needle_l or needle_l in desc):
            return i
    return 0


class ProxyResponder:
    """Answers file_proxy requests honoring call_node two-pass LLM semantics."""

    def __init__(self, script: dict):
        self.script = script
        self._stop = threading.Event()
        self._answered: set[str] = set()

    def stop(self) -> None:
        self._stop.set()

    def _circuit(self, system: str, user: str) -> str:
        if "ROLE: Planner" in system:
            return "planner"
        if "ROLE: Act" in system:
            return "act"
        if "ROLE: Verifier" in system:
            return "verify"
        if "ROLE: Reflector" in system:
            return "reflect"
        if "SUBTASK:" in user and "SCREEN" in user:
            return "act"
        if "STEP:" in user and "LAST_OUTCOME" in user:
            return "verify"
        if "GOAL:" in user and "SUBTASK" not in user and "STEP" not in user:
            return "planner"
        return "reflect"

    def _steps(self) -> list:
        return list(self.script.get("planner", {}).get("data", {}).get("steps", []))

    def _decide_payload(self, system: str, user: str) -> dict:
        circuit = self._circuit(system, user)
        steps = self._steps()

        if circuit == "planner":
            return self.script["planner"]

        if circuit == "act":
            idx = _match_step_index(_label_value(user, "SUBTASK"), steps)
            acts = self.script.get("acts", [])
            if acts and idx < len(acts):
                return acts[idx]
            return {"record_type": "action", "data": {"conclusion": "CANNOT", "actions": []}}

        if circuit == "verify":
            outcome = _label_value(user, "LAST_OUTCOME").lower()
            idx = _match_step_index(_label_value(user, "STEP"), steps)
            if "ok:" in outcome and any(v in outcome for v in ("hotkey", "open_url", "write", "focus", "press")):
                return {
                    "record_type": "verdict",
                    "data": {"confirmed": True, "evidence": outcome, "reason": "structural OK"},
                }
            verdicts = self.script.get("verdicts", [])
            if idx < len(verdicts):
                return verdicts[idx]
            return {
                "record_type": "verdict",
                "data": {"confirmed": True, "evidence": outcome or "ok", "reason": "fallback confirm"},
            }

        idx = _match_step_index(_label_value(user, "STEP"), steps)
        reflects = self.script.get("reflects", [])
        if idx < len(reflects):
            return reflects[idx]
        return {
            "record_type": "diagnosis",
            "data": {"diagnosis": "retry", "suggestion": "retry same step", "should_replan": False},
        }

    def _build_response(self, req_id: str, req: dict) -> dict:
        messages = req.get("messages") or []
        system = str(messages[0].get("content", "")) if messages else ""
        user = str(messages[-1].get("content", "")) if messages else ""

        if "DECIDE NOW" not in user:
            circuit = self._circuit(system, user)
            prose = f"ROD reasoning for {circuit}: review goal, step, screen, and history before JSON."
            return {
                "id": req_id,
                "choices": [{"message": {"content": prose, "reasoning_content": prose}}],
            }

        payload = self._decide_payload(system, user)
        return {
            "id": req_id,
            "choices": [{"message": {"content": json.dumps(payload), "reasoning_content": ""}}],
        }

    def run(self) -> None:
        while not self._stop.is_set():
            if not REQ.exists():
                time.sleep(0.02)
                continue
            try:
                req = json.loads(REQ.read_text(encoding="utf-8"))
            except Exception:
                time.sleep(0.02)
                continue
            req_id = str(req.get("id", "") or "")
            if not req_id or req_id in self._answered:
                time.sleep(0.02)
                continue
            response = self._build_response(req_id, req)
            RESP.parent.mkdir(parents=True, exist_ok=True)
            RESP.write_text(json.dumps(response, indent=2), encoding="utf-8")
            self._answered.add(req_id)
            time.sleep(0.02)


def start_proxy(script: dict) -> tuple[ProxyResponder, threading.Thread]:
    responder = ProxyResponder(script)
    thread = threading.Thread(target=responder.run, daemon=True)
    thread.start()
    return responder, thread