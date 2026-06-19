"""
endgame-ai — stdlib only, zero pip.
One file. Node handlers are pure functions. Wiring.json is the brain.
"""
import json, http.server, urllib.request, pathlib, time, sys, re, threading, queue

ROOT = pathlib.Path(__file__).parent
PROMPTS = ROOT / "prompts"
WIRING = json.loads((PROMPTS / "wiring.json").read_text(encoding="utf-8"))
MODEL = json.loads((PROMPTS / "model.json").read_text(encoding="utf-8"))

try:
    from actions import execute_verb, observe_screen
except Exception:
    def observe_screen(): return "(desktop not available)"
    def execute_verb(verb, target, value=""): return f"[stub] {verb} {target} {value}"

# ─── SSE ───
SSE = []

def sse_push(evt, data):
    msg = f"event: {evt}\ndata: {json.dumps(data)}\n\n"
    for q in list(SSE):
        try: q.put_nowait(msg)
        except: SSE.remove(q)

# ─── LLM ───

def llm(system, user):
    body = {
        "model": MODEL.get("model", "local-model"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": MODEL.get("temperature", 0.3),
        "max_tokens": MODEL.get("max_tokens", 16384),
    }
    url = MODEL["host"] + "/v1/chat/completions"
    t0 = time.time()
    r = urllib.request.urlopen(
        urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}),
        timeout=MODEL.get("timeout", 120)
    )
    c = json.loads(r.read())["choices"][0]["message"]
    return c.get("content", ""), c.get("reasoning_content", ""), time.time() - t0

def extract_json(text):
    m = re.search(r'\{.*\}', text or "", re.DOTALL)
    if m:
        try: return json.loads(m.group())
        except: pass
    return None

# ─── Node handlers ───

def node_entry(state, _):
    return {"signals": ["ready"], "patch": {}}

def node_planner(state, _):
    goal = state.get("goal", "")
    screen = state.get("screen", "")
    prompt = (PROMPTS / "planner.txt").read_text(encoding="utf-8")
    try:
        content, _, _ = llm(prompt, f"GOAL: {goal}\nSCREEN: {screen[:3000]}")
        parsed = extract_json(content)
        steps = parsed["data"]["steps"] if parsed and "data" in parsed and "steps" in parsed.get("data", {}) else [{"description": goal, "done_when": "goal achieved"}]
    except Exception as e:
        steps = [{"description": goal, "done_when": "goal achieved"}]
    return {"signals": ["plan_ready"], "patch": {"plan": steps, "step": 0, "retries": 0}}

def node_scheduler(state, _):
    steps = state.get("plan", [])
    idx = state.get("step", 0)
    if idx >= len(steps):
        return {"signals": ["plan_complete"], "patch": {}}
    return {"signals": ["step_ready"], "patch": {"current_step": steps[idx], "step_goal": steps[idx]["description"]}}

def node_observe(state, _):
    if state.get("no_desktop"):
        s = WIRING.get("context", {}).get("screen_disabled", "(no desktop)")
    else:
        s = observe_screen()
    return {"signals": ["screen_ready"], "patch": {"screen": s}}

def node_act(state, _):
    """Build prompt, call LLM, parse, execute actions. One node does the full act cycle."""
    # Build prompt
    prompt_file = WIRING.get("request", {}).get("unified", {}).get("system", {}).get("file", "unified.txt")
    # Check prompt swap
    swaps = WIRING.get("circuits", {}).get("unified", {}).get("prompt_swap", [])
    goal = state.get("goal", "")
    for sw in swaps:
        if any(k.lower() in goal.lower() for k in sw.get("when", [])):
            prompt_file = sw["prompt"]
            break
    system = (PROMPTS / prompt_file).read_text(encoding="utf-8")
    step_goal = state.get("step_goal", goal)
    screen = state.get("screen", "(no screen)")
    error = state.get("last_error", "")
    user = f"GOAL: {step_goal}\nSCREEN: {screen[:4000]}"
    if error:
        user += f"\nLAST ERROR: {error}"

    # Call LLM
    try:
        content, reasoning, dur = llm(system, user)
    except Exception as e:
        return {"signals": ["act_failed"], "patch": {"last_error": str(e)}}

    # Parse
    parsed = extract_json(content) or extract_json(reasoning)
    if not parsed:
        return {"signals": ["act_failed"], "patch": {"last_error": "LLM returned no JSON"}}

    conclusion = parsed.get("data", {}).get("conclusion", "")
    actions = parsed.get("data", {}).get("actions", [])

    if conclusion == "DONE":
        return {"signals": ["step_done"], "patch": {}}
    if conclusion == "CANNOT":
        return {"signals": ["act_failed"], "patch": {"last_error": "LLM says CANNOT"}}
    if conclusion != "EXECUTE" or not actions:
        return {"signals": ["act_failed"], "patch": {"last_error": f"bad conclusion: {conclusion}"}}

    # Execute
    results = []
    for a in actions:
        r = execute_verb(a.get("verb", ""), a.get("target", ""), a.get("value", ""))
        results.append(f"{a.get('verb')} {a.get('target')}: {r}")
    return {"signals": ["acted"], "patch": {"last_actions": results, "last_error": ""}}

