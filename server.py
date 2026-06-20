"""
endgame-ai — stdlib only, zero pip.
One file. Node handlers are pure functions. Wiring.json is the brain.
"""
import json, http.server, urllib.request, pathlib, time, sys, re, threading, queue, os, importlib, importlib.util

class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

ROOT = pathlib.Path(__file__).parent
PROMPTS = ROOT / "prompts"
STATE_FILE = ROOT / "state.json"
BUS_FILE = pathlib.Path(os.environ.get("ENDGAME_BUS", str(ROOT / "bus.json")))
WIRING = json.loads((PROMPTS / "wiring.json").read_text(encoding="utf-8"))
WIRING_SCHEMA = json.loads((PROMPTS / "wiring-schema.json").read_text(encoding="utf-8"))
MODEL = json.loads((PROMPTS / "model.json").read_text(encoding="utf-8"))


def validate_wiring(w):
    """Validate wiring against schema. Returns list of error strings (empty = valid)."""
    errs = []
    if not isinstance(w, dict):
        return ["root must be object"]
    if w.get("schema") != "endgame-topology/v1":
        errs.append("schema must be 'endgame-topology/v1'")
    topo = w.get("topology")
    if not isinstance(topo, dict):
        return errs + ["topology required and must be object"]
    if not topo.get("cycle_start"):
        errs.append("topology.cycle_start required")
    nodes = topo.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return errs + ["topology.nodes must be non-empty array"]
    node_ids = set()
    id_pat = re.compile(r'^[a-z][a-z0-9_]*$')
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errs.append(f"nodes[{i}] must be object"); continue
        nid = n.get("id", "")
        if not nid or not id_pat.match(nid):
            errs.append(f"nodes[{i}].id invalid: '{nid}'")
        if not n.get("type"):
            errs.append(f"nodes[{i}].type required")
        if "label" not in n:
            errs.append(f"nodes[{i}].label required")
        node_ids.add(nid)
    if topo.get("cycle_start") not in node_ids:
        errs.append(f"cycle_start '{topo.get('cycle_start')}' not in nodes")
    for i, e in enumerate(topo.get("edges") or []):
        if not isinstance(e, dict):
            errs.append(f"edges[{i}] must be object"); continue
        if e.get("from") not in node_ids:
            errs.append(f"edges[{i}].from '{e.get('from')}' unknown")
        if e.get("to") not in node_ids:
            errs.append(f"edges[{i}].to '{e.get('to')}' unknown")
        if not e.get("on"):
            errs.append(f"edges[{i}].on required")
    return errs

try:
    from actions import execute_verb, observe_screen
except Exception:
    def observe_screen(): return "(desktop not available)"
    def execute_verb(verb, target, value=""): return f"[stub] {verb} {target} {value}"

# ─── Wiring accessors (policy lives in wiring.json — Python only executes) ───

def wiring_limit(key, default=None):
    return WIRING.get("limits", {}).get(key, default)

def wiring_error(key, **fmt):
    msg = WIRING.get("errors", {}).get(key, key)
    return msg.format(**fmt) if fmt else msg

LLM_NODE_TYPES = frozenset({"planner", "act", "verify", "reflect", "self_modify"})

def topo_node(node_type):
    for n in WIRING.get("topology", {}).get("nodes", []):
        if n.get("type") == node_type:
            return n
    return {}

def circuit_for(node_type):
    """Circuit role key for reasoning store — from node.prompt.role on topology."""
    node = topo_node(node_type)
    prompt = node.get("prompt", {})
    return prompt.get("role") or node.get("circuit") or WIRING.get("node_circuits", {}).get(node_type, node_type)

def node_circuits_map():
    out = {}
    for n in WIRING.get("topology", {}).get("nodes", []):
        t = n.get("type")
        if t in LLM_NODE_TYPES or n.get("prompt"):
            out[t] = circuit_for(t)
    return out

def _prompt_cfg(node_type=None, circuit=None):
    if node_type:
        cfg = topo_node(node_type).get("prompt", {})
        if cfg:
            return cfg
    if circuit:
        return WIRING.get("request", {}).get(circuit, {})
    return {}

def http_port(slot=None):
    rt = WIRING.get("runtime", {})
    base = int(rt.get("http_port_base", 9077))
    if slot is None:
        slot = int(WIRING.get("instance", {}).get("slot", 0) or 0)
    if slot and rt.get("http_port_slot_offset", True):
        return base + int(slot)
    return base

