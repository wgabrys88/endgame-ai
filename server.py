"""
endgame-ai node server — stdlib only, zero pip install.
Each topology node = one POST endpoint. Browser drives the graph.
State lives in the browser; Python is stateless per-call.
"""
import json, http.server, urllib.request, pathlib, time, os, sys, re

ROOT = pathlib.Path(__file__).parent
PROMPTS = ROOT / "prompts"
WIRING = json.loads((PROMPTS / "wiring.json").read_text(encoding="utf-8"))
MODEL = json.loads((PROMPTS / "model.json").read_text(encoding="utf-8"))

# ─── Desktop (optional import) ───
try:
    from actions import execute_verb, observe_screen
except ImportError:
    def observe_screen(): return "(desktop module not available)"
    def execute_verb(verb, target, value=""): return f"[stub] {verb} {target} {value}"

# ─── Node handlers: pure functions (input→output+signals) ───

def node_gate(state, config):
    """Check response_limit gate."""
    limit = state.get("response_limit", 0)
    count = state.get("response_count", 0)
    if limit > 0 and count >= limit:
        return {"signals": ["limit_reached"], "state_patch": {}}
    return {"signals": ["under_limit"], "state_patch": {}}


def node_route_slot(state, config):
    """Always passes through (single slot)."""
    return {"signals": ["route_open"], "state_patch": {}}


def node_observe_screen(state, config):
    """Capture desktop UI tree."""
    if state.get("no_desktop"):
        screen = WIRING.get("context", {}).get("screen_disabled", "(no desktop)")
    else:
        screen = observe_screen()
    return {"signals": ["screen_ready"], "state_patch": {"screen": screen}, "data": {"screen": screen}}


def node_build_request(state, config):
    """Assemble LLM request from prompt files + state."""
    circuit = state.get("circuit", "unified")
    req_cfg = WIRING.get("request", {}).get(circuit, {})

    # System prompt
    sys_cfg = req_cfg.get("system", {})
    prompt_file = sys_cfg.get("file", "unified.txt")
    # Check prompt_swap
    swap_ref = sys_cfg.get("swap_ref", "")
    if swap_ref:
        swaps = _resolve_ref(WIRING, swap_ref) or []
        goal = state.get("goal", "")
        for swap in swaps:
            if any(kw.lower() in goal.lower() for kw in swap.get("when", [])):
                prompt_file = swap["prompt"]
                break
    system = (PROMPTS / prompt_file).read_text(encoding="utf-8")

    # User blocks
    blocks_cfg = req_cfg.get("user", {}).get("blocks", [])
    sep = req_cfg.get("user", {}).get("separator", "\n")
    parts = []
    for b in blocks_cfg:
        src = b.get("source", "")
        val = _resolve_ref(state, src.replace("state.", "")) if src.startswith("state.") else ""
        if not val and b.get("empty_template"):
            val = b["empty_template"]
        if not val and not b.get("always"):
            continue
        label = b.get("label", "")
        parts.append(f"{label}: {val}" if label else str(val))
    # Workspace line
    parts.append(f"ROOT: {ROOT}")
    parts.append(f"PROMPTS: {PROMPTS}")
    parts.append(f"WIRING: {PROMPTS / 'wiring.json'}")
    user = sep.join(parts)

    return {"signals": ["request_built"], "state_patch": {"last_request": {"system": system, "user": user}}, "data": {"system": system, "user": user}}


def node_llm_call(state, config):
    """Call LM Studio or compatible OpenAI endpoint."""
    req = state.get("last_request", {})
    t0 = time.time()
    body = {
        "model": MODEL.get("model", "local-model"),
        "messages": [
            {"role": "system", "content": req.get("system", "")},
            {"role": "user", "content": req.get("user", "")}
        ],
        "temperature": MODEL.get("temperature", 0.3),
        "max_tokens": MODEL.get("max_tokens", 2048),
    }
    url = MODEL.get("base_url", "http://localhost:1234") + "/v1/chat/completions"
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}),
            timeout=120
        )
        resp = json.loads(r.read())
        choice = resp["choices"][0]["message"]
        content = choice.get("content", "")
        reasoning = choice.get("reasoning_content", "")
        dur = f"{time.time()-t0:.1f}s"
        return {
            "signals": ["response_received"],
            "state_patch": {"last_content": content, "last_reasoning": reasoning, "response_count": state.get("response_count", 0) + 1},
            "data": {"content": content, "reasoning": reasoning, "duration": dur}
        }
    except Exception as e:
        return {"signals": ["response_received"], "state_patch": {"last_content": "", "last_error": str(e)}, "data": {"error": str(e)}}


