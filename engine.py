"""Exec-based graph engine for endgame-ai."""
from __future__ import annotations

import http.server
import json
import os
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from typing import Any

import runtime

ROOT = pathlib.Path(__file__).parent.resolve()
RUN_LOCK = threading.RLock()
RUN_THREAD: threading.Thread | None = None
RUN_STATE = {"running": False, "paused": False, "stop": False, "last_error": "", "started_at": None, "finished_at": None}

class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def read_body(handler: http.server.BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    ctype = handler.headers.get("Content-Type", "")
    if "application/json" in ctype:
        try:
            return json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return {"_raw": raw}
    parsed = urllib.parse.parse_qs(raw)
    return {k: v[-1] if len(v) == 1 else v for k, v in parsed.items()}


def send(handler: http.server.BaseHTTPRequestHandler, status: int, data: Any, ctype: str = "application/json") -> None:
    body = data if isinstance(data, bytes) else json_bytes(data)
    handler.send_response(status)
    handler.send_header("Content-Type", ctype + ("; charset=utf-8" if "charset" not in ctype else ""))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def run_status_snapshot() -> dict[str, Any]:
    with RUN_LOCK:
        return dict(RUN_STATE)


def build_namespace(state: dict[str, Any], config: dict[str, Any], wiring: dict[str, Any]) -> dict[str, Any]:
    ns = {
        "state": state,
        "config": config,
        "wiring": wiring,
        "signals": [],
        "patch": {},
        "time": time,
        "json": json,
        "re": re,
        "pathlib": pathlib,
        "os": os,
        "runtime": runtime,
    }
    for name in [
        "llm", "observe_screen", "last_observation_snapshot", "get_focused_title", "execute_verb",
        "evaluate_rules", "load_system_prompt", "build_user_message", "call_node", "save_state",
        "load_state", "load_wiring", "save_wiring", "wiring_limit", "wiring_error", "fresh_state",
        "normalize_actions_from_wiring", "apply_memory_action", "write_llm_request", "wait_llm_response",
        "bus_read", "bus_write", "append_trace", "recent_traces", "preview_text",
        "apply_wiring_patch", "validate_wiring", "atomic_write_json", "atomic_write_text",
        "copy_codebase_to_clipboard", "collect_codebase_text", "scaffold_node_file",
    ]:
        ns[name] = getattr(runtime, name)
    return ns


def exec_node(node_cfg: dict[str, Any], state: dict[str, Any], wiring: dict[str, Any]) -> dict[str, Any]:
    node_type = node_cfg.get("type")
    path = runtime.NODES_DIR / f"{node_type}.py"
    if not path.exists():
        raise FileNotFoundError(f"node script not found: {path}")
    code = path.read_text(encoding="utf-8")
    ns = build_namespace(state, node_cfg, wiring)
    exec(compile(code, str(path), "exec"), ns, ns)
    signals = ns.get("signals", [])
    patch = ns.get("patch", {})
    if isinstance(signals, str):
        signals = [signals]
    if not isinstance(signals, list):
        signals = [str(signals)]
    if not isinstance(patch, dict):
        patch = {"node_patch_value": patch}
    result = ns.get("result") if isinstance(ns.get("result"), dict) else {}
    return {**result, "signals": signals, "patch": patch}


def step_once(goal: str = "", state: dict[str, Any] | None = None, node_id: str | None = None) -> dict[str, Any]:
    wiring = runtime.load_wiring()  # fresh each cycle
    topo = wiring.get("topology", {})
    state = dict(state if state is not None else (runtime.load_state() or {}))
    if not state:
        if not goal:
            raise ValueError("goal required when state is empty")
        state = runtime.fresh_state(goal, wiring)
    if goal and not state.get("goal"):
        state["goal"] = goal
    node_id = node_id or state.pop("_resume_node", None) or topo.get("cycle_start")
    state.pop("_paused", None)
    node_cfg = runtime.topo_node_by_id(node_id, wiring)
    if not node_cfg:
        raise ValueError(f"dead end: no node '{node_id}'")
    before_debug = runtime.node_debug_context(node_id, state, wiring)
    runtime.remember_state(state)
    runtime.sse_push("node", {"c": state.get("_cycle", 0) + 1, "id": node_id, "type": node_cfg.get("type")})
    try:
        result = exec_node(node_cfg, state, wiring)
    except Exception as e:
        result = {"signals": ["error"], "patch": {"last_error": f"{type(e).__name__}: {e}", "exception": runtime.format_exception(e)}}
    patch = result.get("patch", {}) or {}
    state.update(patch)
    signals = result.get("signals", []) or []
    targets = runtime.find_targets(node_id, signals, topo)
    next_node = targets[0] if targets else None
    terminal = (not next_node) or ("idle" in signals)
    state["_cycle"] = state.get("_cycle", 0) + 1
    state["_resume_node"] = node_id if terminal else next_node
    runtime.save_state(state)
    runtime.sse_push("result", {"c": state["_cycle"], "id": node_id, "signals": signals, "patch_keys": sorted(patch.keys())[:40]})
    if terminal:
        runtime.sse_push("stop", {"outcome": state.get("satisfied", False), "node": node_id})
    next_debug = runtime.node_debug_context(next_node, state, wiring) if next_node else None
    return {
        "node": node_id,
        "type": node_cfg.get("type"),
        "executed": {"id": node_id, "type": node_cfg.get("type"), "label": node_cfg.get("label", ""), "circuit": before_debug.get("circuit", "")},
        "signals": signals,
        "state_patch": patch,
        "state": state,
        "targets": targets,
        "next": None if terminal else next_node,
        "next_node": next_debug,
        "transition": {"from": node_id, "signals": signals, "targets": targets, "next": None if terminal else next_node, "terminal": terminal},
        "debug": {"before": before_debug, "after": next_debug, "run": run_status_snapshot()},
        "terminal": terminal,
        "satisfied": state.get("satisfied", False),
    }


def run_loop(goal: str, resume_state: dict[str, Any] | None = None, max_cycles: int | None = None) -> dict[str, Any]:
    wiring = runtime.load_wiring()
    state = dict(resume_state or runtime.fresh_state(goal, wiring))
    node_id = state.pop("_resume_node", None) or wiring.get("topology", {}).get("cycle_start")
    max_cycles = max_cycles if max_cycles is not None else runtime.wiring_limit("max_cycles", 300, wiring)
    with RUN_LOCK:
        RUN_STATE.update({"running": True, "paused": False, "stop": False, "last_error": "", "started_at": time.time(), "finished_at": None})
    runtime.sse_push("run_start", {"goal": goal})
    cycle = 0
    try:
        while cycle < max_cycles:
            with RUN_LOCK:
                if RUN_STATE.get("stop"):
                    break
                if RUN_STATE.get("paused"):
                    state["_paused"] = True
                    state["_resume_node"] = node_id
                    runtime.save_state(state)
                    runtime.sse_push("pause", {"node": node_id})
                    return state
            res = step_once(goal="", state=state, node_id=node_id)
            state = res["state"]
            cycle += 1
            if res.get("terminal"):
                break
            node_id = res.get("next") or state.get("_resume_node")
            wiring = runtime.load_wiring()
            delay = int(wiring.get("runtime", {}).get("cycle_delay_ms", 300)) / 1000.0
            time.sleep(delay)
        return state
    except Exception as e:
        with RUN_LOCK:
            RUN_STATE["last_error"] = f"{type(e).__name__}: {e}"
        runtime.sse_push("error", {"error": RUN_STATE["last_error"]})
        raise
    finally:
        with RUN_LOCK:
            RUN_STATE["running"] = False
            RUN_STATE["finished_at"] = time.time()
        runtime.sse_push("run_end", {"satisfied": state.get("satisfied", False)})


def start_run(goal: str, resume: bool = False) -> dict[str, Any]:
    global RUN_THREAD
    with RUN_LOCK:
        if RUN_STATE.get("running"):
            return {"ok": False, "error": "run already active", "run": run_status_snapshot()}
        resume_state = runtime.load_state() if resume else None
        RUN_THREAD = threading.Thread(target=run_loop, args=(goal, resume_state), daemon=True)
        RUN_THREAD.start()
    return {"ok": True, "run": run_status_snapshot()}


def inspect_state(goal: str = "", node_id: str | None = None) -> dict[str, Any]:
    wiring = runtime.load_wiring()
    state = runtime.load_state() or {}
    if goal and not state.get("goal"):
        state["goal"] = goal
    node_id = node_id or state.get("_resume_node") or wiring.get("topology", {}).get("cycle_start")
    return {"node": node_id, "state": state, "debug": runtime.node_debug_context(node_id, state, wiring), "wiring": runtime.wiring_summary(wiring), "run": run_status_snapshot()}


def create_node(payload: dict[str, Any]) -> dict[str, Any]:
    node_type = payload.get("type") or payload.get("node_type") or payload.get("id")
    path = runtime.scaffold_node_file(str(node_type), payload.get("code"), overwrite=bool(payload.get("overwrite")))
    wiring = runtime.load_wiring()
    topo = wiring.setdefault("topology", {})
    node_id = payload.get("id") or str(node_type)
    nodes = topo.setdefault("nodes", [])
    if not any(n.get("id") == node_id for n in nodes):
        nodes.append({"id": node_id, "type": str(node_type), "label": payload.get("label") or node_id})
    if payload.get("edge_from"):
        topo.setdefault("edges", []).append({"from": payload["edge_from"], "to": node_id, "on": payload.get("on") or "ready"})
    if payload.get("edge_to"):
        topo.setdefault("edges", []).append({"from": node_id, "to": payload["edge_to"], "on": payload.get("edge_to_on") or "done"})
    errs = runtime.validate_wiring(wiring)
    if errs:
        return {"ok": False, "errors": errs, "path": str(path)}
    runtime.save_wiring(wiring)
    runtime.sse_push("node_created", {"type": str(node_type), "path": str(path), "id": node_id})
    return {"ok": True, "type": str(node_type), "id": node_id, "path": str(path), "wiring": runtime.wiring_summary(wiring)}


def spawn_slot(slot: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["ENDGAME_SLOT"] = str(slot)
    env["ENDGAME_STATE"] = str(ROOT / f"state.slot{slot}.json")
    if slot == 2 and (runtime.PROMPTS / "wiring_relay.json").exists():
        env["ENDGAME_WIRING"] = str(runtime.PROMPTS / "wiring_relay.json")
    return subprocess.Popen([sys.executable, str(ROOT / "engine.py")], cwd=str(ROOT), env=env)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "endgame-ai-engine/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        send(self, 204, b"", "text/plain")

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            if path in {"/", "/editor"}:
                html = (ROOT / "wiring-editor.html").read_bytes()
                send(self, 200, html, "text/html")
            elif path == "/health":
                wiring = runtime.load_wiring()
                send(self, 200, {"ok": True, "port": runtime.http_port(wiring), "wiring": runtime.wiring_summary(wiring), "run": run_status_snapshot()})
            elif path == "/wiring":
                send(self, 200, runtime.load_wiring())
            elif path == "/state":
                send(self, 200, runtime.load_state())
            elif path == "/inspect":
                send(self, 200, inspect_state(query.get("goal", [""])[0], query.get("node", [None])[0]))
            elif path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        item = runtime.EVENTS.get(timeout=15)
                        data = json.dumps(item, ensure_ascii=False)
                        self.wfile.write(f"event: {item.get('type','message')}\n".encode())
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                        break
            elif path == "/node/types":
                send(self, 200, {"types": runtime.available_node_types()})
            elif path.startswith("/node/"):
                node_type = path.split("/", 2)[2].replace(".py", "")
                f = runtime.NODES_DIR / f"{node_type}.py"
                if not f.exists():
                    send(self, 404, {"error": "not found"})
                else:
                    send(self, 200, {"type": node_type, "code": f.read_text(encoding="utf-8")})
            elif path == "/bus":
                send(self, 200, runtime.bus_read())
            elif path == "/system":
                send(self, 200, {"root": str(ROOT), "python": sys.version, "model": runtime.load_model(), "wiring_path": str(runtime.WIRING_PATH), "state_file": str(runtime.STATE_FILE)})
            elif path == "/codebase":
                text, manifest = runtime.collect_codebase_text()
                if query.get("format", [""])[0] == "text":
                    send(self, 200, text.encode("utf-8"), "text/plain")
                else:
                    send(self, 200, manifest)
            elif path == "/slots":
                send(self, 200, {"slots": [{"slot": 1, "port": runtime.http_port(slot=1)}, {"slot": 2, "port": runtime.http_port(slot=2)}]})
            else:
                send(self, 404, {"error": "not found", "path": path})
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            pass
        except Exception as e:
            try:
                send(self, 500, {"error": f"{type(e).__name__}: {e}"})
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                pass

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        body = read_body(self)
        try:
            if path == "/wiring":
                errs = runtime.validate_wiring(body)
                if errs:
                    send(self, 400, {"ok": False, "errors": errs})
                else:
                    runtime.save_wiring(body)
                    runtime.sse_push("wiring_saved", runtime.wiring_summary(body))
                    send(self, 200, {"ok": True, "wiring": runtime.wiring_summary(body)})
            elif path == "/state":
                runtime.save_state(body)
                send(self, 200, {"ok": True})
            elif path == "/run":
                goal = str(body.get("goal") or "")
                send(self, 200, start_run(goal, resume=bool(body.get("resume"))))
            elif path == "/step":
                goal = str(body.get("goal") or "")
                state = body.get("state") if isinstance(body.get("state"), dict) else None
                node_id = body.get("node") or body.get("node_id")
                send(self, 200, step_once(goal=goal, state=state, node_id=node_id))
            elif path == "/pause":
                with RUN_LOCK:
                    RUN_STATE["paused"] = True
                send(self, 200, {"ok": True, "run": run_status_snapshot()})
            elif path == "/resume":
                with RUN_LOCK:
                    RUN_STATE["paused"] = False
                state = runtime.load_state()
                goal = str(body.get("goal") or state.get("goal") or "")
                send(self, 200, start_run(goal, resume=True))
            elif path == "/stop":
                with RUN_LOCK:
                    RUN_STATE["stop"] = True
                send(self, 200, {"ok": True, "run": run_status_snapshot()})
            elif path == "/node/create":
                send(self, 200, create_node(body))
            elif path.startswith("/node/"):
                node_type = path.split("/", 2)[2].replace(".py", "")
                code = str(body.get("code") or "")
                if not code:
                    send(self, 400, {"ok": False, "error": "code required"})
                else:
                    p = runtime.scaffold_node_file(node_type, code, overwrite=True)
                    send(self, 200, {"ok": True, "path": str(p)})
            elif path == "/clipboard/codebase":
                ok, info = runtime.copy_codebase_to_clipboard()
                send(self, 200, {"ok": ok, **info})
            elif path == "/bus":
                runtime.bus_write(body)
                send(self, 200, {"ok": True})
            else:
                send(self, 404, {"error": "not found", "path": path})
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            pass
        except Exception as e:
            try:
                send(self, 500, {"error": f"{type(e).__name__}: {e}"})
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                pass


def ensure_files() -> None:
    runtime.PROMPTS.mkdir(exist_ok=True)
    runtime.NODES_DIR.mkdir(exist_ok=True)
    if not runtime.WIRING_PATH.exists():
        runtime.save_wiring(runtime.default_wiring())
    if not runtime.MODEL_PATH.exists():
        runtime.save_model(runtime.default_model())


def main() -> None:
    if sys.platform != "win32":
        sys.exit("ERROR: engine.py requires native Windows Python (desktop.py needs ctypes.WinDLL). Do not run from WSL.")
    ensure_files()
    wiring = runtime.load_wiring()
    bind = wiring.get("runtime", {}).get("http_bind", "0.0.0.0")
    port = runtime.http_port(wiring)
    server = ThreadingHTTPServer((bind, port), Handler)
    print(f"endgame-ai engine serving http://127.0.0.1:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