def http_bind():
    return os.environ.get("ENDGAME_BIND") or WIRING.get("runtime", {}).get("http_bind", "0.0.0.0")

def local_lan_ips():
    import socket
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ips)

def print_listen_urls(port):
    bind = http_bind()
    print(f"  local   http://127.0.0.1:{port}")
    if bind in ("0.0.0.0", "::"):
        for ip in local_lan_ips():
            print(f"  lan     http://{ip}:{port}")
        print(f"  phone   same WiFi - open LAN URL in browser")
        print(f"  firewall (once, admin PS): netsh advfirewall firewall add rule name=\"endgame-ai\" dir=in action=allow protocol=TCP localport={port}")

def colony_port(slot):
    rt = WIRING.get("runtime", {})
    return int(rt.get("colony_port_base", 9076)) + int(slot)

def fresh_state(goal):
    state = dict(WIRING.get("runtime", {}).get("initial_state", {}))
    state["goal"] = goal
    state["bus_last_check"] = time.time()
    return state

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
    BUS_FILE.write_text(json.dumps(msgs[-wiring_limit("bus_max", 200):], indent=1), encoding="utf-8")

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

def extract_json_objects(text):
    """Return all top-level JSON objects in text, in document order."""
    if not text:
        return []
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        for j in range(i, n):
            c = text[j]
            if esc:
                esc = False
                continue
            if c == "\\" and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        out.append(json.loads(text[i:j + 1]))
                    except json.JSONDecodeError:
                        pass
                    i = j + 1
                    break
        else:
            break
    return out

def extract_json(text):
    objs = extract_json_objects(text)
    return objs[0] if objs else None

# ─── Reasoning loop (wired in wiring.json — Python only captures + resolves) ───

def reasoning_patch(state, circuit, reasoning_text):
    """Store LM Studio reasoning_content per wiring.reasoning.store_as + append chain."""
    text = (reasoning_text or "").strip()
    if not text:
        return {}
    cfg = WIRING.get("reasoning", {})
    store_as = cfg.get("store_as", {}).get(circuit, circuit)
    reasoning = dict(state.get("reasoning", {}))
    reasoning[store_as] = text
    reasoning["last"] = text
    reasoning["last_circuit"] = store_as
    chain = list(state.get("reasoning_chain", []))
    chain.append({"circuit": store_as, "text": text, "ts": time.time()})
    depth = cfg.get("chain_depth", wiring_limit("reasoning_chain_depth", 8))
    return {"reasoning": reasoning, "reasoning_chain": chain[-depth:]}

def clear_reasoning_patch(state, keys):
    """Clear per-circuit reasoning slots (wired via reasoning.clear_on_step_confirm)."""
    if not keys:
        return {}
    reasoning = dict(state.get("reasoning", {}))
    for k in keys:
        reasoning.pop(k, None)
    return {"reasoning": reasoning}

def parse_circuit_response(circuit, content, reasoning):
    """Parse LLM JSON; enforce wiring.reasoning.expected_record_type per circuit."""
    cfg = WIRING.get("reasoning", {})
    expected = cfg.get("expected_record_type", {}).get(circuit)
    fallback = circuit in cfg.get("parse_fallback", [])
    sources = [("content", content)]
    if fallback and reasoning:
        sources.append(("reasoning", reasoning))
    for source_name, text in sources:
        for parsed in extract_json_objects(text):
            if expected and parsed.get("record_type") != expected:
                continue
            return parsed, source_name
    return None, None

def call_node(node_type, state, extra=None):
    """Run LLM for a topology node: prompt on node + prompts.base/roles."""
    circuit = circuit_for(node_type)
    s = dict(state)
    if extra:
        s.update(extra)
    system = load_system_prompt(circuit, s, node_type=node_type)
    user = build_user_message(circuit, s, node_type=node_type)
    content, reasoning, _ = llm(system, user)
    patch = reasoning_patch(state, circuit, reasoning)
    parsed, _ = parse_circuit_response(circuit, content, reasoning)
    return {"content": content, "reasoning": reasoning, "parsed": parsed, "patch": patch}

# ─── Prompt assembly: static system, dynamic user (from wiring.json) ───

