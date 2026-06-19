"""
endgame-ai — stdlib only, zero pip.
One file. Node handlers are pure functions. Wiring.json is the brain.
"""
import json, http.server, urllib.request, pathlib, time, sys, re, threading, queue

ROOT = pathlib.Path(__file__).parent
PROMPTS = ROOT / "prompts"
STATE_FILE = ROOT / "state.json"
BUS_FILE = ROOT / "bus.json"
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

# ─── State persistence ───

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, default=str), encoding="utf-8")

def load_state():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except: pass
    return None

# ─── Bus ───

def bus_read():
    if BUS_FILE.exists():
        try: return json.loads(BUS_FILE.read_text(encoding="utf-8"))
        except: pass
    return []

def bus_write(msgs):
    BUS_FILE.write_text(json.dumps(msgs[-WIRING.get("limits", {}).get("bus_max", 200):], indent=1), encoding="utf-8")

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

# ─── Guards (from wiring.json, evaluated in act node) ───

def check_repeat_block(state, actions):
    """Block if same actions as last time and last outcome was OK."""
    last = state.get("last_actions_raw", [])
    if not last:
        return None
    if actions == last and "OK" in state.get("last_outcome", ""):
        hint = _find_advance_hint(state, actions)
        return hint or "repeat blocked — try a different action"
    return None

def _find_advance_hint(state, actions):
    """Match advance hints from wiring."""
    hints = WIRING.get("guards", {}).get("advance_hints", [])
    screen = (state.get("screen", "") or "").lower()
    for a in actions:
        verb = a.get("verb", "").lower()
        target = (a.get("target", "") or "").lower()
        for h in hints:
            if h.get("verb", "") != verb:
                continue
            tc = h.get("target_contains", [])
            if tc and not any(t.lower() in target for t in tc):
                continue
            sc = h.get("screen_contains", [])
            if sc and not any(s.lower() in screen for s in sc):
                continue
            return h.get("hint", "")
    default = WIRING.get("guards", {}).get("advance_hints_default", "")
    return default

def check_premature_done(state):
    """Block DONE if goal requires typing but no write was done."""
    goal = (state.get("goal", "") or "").lower()
    needs_write = any(k in goal for k in ["type", "write", "enter text"])
    if not needs_write:
        return None
    history = state.get("history", [])
    wrote = any("write" in h.get("outcome", "").lower() or "typed" in h.get("outcome", "").lower() for h in history)
    if not wrote:
        return "goal requires typing but no write was done yet"
    return None

# ─── Node handlers ───

def node_entry(state, _):
    return {"signals": ["ready"], "patch": {}}