def node_parse_response(state, config):
    """Parse JSON response, apply guards, emit signals."""
    content = state.get("last_content", "")
    reasoning = state.get("last_reasoning", "")
    # Try parse from content or reasoning
    parsed = None
    for src in [content, reasoning]:
        m = re.search(r'\{.*\}', src, re.DOTALL)
        if m:
            try: parsed = json.loads(m.group()); break
            except: pass
    if not parsed:
        return {
            "signals": ["unified_error"],
            "state_patch": {"last_error": "parse_failed: respond with JSON only"},
            "data": {"error": "parse_failed"}
        }
    conclusion = parsed.get("data", {}).get("conclusion", "")
    actions = parsed.get("data", {}).get("actions", [])

    if conclusion == "DONE":
        return {"signals": ["goal_complete", "limit_reached"], "state_patch": {"outcome": "goal complete"}, "data": {"conclusion": "DONE"}}
    elif conclusion == "CANNOT":
        return {"signals": ["unified_cannot"], "state_patch": {"outcome": "cannot"}, "data": {"conclusion": "CANNOT"}}
    elif conclusion == "EXECUTE":
        return {"signals": ["actions_present"], "state_patch": {"pending_actions": actions}, "data": {"conclusion": "EXECUTE", "actions": actions}}
    else:
        return {"signals": ["unified_error"], "state_patch": {"last_error": f"unknown conclusion: {conclusion}"}, "data": {"conclusion": conclusion}}


def node_desktop_exec(state, config):
    """Execute pending desktop actions."""
    actions = state.get("pending_actions", [])
    results = []
    for a in actions:
        r = execute_verb(a.get("verb", ""), a.get("target", ""), a.get("value", ""))
        results.append({"action": a, "result": r})
    return {"signals": ["cycle_done"], "state_patch": {"last_exec_results": results, "pending_actions": []}, "data": {"results": results}}


def node_feedback(state, config):
    """Append reasoning to history."""
    reasoning = state.get("last_reasoning", "")
    outcome = state.get("outcome", "")
    history = list(state.get("reasoning_history", []))
    depth = WIRING.get("limits", {}).get("reasoning_history_depth", 20)
    entry = f"[attempt] {reasoning} → {outcome}"
    history.append(entry)
    if len(history) > depth:
        history = history[-depth:]
    return {"signals": ["cycle_done"], "state_patch": {"reasoning_history": history, "last_reasoning_display": entry}, "data": {"entry": entry}}


def node_audit_log(state, config):
    """Log action to bus (noop in minimal server)."""
    return {"signals": [], "state_patch": {}, "data": {"logged": True}}


def node_idle(state, config):
    """Terminal node."""
    return {"signals": ["idle"], "state_patch": {}, "data": {"stopped": True}}


# ─── Helpers ───
def _resolve_ref(obj, path):
    parts = path.split(".")
    for p in parts:
        if isinstance(obj, dict): obj = obj.get(p)
        else: return None
    return obj

# ─── Node registry ───
NODES = {
    "gate": node_gate,
    "bus_route": node_route_slot,
    "desktop_observe": node_observe_screen,
    "request_assembly": node_build_request,
    "llm": node_llm_call,
    "response_pipeline": node_parse_response,
    "desktop_execute": node_desktop_exec,
    "feedback": node_feedback,
    "audit_log": node_audit_log,
    "idle": node_idle,
    "entry": lambda s, c: {"signals": ["args_parsed"], "state_patch": {}, "data": {}},
}

# ─── HTTP Server ───
class Handler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._json({"ok": True, "nodes": list(NODES.keys())})
        elif self.path == "/wiring":
            self._json(WIRING)
        elif self.path in ("/", "/index.html", "/editor"):
            self._serve_file(ROOT / "wiring-editor.html", "text/html")
        else:
            self.send_error(404)

    def _serve_file(self, path, mime):
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/node/"):
            node_type = self.path[6:]
            handler = NODES.get(node_type)
            if not handler:
                self._json({"error": f"unknown node type: {node_type}"}, 404)
                return
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            state = body.get("state", {})
            config = body.get("config", {})
            try:
                result = handler(state, config)
                self._json(result)
            except Exception as e:
                self._json({"error": str(e), "signals": ["error"]}, 500)
        else:
            self.send_error(404)

    def _json(self, data, code=200):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[node-server] {fmt % args}\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9077
    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print(f"endgame-ai node server on http://127.0.0.1:{port}")
    print(f"  Nodes: {', '.join(NODES.keys())}")
    print(f"  Wiring: {PROMPTS / 'wiring.json'}")
    srv.serve_forever()