def _resolve_value(state, source):
    """Resolve a wiring request block source to a string value."""
    if source == "instance.persona":
        persona = WIRING.get("instance", {}).get("persona", "")
        if not persona:
            return ""
        pf = PROMPTS / "personalities" / f"{persona}.txt"
        return pf.read_text(encoding="utf-8") if pf.exists() else ""
    if source == "topology.nodes":
        return json.dumps([n["id"] for n in WIRING.get("topology", {}).get("nodes", [])])
    if source.startswith("reasoning."):
        key = source[10:]
        bucket = state.get("reasoning", {})
        if key == "chain":
            chain = state.get("reasoning_chain", [])
            depth = WIRING.get("reasoning", {}).get("chain_depth", wiring_limit("reasoning_chain_depth", 8))
            if not chain:
                return ""
            return "\n\n".join(f"[{e.get('circuit', '?')}] {e.get('text', '')}" for e in chain[-depth:])
        if key == "last":
            return bucket.get("last", "")
        return bucket.get(key, "")
    if source == "state.history":
        history = state.get("history", [])
        depth = wiring_limit("history_depth", 10)
        if not history:
            return ""
        recent = history[-depth:]
        return "\n".join(f"  [{h.get('attempt', 0)}] {h.get('action', '')} → {h.get('outcome', '')}" for h in recent)
    if source == "state.last_actions":
        actions = state.get("last_actions", [])
        return json.dumps(actions) if actions else ""
    if source.startswith("state."):
        key = source[6:]
        if key == "current_step.description":
            return state.get("current_step", {}).get("description", "")
        if key == "current_step.done_when":
            return state.get("current_step", {}).get("done_when", "")
        return state.get(key, "")
    return ""

def load_system_prompt(circuit, state=None, node_type=None):
    """Compose system prompt: node.prompt + prompts.base + prompts.roles. Legacy fallbacks."""
    prompts = WIRING.get("prompts", {})
    cfg = _prompt_cfg(node_type, circuit)
    use_base = cfg.get("extends", "base") != "none"
    base = prompts.get("base", "") if use_base else ""
    roles = prompts.get("roles", {})
    role_key = cfg.get("role", circuit)
    role_text = cfg.get("system") or roles.get(role_key, "")
    if not role_text:
        sys_cfg = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
        if sys_cfg.get("text"):
            role_text = sys_cfg["text"]
        elif sys_cfg.get("file"):
            pf = PROMPTS / sys_cfg["file"]
            if pf.exists():
                return pf.read_text(encoding="utf-8")
    if not role_text:
        pf = PROMPTS / f"{circuit}.txt"
        if pf.exists():
            return pf.read_text(encoding="utf-8")
    parts = [p.strip() for p in (base, role_text) if p and p.strip()]
    return "\n\n".join(parts)

def build_user_message(circuit, state, node_type=None):
    """Build dynamic user message from node.prompt.user.blocks (or legacy request)."""
    cfg = _prompt_cfg(node_type, circuit)
    blocks = cfg.get("user", {}).get("blocks", [])
    if not blocks:
        blocks = WIRING.get("request", {}).get(circuit, {}).get("user", {}).get("blocks", [])
    parts = []
    for block in blocks:
        label = block.get("label", "")
        value = _resolve_value(state, block.get("source", ""))
        if not value and not block.get("always"):
            if block.get("empty_template"):
                value = block["empty_template"]
            else:
                continue
        parts.append(f"{label}: {value}")
    return "\n".join(parts)

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

# ─── Node handlers ───

def node_entry(state, _):
    return {"signals": ["ready"], "patch": {}}

def node_planner(state, _):
    try:
        r = call_node("planner", state)
        parsed = r["parsed"]
        patch = dict(r["patch"])
        if not parsed or "data" not in parsed or "steps" not in parsed.get("data", {}):
            retries = state.get("planner_retries", 0) + 1
            max_r = wiring_limit("planner_retries", 3)
            patch.update({"planner_retries": retries, "last_error": wiring_error("planner_parse_failed")})
            if retries >= max_r:
                return {"signals": ["plan_failed"], "patch": patch}
            return {"signals": ["retry_plan"], "patch": patch}
        steps = parsed["data"]["steps"]
        if not steps:
            return {"signals": ["plan_failed"], "patch": {**patch, "last_error": wiring_error("planner_empty")}}
    except Exception as e:
        retries = state.get("planner_retries", 0) + 1
        max_r = wiring_limit("planner_retries", 3)
        patch = {"planner_retries": retries, "last_error": f"planner: {e}"}
        if retries >= max_r:
            return {"signals": ["plan_failed"], "patch": patch}
        return {"signals": ["retry_plan"], "patch": patch}
    return {"signals": ["plan_ready"], "patch": {**patch, "plan": steps, "step": 0, "retries": 0, "history": [], "planner_retries": 0, "last_error": ""}}