def node_planner(state, _):
    goal = state.get("goal", "")
    screen = state.get("screen", "")
    prompt = (PROMPTS / "planner.txt").read_text(encoding="utf-8")
    # Include persona context if available
    persona = WIRING.get("instance", {}).get("persona", "")
    persona_ctx = ""
    if persona:
        pf = PROMPTS / "personalities" / f"{persona}.txt"
        if pf.exists():
            persona_ctx = f"\nPERSONA: {pf.read_text(encoding='utf-8')[:500]}\n"
    try:
        content, _, _ = llm(prompt, f"{persona_ctx}GOAL: {goal}\nSCREEN: {screen[:3000]}")
        parsed = extract_json(content)
        steps = parsed["data"]["steps"] if parsed and "data" in parsed and "steps" in parsed.get("data", {}) else [{"description": goal, "done_when": "goal achieved"}]
    except Exception:
        steps = [{"description": goal, "done_when": "goal achieved"}]
    return {"signals": ["plan_ready"], "patch": {"plan": steps, "step": 0, "retries": 0, "history": []}}

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
    """Build prompt with feedback history, call LLM, apply guards, execute."""
    # Load system prompt (with persona and swap)
    prompt_file = WIRING.get("request", {}).get("unified", {}).get("system", {}).get("file", "unified.txt")
    swaps = WIRING.get("circuits", {}).get("unified", {}).get("prompt_swap", [])
    goal = state.get("goal", "")
    for sw in swaps:
        if any(k.lower() in goal.lower() for k in sw.get("when", [])):
            prompt_file = sw["prompt"]
            break
    system = (PROMPTS / prompt_file).read_text(encoding="utf-8")

    # Persona injection
    persona = WIRING.get("instance", {}).get("persona", "")
    if persona:
        pf = PROMPTS / "personalities" / f"{persona}.txt"
        if pf.exists():
            system = pf.read_text(encoding="utf-8") + "\n" + system

    # Build user message with feedback history
    step_goal = state.get("step_goal", goal)
    screen = state.get("screen", "(no screen)")
    error = state.get("last_error", "")
    history = state.get("history", [])

    user_parts = [f"GOAL: {step_goal}", f"SCREEN: {screen[:4000]}"]
    if error:
        user_parts.append(f"LAST ERROR: {error}")
    # Inject reasoning history (last N entries)
    depth = WIRING.get("limits", {}).get("history_depth", 10)
    if history:
        recent = history[-depth:]
        reasoning_block = "\n".join(f"  [{h.get('attempt',0)}] {h.get('action','')} → {h.get('outcome','')}" for h in recent)
        user_parts.append(f"HISTORY:\n{reasoning_block}")

    user = "\n".join(user_parts)

    # Call LLM
    try:
        content, reasoning, dur = llm(system, user)
    except Exception as e:
        return {"signals": ["act_failed"], "patch": {"last_error": str(e)}}

    # Parse
    parsed = extract_json(content) or extract_json(reasoning)
    if not parsed:
        return {"signals": ["act_failed"], "patch": {"last_error": "parse_failed: respond with JSON only"}}

    conclusion = parsed.get("data", {}).get("conclusion", "")
    actions = parsed.get("data", {}).get("actions", [])

    # Guard: premature DONE
    if conclusion == "DONE":
        block = check_premature_done(state)
        if block:
            entry = {"attempt": len(history) + 1, "action": "DONE blocked", "outcome": block}
            return {"signals": ["act_failed"], "patch": {"last_error": block, "history": history + [entry]}}
        entry = {"attempt": len(history) + 1, "action": "DONE", "outcome": "goal complete"}
        return {"signals": ["step_done"], "patch": {"history": history + [entry]}}

    if conclusion == "CANNOT":
        entry = {"attempt": len(history) + 1, "action": "CANNOT", "outcome": "LLM cannot proceed"}
        return {"signals": ["act_failed"], "patch": {"last_error": "CANNOT", "history": history + [entry]}}

    if conclusion != "EXECUTE" or not actions:
        return {"signals": ["act_failed"], "patch": {"last_error": f"bad conclusion: {conclusion}"}}

    # Guard: repeat block
    block = check_repeat_block(state, actions)
    if block:
        entry = {"attempt": len(history) + 1, "action": f"{actions[0].get('verb','')} {actions[0].get('target','')}", "outcome": f"BLOCKED: {block}"}
        return {"signals": ["act_failed"], "patch": {"last_error": block, "history": history + [entry]}}

    # Execute
    results = []
    for a in actions:
        r = execute_verb(a.get("verb", ""), a.get("target", ""), a.get("value", ""))
        results.append(f"{a.get('verb')} {a.get('target')}: {r}")

    outcome = "OK: " + "; ".join(results)
    entry = {"attempt": len(history) + 1, "action": f"{actions[0].get('verb','')} {actions[0].get('target','')}", "outcome": outcome}
    return {"signals": ["acted"], "patch": {
        "last_actions": results,
        "last_actions_raw": actions,
        "last_outcome": outcome,
        "last_error": "",
        "history": history + [entry]
    }}

def node_verify(state, _):
    """Fresh observe + LLM verification."""
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
    """Retry vs replan. Retries exhausted → replan."""
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
    except Exception:
        return {"signals": ["retry"], "patch": {"retries": retries + 1}}

def node_satisfied(state, _):
    return {"signals": ["idle"], "patch": {"satisfied": True}}

def node_bus_check(state, _):
    """Poll bus for interrupt goals. Higher-priority goal → interrupt."""
    slot = WIRING.get("instance", {}).get("slot", 0)
    since = state.get("bus_last_check", 0)
    msgs = bus_read()
    # Look for goal messages addressed to this slot
    goals = [m for m in msgs if m.get("to_slot") in (slot, "all") and m.get("ts", 0) > since and m.get("type") == "goal"]
    if goals:
        newest = goals[-1]
        return {"signals": ["interrupt"], "patch": {
            "bus_last_check": time.time(),
            "goal": newest.get("payload", {}).get("goal", state.get("goal", "")),
            "interrupt_from": newest.get("from_slot")
        }}
    return {"signals": ["no_interrupt"], "patch": {"bus_last_check": time.time()}}

