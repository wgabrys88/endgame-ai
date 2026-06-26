"""Drive P0 goals through a clean Slot 1 server with scripted file-proxy cognition."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SCRATCH = Path(r"C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer")
REQ = ROOT / "comms" / "slot1_cognition" / "request.json"
RESP = ROOT / "comms" / "slot1_cognition" / "response.json"
STATE = ROOT / "state.slot1.json"
SLOT_PORT = 9078
BASE = f"http://127.0.0.1:{SLOT_PORT}"

GOAL_SCRIPTS = {
    "open notepad and type hello": {
        "planner": {
            "record_type": "task",
            "data": {
                "steps": [
                    {"description": "Open Notepad", "done_when": "Notepad window is open and focused"},
                    {"description": "Type hello in Notepad", "done_when": "hello text is written in Notepad"},
                ]
            },
        },
        "acts": [
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [
                        {"verb": "hotkey", "target": "win+r", "value": ""},
                        {"verb": "write", "target": "", "value": "notepad"},
                        {"verb": "press", "target": "enter", "value": ""},
                    ],
                },
            },
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [{"verb": "write", "target": "", "value": "hello"}],
                },
            },
        ],
        "verdicts": [
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
        ],
        "reflects": [
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
        ],
    },
    "navigate to google.com in chrome": {
        "planner": {
            "record_type": "task",
            "data": {
                "steps": [
                    {"description": "Navigate to google.com in Chrome", "done_when": "google.com page is loaded in Chrome"},
                ]
            },
        },
        "acts": [
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [{"verb": "open_url", "target": "chrome", "value": "google.com"}],
                },
            }
        ],
        "verdicts": [
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
        ],
        "reflects": [
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
        ],
    },
    "play shakira waka waka on youtube": {
        "planner": {
            "record_type": "task",
            "data": {
                "steps": [
                    {"description": "Open YouTube and search Shakira Waka Waka", "done_when": "YouTube results for Shakira Waka Waka are visible"},
                    {"description": "Play the Waka Waka video", "done_when": "video is playing on YouTube"},
                ]
            },
        },
        "acts": [
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [{"verb": "open_url", "target": "chrome", "value": "youtube.com/results?search_query=Shakira+Waka+Waka"}],
                },
            },
            {
                "record_type": "action",
                "data": {
                    "conclusion": "EXECUTE",
                    "actions": [
                        {"verb": "wait", "target": "", "value": "2000"},
                        {"verb": "open_url", "target": "chrome", "value": "youtube.com/watch?v=pRpeEdMmmQ0"},
                    ],
                },
            },
        ],
        "verdicts": [
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
            {"record_type": "verdict", "data": {"confirmed": False, "evidence": "defer", "reason": "structural"}},
        ],
        "reflects": [
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
            {"record_type": "diagnosis", "data": {"diagnosis": "retry", "suggestion": "retry", "should_replan": False}},
        ],
    },
}


class ProxyResponder:
    def __init__(self, script: dict):
        self.script = script
        self.act_i = 0
        self.verdict_i = 0
        self.reflect_i = 0
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _circuit(self, req: dict, user: str) -> str:
        messages = req.get("messages") or []
        system = str(messages[0].get("content", "")) if messages else ""
        if "ROLE: Planner" in system:
            return "planner"
        if "ROLE: Act" in system:
            return "act"
        if "ROLE: Verifier" in system:
            return "verify"
        if "ROLE: Reflector" in system:
            return "reflect"
        if "GOAL:" in user and "SUBTASK" not in user and "STEP" not in user:
            return "planner"
        if "SUBTASK" in user or ("SCREEN" in user and "DONE_WHEN" in user):
            return "act"
        if "STEP" in user and "LAST_OUTCOME" in user:
            return "verify"
        return "reflect"

    def _payload_for(self, req: dict, user: str) -> dict:
        circuit = self._circuit(req, user)
        if circuit == "planner":
            return self.script["planner"]
        if circuit == "act":
            acts = self.script.get("acts", [])
            idx = min(self.act_i, max(0, len(acts) - 1))
            if acts:
                if self.act_i < len(acts):
                    self.act_i += 1
                return acts[idx]
            return {
                "record_type": "action",
                "data": {"conclusion": "CANNOT", "actions": []},
            }
        if circuit == "verify":
            outcome = ""
            for line in user.splitlines():
                if line.startswith("LAST_OUTCOME:"):
                    outcome = line.split(":", 1)[1].strip().lower()
                    break
            if "ok:" in outcome and any(v in outcome for v in ("hotkey", "open_url", "write", "focus")):
                return {
                    "record_type": "verdict",
                    "data": {"confirmed": True, "evidence": outcome, "reason": "structural OK"},
                }
            verdicts = self.script.get("verdicts", [])
            if self.verdict_i < len(verdicts):
                payload = verdicts[self.verdict_i]
                self.verdict_i += 1
                return payload
            return {
                "record_type": "verdict",
                "data": {"confirmed": True, "evidence": outcome or "ok", "reason": "retry confirm"},
            }
        reflects = self.script.get("reflects", [])
        if self.reflect_i < len(reflects):
            payload = reflects[self.reflect_i]
            self.reflect_i += 1
            return payload
        return {
            "record_type": "diagnosis",
            "data": {"diagnosis": "retry", "suggestion": "retry same step", "should_replan": False},
        }

    def run(self):
        answered: set[str] = set()
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
            if not req_id or req_id in answered:
                time.sleep(0.02)
                continue
            user = ""
            messages = req.get("messages") or []
            if messages:
                user = str(messages[-1].get("content", ""))
            payload = self._payload_for(req, user)
            response = {
                "id": req_id,
                "choices": [{"message": {"content": json.dumps(payload), "reasoning_content": ""}}],
            }
            RESP.parent.mkdir(parents=True, exist_ok=True)
            RESP.write_text(json.dumps(response, indent=2), encoding="utf-8")
            answered.add(req_id)
            time.sleep(0.02)


def _http_json(method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def kill_port(port: int) -> None:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            try:
                pid = int(line.split()[-1])
            except (ValueError, IndexError):
                continue
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)


def clear_proxy_files() -> None:
    REQ.parent.mkdir(parents=True, exist_ok=True)
    for path in (REQ, RESP, ROOT / "state.json", STATE):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def wait_health(timeout_s: float = 20.0) -> dict:
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        try:
            return _http_json("GET", "/health", timeout=3)
        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.3)
    raise RuntimeError(f"server not healthy on {BASE}: {last_err}")


def start_server() -> subprocess.Popen:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        proc.wait(timeout=8)
    except Exception:
        proc.kill()


def poll_state(timeout_s: int = 240) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        try:
            last = _http_json("GET", "/state", timeout=5)
            if str(last.get("last_error", "")).startswith("planner:"):
                time.sleep(0.5)
                continue
            history = last.get("history") or []
            if last.get("satisfied") is True:
                break
            if last.get("plan_failed") or last.get("self_modify_exhausted"):
                break
            plan = last.get("plan") or []
            step = int(last.get("step", 0) or 0)
            if plan and step >= len(plan) and history:
                break
        except Exception:
            pass
        time.sleep(1)
    return last


def run_goal(goal_key: str, run_index: int, proc_holder: list) -> dict:
    clear_proxy_files()
    try:
        _http_json("POST", "/llm-proxy/clear", {"confirm": True})
    except Exception:
        pass

    script = GOAL_SCRIPTS[goal_key]
    responder = ProxyResponder(script)
    thread = threading.Thread(target=responder.run, daemon=True)
    thread.start()
    time.sleep(0.35)

    queued = _http_json("POST", "/run", {"goal": goal_key})
    state = poll_state()
    responder.stop()

    history = state.get("history") or []
    payload = {
        "goal": goal_key,
        "run": run_index,
        "port": SLOT_PORT,
        "queued": queued,
        "satisfied": state.get("satisfied"),
        "step": state.get("step"),
        "last_outcome": state.get("last_outcome"),
        "last_error": state.get("last_error"),
        "history": history,
        "post_action_title": state.get("post_action_title"),
        "memory": state.get("memory", {}),
        "screen_excerpt": (state.get("screen") or "")[:2000],
        "focus_failed": any("FAILED" in str(h.get("outcome", "")) and "focus" in str(h.get("action", "")).lower() for h in history),
        "open_url_ran": any("open_url" in str(h.get("action", "")).lower() for h in history),
        "confirm_evidence": {
            "browser_nav": any("google" in str(h.get("outcome", "")).lower() or "google" in (state.get("post_action_title") or "").lower() for h in history),
            "youtube": any("youtube" in (state.get("screen") or "").lower() or "youtube" in (state.get("post_action_title") or "").lower() for h in history),
        },
    }
    out = SCRATCH / f"p0-{goal_key.replace(' ', '-')}-run{run_index}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    kill_port(SLOT_PORT)
    clear_proxy_files()
    proc_holder: list = []
    proc = start_server()
    proc_holder.append(proc)
    health: dict = {}
    try:
        health = wait_health()
        (SCRATCH / "server-health.json").write_text(json.dumps({"started": True, "health": health}, indent=2), encoding="utf-8")
        results = []
        for goal in GOAL_SCRIPTS:
            for run in (1, 2):
                results.append(run_goal(goal, run, proc_holder))
                clear_proxy_files()
                time.sleep(1)
        (SCRATCH / "p0-summary.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"port": SLOT_PORT, "health_ok": health.get("ok"), "runs": len(results)}, indent=2))
    finally:
        stop_server(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())