def node_scheduler(state, _):
    steps = state.get("plan", [])
    idx = state.get("step", 0)
    if idx >= len(steps):
        return {"signals": ["plan_complete"], "patch": {}}
    return {"signals": ["step_ready"], "patch": {"current_step": steps[idx], "step_goal": steps[idx]["description"]}}

def node_observe(state, _):
    if state.get("no_desktop"):
        s = state.get("screen") or WIRING.get("context", {}).get("screen_disabled", "(no desktop)")
    else:
        s = observe_screen()
    return {"signals": ["screen_ready"], "patch": {"screen": s}}

def node_act(state, _):
    """Static system prompt + dynamic user message. Guards + execute."""
    history = state.get("history", [])

    act_cfg = WIRING.get("act", {})
    reject = set(act_cfg.get("reject_conclusions", ["DONE"]))
    valid = set(act_cfg.get("valid_conclusions", ["EXECUTE", "CANNOT"]))

    try:
        r = call_node("act", state)
    except Exception as e:
        return {"signals": ["act_failed"], "patch": {"last_error": str(e)}}

    parsed = r["parsed"]
    patch = dict(r["patch"])
    if not parsed:
        preview = (r.get("content") or "")[:200].replace("\n", " ")
        patch["last_error"] = wiring_error("parse_failed") + f" (content: {preview!r})"
        print(f"       [!] act parse_failed: {patch['last_error']}")
        return {"signals": ["act_failed"], "patch": patch}

    conclusion = parsed.get("data", {}).get("conclusion", "")
    actions = parsed.get("data", {}).get("actions", [])

    if conclusion in reject:
        entry = {"attempt": len(history) + 1, "action": "DONE rejected", "outcome": "executor cannot emit DONE — verify confirms completion"}
        patch.update({
            "last_error": wiring_error("act_done_rejected"),
            "history": history + [entry],
        })
        return {"signals": ["act_failed"], "patch": patch}

    if conclusion == "CANNOT":
        entry = {"attempt": len(history) + 1, "action": "CANNOT", "outcome": "LLM cannot proceed"}
        patch.update({"last_error": wiring_error("act_cannot"), "history": history + [entry]})
        return {"signals": ["act_failed"], "patch": patch}

    if conclusion not in valid or not actions:
        patch["last_error"] = wiring_error("act_bad_conclusion", conclusion=conclusion)
        return {"signals": ["act_failed"], "patch": patch}

    # Guard: repeat block
    block = check_repeat_block(state, actions)
    if block:
        entry = {"attempt": len(history) + 1, "action": f"{actions[0].get('verb','')} {actions[0].get('target','')}", "outcome": f"BLOCKED: {block}"}
        patch.update({"last_error": block, "history": history + [entry]})
        return {"signals": ["act_failed"], "patch": patch}

    # Execute (normalize verb: press with + → hotkey)
    results = []
    for a in actions:
        verb = a.get("verb", "")
        target = a.get("target", "")
        for norm in act_cfg.get("verb_normalize", []):
            if verb == norm.get("from") and norm.get("when_target_contains", "") in target:
                verb = norm.get("to", verb)
        result = execute_verb(verb, target, a.get("value", ""))
        results.append(f"{verb} {a.get('target')}: {result}")

    outcome = "OK: " + "; ".join(results)
    entry = {"attempt": len(history) + 1, "action": f"{actions[0].get('verb','')} {actions[0].get('target','')}", "outcome": outcome}
    patch.update({
        "last_actions": results,
        "last_actions_raw": actions,
        "last_outcome": outcome,
        "last_error": "",
        "history": history + [entry],
    })
    return {"signals": ["acted"], "patch": patch}