def node_verify(state, _):
    """Fresh observe + LLM verification in one node."""
    # Fresh screen
    if not state.get("no_desktop"):
        screen = observe_screen()
    else:
        screen = state.get("screen", "(no desktop)")

    step = state.get("current_step", {})
    actions = state.get("last_actions", [])
    prompt = (PROMPTS / "verifier.txt").read_text(encoding="utf-8")
    user = f"STEP: {step.get('description','')}\nDONE_WHEN: {step.get('done_when','')}\nSCREEN: {screen[:3000]}\nLAST_ACTIONS: {json.dumps(actions)[:500]}"
    try:
        content, _, _ = llm(prompt, user)
        parsed = extract_json(content)
        if parsed and parsed.get("data", {}).get("confirmed"):
            return {"signals": ["step_confirmed"], "patch": {"step": state.get("step", 0) + 1, "retries": 0, "screen": screen}}
        reason = parsed.get("data", {}).get("reason", "unconfirmed") if parsed else "verify parse failed"
        return {"signals": ["step_denied"], "patch": {"last_error": reason, "screen": screen}}
    except Exception as e:
        return {"signals": ["step_denied"], "patch": {"last_error": str(e), "screen": screen}}

def node_reflect(state, _):
    """Decide retry vs replan. If retries exhausted → replan."""
    retries = state.get("retries", 0)
    max_r = WIRING.get("limits", {}).get("max_attempts", 5)
    if retries >= max_r:
        return {"signals": ["replan"], "patch": {"retries": 0}}

    step = state.get("current_step", {})
    screen = state.get("screen", "")
    error = state.get("last_error", "")
    prompt = (PROMPTS / "reflector.txt").read_text(encoding="utf-8")
    user = f"STEP: {step.get('description','')}\nDONE_WHEN: {step.get('done_when','')}\nSCREEN: {screen[:3000]}\nDENIAL_REASON: {error}"
    try:
        content, _, _ = llm(prompt, user)
        parsed = extract_json(content)
        if parsed and parsed.get("data", {}).get("should_replan"):
            return {"signals": ["replan"], "patch": {"retries": 0}}
        suggestion = parsed.get("data", {}).get("suggestion", "") if parsed else ""
        return {"signals": ["retry"], "patch": {"retries": retries + 1, "last_error": suggestion or error}}
    except Exception as e:
        return {"signals": ["retry"], "patch": {"retries": retries + 1}}

def node_satisfied(state, _):
    return {"signals": ["idle"], "patch": {"satisfied": True}}

# ─── Bus (Phase 4) — 3 functions, 1 file ───

BUS_FILE = ROOT / "bus.json"

def _bus_read():
    if BUS_FILE.exists():
        try: return json.loads(BUS_FILE.read_text(encoding="utf-8"))
        except: pass
    return []

def _bus_write(msgs):
    limit = WIRING.get("limits", {}).get("bus_max", 200)
    BUS_FILE.write_text(json.dumps(msgs[-limit:], indent=1), encoding="utf-8")

def node_bus_post(state, _):
    """Post a message to the shared bus."""
    msg = {
        "ts": time.time(),
        "from_slot": WIRING.get("instance", {}).get("slot", 0),
        "type": state.get("bus_msg_type", "telemetry"),
        "payload": state.get("bus_payload", {})
    }
    msgs = _bus_read()
    msgs.append(msg)
    _bus_write(msgs)
    return {"signals": ["posted"], "patch": {}}

def node_bus_check(state, _):
    """Check bus for messages addressed to this slot."""
    slot = WIRING.get("instance", {}).get("slot", 0)
    since = state.get("bus_last_check", 0)
    msgs = _bus_read()
    relevant = [m for m in msgs if m.get("to_slot") in (slot, None, "all") and m.get("ts", 0) > since]
    if relevant:
        newest = relevant[-1]
        return {"signals": ["bus_message"], "patch": {"bus_last_check": time.time(), "bus_incoming": newest}}
    return {"signals": ["no_message"], "patch": {"bus_last_check": time.time()}}