def node_bus_post(state, _):
    """Post telemetry/result to bus."""
    msg = {
        "ts": time.time(),
        "from_slot": WIRING.get("instance", {}).get("slot", 0),
        "type": state.get("bus_msg_type", "telemetry"),
        "payload": {"goal": state.get("goal", ""), "step": state.get("step", 0), "satisfied": state.get("satisfied", False)}
    }
    msgs = bus_read()
    msgs.append(msg)
    bus_write(msgs)
    return {"signals": ["posted"], "patch": {}}

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
    "bus_check": node_bus_check,
    "bus_post": node_bus_post,
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

def run(goal, resume_state=None):
    topo = WIRING["topology"]
    if resume_state:
        state = resume_state
        node_id = state.pop("_resume_node", topo["cycle_start"])
    else:
        state = {"goal": goal, "step": 0, "retries": 0, "no_desktop": False, "history": [], "bus_last_check": 0}
        node_id = topo["cycle_start"]
    cycle = 0

    print(f"\n{'='*50}\n  ROD [{WIRING.get('instance',{}).get('slot',0)}]: {goal}\n{'='*50}\n")

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

        # Persist state each cycle
        state["_resume_node"] = node_id
        save_state(state)

        targets = find_targets(node_id, signals, topo)
        if not targets:
            print(f"\n[{cycle}] terminal — no outgoing edge for {signals}")
            break
        node_id = targets[0]
        time.sleep(0.3)

    print(f"\nDone. step={state.get('step')} satisfied={state.get('satisfied')}")
    sse_push("stop", {"outcome": state.get("satisfied", False)})
    return state

# ─── HTTP ───

class H(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._j({"ok": True, "nodes": list(NODES.keys()), "slot": WIRING.get("instance", {}).get("slot", 0)})
        elif self.path == "/wiring":
            self._j(WIRING)
        elif self.path == "/state":
            self._j(load_state() or {})
        elif self.path == "/bus":
            self._j(bus_read())
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
        elif self.path == "/resume":
            s = load_state()
            if not s: self._j({"error": "no saved state"}, 404); return
            threading.Thread(target=run, args=(s.get("goal",""),s), daemon=True).start()
            self._j({"resumed": True, "goal": s.get("goal","")})
        elif self.path == "/bus/post":
            msgs = bus_read(); msgs.append(body); bus_write(msgs)
            self._j({"ok": True})
        elif self.path == "/interrupt":
            # Post a goal interrupt to this rod's bus slot
            new_goal = body.get("goal", "")
            if not new_goal: self._j({"error": "no goal"}, 400); return
            slot = WIRING.get("instance", {}).get("slot", 0)
            msgs = bus_read()
            msgs.append({"ts": time.time(), "from_slot": 0, "to_slot": slot, "type": "goal", "payload": {"goal": new_goal}})
            bus_write(msgs)
            self._j({"interrupted": True, "goal": new_goal})
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
    if "--resume" in args:
        s = load_state()
        if not s: print("No state.json to resume from"); sys.exit(1)
        srv = http.server.HTTPServer(("127.0.0.1", 9077), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        run(s.get("goal", ""), s)
    elif "--run" in args:
        goal = " ".join(args[args.index("--run")+1:])
        if not goal: print("Usage: python server.py --run \"goal\""); sys.exit(1)
        port = int(WIRING.get("instance", {}).get("slot", 0)) + 9077 if WIRING.get("instance", {}).get("slot", 0) else 9077
        srv = http.server.HTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"SSE: http://127.0.0.1:{port}/events")
        run(goal)
    else:
        port = int(args[0]) if args and args[0].isdigit() else 9077
        srv = http.server.HTTPServer(("127.0.0.1", port), H)
        print(f"endgame-ai [{WIRING.get('instance',{}).get('slot',0)}] on http://127.0.0.1:{port}  nodes: {list(NODES.keys())}")
        srv.serve_forever()