def node_verify(state, _):
    """Verify from descriptive step + act outcomes only — act is sole SCREEN consumer."""
    try:
        r = call_node("verify", state)
        parsed = r["parsed"]
        patch = dict(r["patch"])
        if parsed and parsed.get("data", {}).get("confirmed"):
            clear_keys = WIRING.get("reasoning", {}).get("clear_on_step_confirm", [])
            patch.update(clear_reasoning_patch({**state, **patch}, clear_keys))
            patch.update({"step": state.get("step", 0) + 1, "retries": 0, "last_error": ""})
            return {"signals": ["step_confirmed"], "patch": patch}
        if not parsed:
            patch["last_error"] = wiring_error("verify_parse_failed")
        return {"signals": ["step_denied"], "patch": patch}
    except Exception as e:
        return {"signals": ["step_denied"], "patch": {"last_error": str(e)}}

def node_reflect(state, _):
    """Retry vs replan vs escalate. Retries exhausted → replan. Replans exhausted → escalate (self-modify)."""
    retries = state.get("retries", 0)
    replans = state.get("replan_count", 0)
    max_r = wiring_limit("max_attempts", 5)
    max_replans = wiring_limit("max_replans", 2)
    if retries >= max_r:
        if replans >= max_replans:
            return {"signals": ["escalate"], "patch": {"retries": 0, "replan_count": 0}}
        return {"signals": ["replan"], "patch": {"retries": 0, "replan_count": replans + 1}}

    try:
        r = call_node("reflect", state)
        parsed = r["parsed"]
        patch = {**r["patch"], "retries": retries + 1}
        if not parsed:
            patch["last_error"] = wiring_error("reflector_parse_failed")
            return {"signals": ["retry"], "patch": patch}
        if parsed.get("data", {}).get("should_replan"):
            if replans >= max_replans:
                return {"signals": ["escalate"], "patch": {"retries": 0, "replan_count": 0, **r["patch"]}}
            return {"signals": ["replan"], "patch": {"retries": 0, "replan_count": replans + 1, **r["patch"]}}
        return {"signals": ["retry"], "patch": patch}
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
        new_goal = newest.get("payload", {}).get("goal", state.get("goal", ""))
        if new_goal.strip().lower() == (state.get("goal", "") or "").strip().lower():
            return {"signals": ["no_interrupt"], "patch": {"bus_last_check": time.time()}}
        return {"signals": ["interrupt"], "patch": {
            "bus_last_check": time.time(),
            "goal": new_goal,
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

def _trigger_rod_run(slot, goal):
    """Wake a peer rod and start its autonomous loop."""
    port = colony_port(slot)
    body = json.dumps({"goal": goal}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/run",
                data=body,
                headers={"Content-Type": "application/json"},
            ),
            timeout=5,
        )
        return True
    except Exception as e:
        print(f"       [!] failed to start rod {slot} on :{port}: {e}")
        return False

def node_moe_route(state, _):
    """MoE gate: route goal to self or delegate to another rod via bus.
    Reads colony telemetry from bus to pick best slot.
    If this rod's persona matches goal domain → self.
    Otherwise → delegate to best slot via bus post."""
    goal = (state.get("goal", "") or "").lower()
    my_slot = WIRING.get("instance", {}).get("slot", 0)
    permissions = WIRING.get("instance", {}).get("permissions", [])

    # Simple competence matching from persona
    moe = WIRING.get("moe", {})
    need_perm = moe.get("required_permission", "desktop_exec")
    delegate_kw = moe.get("delegate_keywords", [])
    if need_perm not in permissions and any(k in goal for k in delegate_kw):
        msgs = bus_read()
        exec_slots = set()
        for m in msgs:
            if m.get("type") == "telemetry" and m.get("from_slot") != my_slot:
                exec_slots.add(m.get("from_slot"))
        target = min(exec_slots) if exec_slots else int(moe.get("default_exec_slot", 1))
        full_goal = state.get("goal", "")
        bus_write(msgs + [{"ts": time.time(), "from_slot": my_slot, "to_slot": target, "type": "goal", "payload": {"goal": full_goal}}])
        _trigger_rod_run(target, full_goal)
        return {"signals": ["delegated"], "patch": {"delegated_to": target}}

    # This rod handles it
    return {"signals": ["self"], "patch": {}}

def node_self_modify(state, _):
    """Self-modification: alter own wiring.json and hot-reload topology.
    Triggered by reflect on 'escalate' signal when stuck.
    Uses LLM to decide what to change in the topology."""
    global WIRING
    wiring_path = PROMPTS / "wiring.json"
    current = json.loads(wiring_path.read_text(encoding="utf-8"))
    # Backup before mutation
    (PROMPTS / "wiring.backup.json").write_text(json.dumps(current, indent=2), encoding="utf-8")
    try:
        r = call_node("self_modify", state)
        parsed = r["parsed"]
        patch = dict(r["patch"])
        expected = WIRING.get("reasoning", {}).get("expected_record_type", {}).get("self_modify", "wiring_patch")
        if not parsed or parsed.get("record_type") != expected:
            patch["last_error"] = wiring_error("self_modify_invalid")
            return {"signals": ["modify_failed"], "patch": patch}

        op = parsed["data"]["op"]
        payload = parsed["data"]["payload"]
        topo = current["topology"]

        if op == "add_node":
            node = {"id": payload["id"], "type": payload["type"], "label": payload.get("label", payload["id"])}
            topo["nodes"].append(node)
            if payload.get("edge_from"):
                topo["edges"].append({"from": payload["edge_from"], "to": payload["id"], "on": payload.get("on", "ready")})
            if payload.get("edge_to"):
                topo["edges"].append({"from": payload["id"], "to": payload["edge_to"], "on": "done"})
        elif op == "add_edge":
            topo["edges"].append({"from": payload["from"], "to": payload["to"], "on": payload.get("on", "ready")})
        elif op == "remove_edge":
            topo["edges"] = [e for e in topo["edges"] if not (e["from"] == payload["from"] and e["to"] == payload["to"])]
        elif op == "set_guard":
            current.setdefault("guards", {})[payload["key"]] = payload["value"]
        else:
            patch["last_error"] = f"unknown op: {op}"
            return {"signals": ["modify_failed"], "patch": patch}

        # Write and hot-reload
        wiring_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        WIRING = current
        sse_push("wiring_modified", {"op": op, "payload": payload})
        patch.update({"self_modify_op": op, "self_modify_payload": payload})
        return {"signals": ["modified"], "patch": patch}
    except Exception as e:
        return {"signals": ["modify_failed"], "patch": {"last_error": f"self_modify: {e}"}}

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
    "moe_route": node_moe_route,
    "self_modify": node_self_modify,
}