# ─── Registry ───
NODES = {
    "entry": node_entry,
    "planner": node_planner,
    "scheduler": node_scheduler,
    "observe": node_observe,
    "act": node_act,
    "verify": node_verify,
    "reflect": node_reflect,
    "satisfied": node_satisfied,
    "bus_post": node_bus_post,
    "bus_check": node_bus_check,
}

# ─── Graph engine ───

def find_targets(node_id, signals, topo):
    targets = []
    for e in topo.get("edges", []):
        if e["from"] != node_id:
            continue
        if any(s in e["on"].split("|") for s in signals):
            targets.append(e["to"])
    return targets

def run(goal):
    topo = WIRING["topology"]
    state = {"goal": goal, "step": 0, "retries": 0, "no_desktop": False}
    node_id = topo["cycle_start"]
    cycle = 0

    print(f"\n{'='*50}\n  ROD: {goal}\n{'='*50}\n")

    while cycle < 300:
        cycle += 1
        node_cfg = next((n for n in topo["nodes"] if n["id"] == node_id), None)
        if not node_cfg:
            print(f"[{cycle}] dead end: no node '{node_id}'")
            break

        handler = NODES.get(node_cfg["type"])
        if not handler:
            print(f"[{cycle}] no handler for type '{node_cfg['type']}'")
            break

        print(f"[{cycle}] {node_id}")
        sse_push("node", {"c": cycle, "id": node_id})

        result = handler(state, node_cfg)
        state.update(result.get("patch", {}))
        signals = result.get("signals", [])
        print(f"       → {signals}")

        sse_push("result", {"c": cycle, "id": node_id, "s": signals})

        targets = find_targets(node_id, signals, topo)
        if not targets:
            print(f"\n[{cycle}] terminal — no outgoing edge for {signals}")
            break
        node_id = targets[0]
        time.sleep(0.3)

    print(f"\nDone. State: step={state.get('step')} satisfied={state.get('satisfied')}")
    sse_push("stop", {"outcome": state.get("satisfied", False)})
    return state

# ─── HTTP ───

class H(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._j({"ok": True, "nodes": list(NODES.keys())})
        elif self.path == "/wiring":
            self._j(WIRING)
        elif self.path == "/bus":
            self._j(_bus_read())
        elif self.path in ("/", "/index.html"):
            d = (ROOT / "wiring-editor.html").read_bytes()
            self.send_response(200); self.send_header("Content-Type","text/html"); self.send_header("Content-Length",len(d)); self.end_headers(); self.wfile.write(d)
        elif self.path == "/events":
            self.send_response(200); self._cors()
            self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.end_headers()
            q = queue.Queue(); SSE.append(q)
            try:
                while True:
                    self.wfile.write(q.get(timeout=30).encode()); self.wfile.flush()
            except: pass
            finally:
                if q in SSE: SSE.remove(q)
        else:
            self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))) if int(self.headers.get("Content-Length", 0) or 0) > 0 else {}
        if self.path.startswith("/node/"):
            t = self.path[6:]
            h = NODES.get(t)
            if not h: self._j({"error": f"unknown: {t}"}, 404); return
            try: self._j(h(body.get("state", {}), body.get("config", {})))
            except Exception as e: self._j({"error": str(e)}, 500)
        elif self.path == "/run":
            goal = body.get("goal", "")
            if not goal: self._j({"error": "no goal"}, 400); return
            threading.Thread(target=run, args=(goal,), daemon=True).start()
            self._j({"started": True})
        elif self.path == "/bus/post":
            msgs = _bus_read(); msgs.append(body); _bus_write(msgs)
            self._j({"ok": True})
        else:
            self.send_error(404)

    def _j(self, d, code=200):
        self.send_response(code); self._cors(); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(d).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")

    def log_message(self, *a): pass

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--run" in args:
        goal = " ".join(args[args.index("--run")+1:])
        if not goal: print("Usage: python server.py --run \"goal\""); sys.exit(1)
        srv = http.server.HTTPServer(("127.0.0.1", 9077), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"SSE: http://127.0.0.1:9077/events")
        run(goal)
    else:
        port = int(args[0]) if args and args[0].isdigit() else 9077
        srv = http.server.HTTPServer(("127.0.0.1", port), H)
        print(f"endgame-ai on http://127.0.0.1:{port}  nodes: {list(NODES.keys())}")
        srv.serve_forever()