# ─── Hot-reload node handlers from nodes/ directory ───

NODES_DIR = ROOT / "nodes"
NODES_DIR.mkdir(exist_ok=True)
_handler_mtimes = {}

def hot_load_nodes():
    """Scan nodes/ dir and load/reload any new or changed .py handler modules."""
    importlib.invalidate_caches()
    for f in NODES_DIR.iterdir():
        if f.suffix != '.py' or f.name.startswith('_'):
            continue
        mtime = f.stat().st_mtime
        name = f.stem
        if name in _handler_mtimes and _handler_mtimes[name] >= mtime:
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"nodes.{name}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'handler'):
                NODES[name] = mod.handler
                _handler_mtimes[name] = mtime
        except Exception as e:
            print(f"[hot-load] {name}: {e}")

hot_load_nodes()  # initial scan

def _node_watcher():
    while True:
        time.sleep(2)
        hot_load_nodes()

threading.Thread(target=_node_watcher, daemon=True).start()

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
        state = fresh_state(goal)
        node_id = topo["cycle_start"]
    cycle = 0
    max_cycles = wiring_limit("max_cycles", 300)
    cycle_delay = int(WIRING.get("runtime", {}).get("cycle_delay_ms", 300)) / 1000.0

    print(f"\n{'='*50}\n  ROD [{WIRING.get('instance',{}).get('slot',0)}]: {goal}\n{'='*50}\n")

    while cycle < max_cycles:
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
        print(f"       -> {signals}")

        sse_push("result", {"c": cycle, "id": node_id, "s": signals})

        # Persist state each cycle
        state["_resume_node"] = node_id
        save_state(state)

        targets = find_targets(node_id, signals, topo)
        if not targets:
            print(f"\n[{cycle}] terminal - no outgoing edge for {signals}")
            break
        node_id = targets[0]
        time.sleep(cycle_delay)

    print(f"\nDone. step={state.get('step')} satisfied={state.get('satisfied')}")
    sse_push("stop", {"outcome": state.get("satisfied", False)})
    return state

# ─── HTTP ───

class H(http.server.BaseHTTPRequestHandler):
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

    def _write(self, data):
        try:
            self.wfile.write(data)
            return True
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            return False

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            slot = WIRING.get("instance", {}).get("slot", 0)
            self._j({
                "ok": True,
                "nodes": list(NODES.keys()),
                "node_circuits": node_circuits_map(),
                "slot": slot,
                "port": http_port(slot),
            })
        elif self.path == "/wiring":
            self._j(WIRING)
        elif self.path == "/schema":
            self._j(WIRING_SCHEMA)
        elif self.path == "/state":
            self._j(load_state() or {})
        elif self.path == "/bus":
            self._j(bus_read())
        elif self.path == "/smoke":
            # Programmatic smoke test — validates all endpoints work
            results = []
            try:
                results.append({"test": "health", "ok": True})
                results.append({"test": "wiring", "ok": len(WIRING.get("topology", {}).get("nodes", [])) > 0, "nodes": len(WIRING.get("topology", {}).get("nodes", []))})
                results.append({"test": "schema", "ok": bool(WIRING_SCHEMA)})
                # Test entry node
                h = NODES.get("entry")
                if h:
                    r = h({"goal": "smoke_test"}, {})
                    results.append({"test": "node/entry", "ok": "signals" in r, "signals": r.get("signals")})
                else:
                    results.append({"test": "node/entry", "ok": False, "error": "no handler"})
                results.append({"test": "html", "ok": (ROOT / "wiring-editor.html").exists()})
            except Exception as e:
                results.append({"test": "exception", "ok": False, "error": str(e)})
            passed = sum(1 for r in results if r["ok"])
            self._j({"passed": passed, "total": len(results), "all_ok": passed == len(results), "results": results})
        elif self.path in ("/", "/index.html"):
            d = (ROOT / "wiring-editor.html").read_bytes()
            self.send_response(200); self.send_header("Content-Type","text/html"); self.send_header("Content-Length",len(d)); self.end_headers(); self._write(d)
        elif self.path == "/events":
            self.send_response(200); self._cors()
            self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.end_headers()
            q = queue.Queue(); SSE.append(q)
            try:
                while True:
                    try:
                        msg = q.get(timeout=30)
                    except queue.Empty:
                        if not self._write(":keepalive\n\n".encode()):
                            break
                        self.wfile.flush()
                        continue
                    if not self._write(msg.encode()):
                        break
                    self.wfile.flush()
            except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
                pass
            finally:
                if q in SSE: SSE.remove(q)
        else:
            self.send_error(404)

    def do_POST(self):
        global WIRING
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))) if int(self.headers.get("Content-Length", 0) or 0) > 0 else {}
        if self.path.startswith("/node/"):
            t = self.path[6:]
            h = NODES.get(t)
            if not h: self._j({"error": f"unknown: {t}"}, 404); return
            try:
                r = h(body.get("state", {}), body.get("config", {}))
                r["state_patch"] = r.pop("patch", {})  # browser expects state_patch
                self._j(r)
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
        elif self.path == "/wiring" and body:
            # Hot-reload: POST new wiring.json (validates against schema)
            errs = validate_wiring(body)
            if errs:
                self._j({"error": "validation failed", "details": errs}, 400)
                return
            try:
                WIRING = body
                (PROMPTS / "wiring.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
                sse_push("wiring_modified", {"source": "api"})
                self._j({"reloaded": True, "nodes": len(body.get("topology", {}).get("nodes", []))})
            except Exception as e:
                self._j({"error": str(e)}, 500)
        else:
            self.send_error(404)

    def _j(self, d, code=200):
        self.send_response(code); self._cors(); self.send_header("Content-Type","application/json"); self.end_headers()
        self._write(json.dumps(d).encode())

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
        port = http_port()
        bind = http_bind()
        srv = ThreadingHTTPServer((bind, port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print_listen_urls(port)
        run(s.get("goal", ""), s)
    elif "--run" in args:
        goal = " ".join(args[args.index("--run")+1:])
        if not goal: print("Usage: python server.py --run \"goal\""); sys.exit(1)
        port = http_port()
        bind = http_bind()
        srv = ThreadingHTTPServer((bind, port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print_listen_urls(port)
        run(goal)
    else:
        port = int(args[0]) if args and args[0].isdigit() else http_port()
        bind = http_bind()
        srv = ThreadingHTTPServer((bind, port), H)
        print(f"endgame-ai [{WIRING.get('instance',{}).get('slot',0)}] bind={bind} port={port}  nodes: {list(NODES.keys())}")
        print_listen_urls(port)
        srv.serve_forever()
