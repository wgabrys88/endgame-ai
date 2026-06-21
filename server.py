"""
endgame-ai — stdlib only, zero pip.
One file. Node handlers are pure functions. Wiring.json is the brain.
"""
import json, http.server, urllib.request, pathlib, time, sys, threading, queue, os, re

class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

ROOT = pathlib.Path(__file__).parent
PROMPTS = ROOT / "prompts"
STATE_FILE = ROOT / "state.json"
BUS_FILE = pathlib.Path(os.environ.get("ENDGAME_BUS", str(ROOT / "bus.json")))
TRACES_FILE = ROOT / "prompts" / "traces.jsonl"
WIRING = json.loads((PROMPTS / "wiring.json").read_text(encoding="utf-8"))
MODEL = json.loads((PROMPTS / "model.json").read_text(encoding="utf-8"))


def apply_instance_env():
    """Override instance.slot / permissions from environment (colony workers)."""
    global WIRING
    slot = os.environ.get("ENDGAME_SLOT")
    perms = os.environ.get("ENDGAME_PERMISSIONS")
    if slot is None and perms is None:
        return
    inst = dict(WIRING.get("instance", {}))
    if slot is not None:
        inst["slot"] = int(slot)
    if perms is not None:
        inst["permissions"] = [p.strip() for p in perms.split(",") if p.strip()]
    WIRING = {**WIRING, "instance": inst}


apply_instance_env()


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
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errs.append(f"nodes[{i}] must be object"); continue
        nid = n.get("id", "")
        if not nid or not nid[0].isalpha() or not all(c.isalnum() or c == '_' for c in nid):
            errs.append(f"nodes[{i}].id invalid: '{nid}'")
        if nid in node_ids:
            errs.append(f"nodes[{i}].id duplicate: '{nid}'")
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
    from actions import execute_verb, observe_screen, configure_runtime, last_observation_snapshot
except Exception:
    def observe_screen(): return "(desktop not available)"
    def execute_verb(verb, target, value=""): return f"[stub] {verb} {target} {value}"
    def configure_runtime(_wiring): pass
    def last_observation_snapshot(): return {}


configure_runtime(WIRING)

# ─── Wiring accessors (policy lives in wiring.json — Python only executes) ───

def wiring_limit(key, default=None):
    return WIRING.get("limits", {}).get(key, default)

def wiring_error(key, **fmt):
    msg = WIRING.get("errors", {}).get(key, key)
    return msg.format(**fmt) if fmt else msg

def preview_text(text, limit_key="debug_value_max_chars", default=1200):
    text = str(text or "")
    try:
        limit = int(wiring_limit(limit_key, default) or 0)
    except (TypeError, ValueError):
        limit = default
    if limit <= 0:
        return text
    return text[:limit]

LLM_NODE_TYPES = frozenset({"planner", "act", "verify", "reflect", "self_modify"})

def topo_node(node_type):
    for n in WIRING.get("topology", {}).get("nodes", []):
        if n.get("type") == node_type:
            return n
    return {}

def topo_node_by_id(node_id):
    for n in WIRING.get("topology", {}).get("nodes", []):
        if n.get("id") == node_id:
            return n
    return None

def circuit_for(node_type):
    """Circuit role key for reasoning store."""
    node = topo_node(node_type)
    return node.get("prompt", {}).get("role") or node.get("circuit") or node_type

def node_circuits_map():
    out = {}
    for n in WIRING.get("topology", {}).get("nodes", []):
        t = n.get("type")
        if t in LLM_NODE_TYPES or n.get("prompt"):
            out[t] = circuit_for(t)
    return out

def wiring_summary():
    """Compact self-description exposed to prompts and health."""
    topo = WIRING.get("topology", {})
    nodes = [
        {
            "id": n.get("id"),
            "type": n.get("type"),
            "circuit": circuit_for(n.get("type", "")) if n.get("type") in LLM_NODE_TYPES or n.get("prompt") else "",
            "label": n.get("label", ""),
        }
        for n in topo.get("nodes", [])
    ]
    edges = [
        {"from": e.get("from"), "on": e.get("on"), "to": e.get("to")}
        for e in topo.get("edges", [])
    ]
    perms = WIRING.get("instance", {}).get("permissions", [])
    roles = sorted(WIRING.get("prompts", {}).get("roles", {}).keys())
    return {
        "schema": WIRING.get("schema"),
        "slot": WIRING.get("instance", {}).get("slot", 0),
        "permissions": perms,
        "nodes": nodes,
        "edges": edges,
        "roles": roles,
        "capabilities": {
            "desktop_exec": "desktop_exec" in perms,
            "rod_loop": all(r in roles for r in ("planner", "unified", "verifier")),
            "self_modify": "self_modify" in roles and any(n.get("type") == "self_modify" for n in topo.get("nodes", [])),
            "colony_delegate": bool(WIRING.get("moe", {}).get("delegate_keywords")),
            "trace_memory": True,
            "step_debug": True,
            "pause_resume": True,
            "wiring_hot_reload": True,
            "state_memory": "remember" in WIRING.get("verbs", {}),
        },
        "limits": WIRING.get("limits", {}),
        "observe": WIRING.get("observe", {}),
    }

def _prompt_cfg(node_type=None, circuit=None):
    if node_type:
        return topo_node(node_type).get("prompt", {})
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

def print_listen_urls(port):
    print(f"  http://127.0.0.1:{port}")

def simulation_mode():
    if os.environ.get("ENDGAME_SIM", "").lower() in ("1", "true", "yes"):
        return True
    return bool(WIRING.get("runtime", {}).get("simulation_mode", False))

def fresh_state(goal):
    state = dict(WIRING.get("runtime", {}).get("initial_state", {}))
    state["goal"] = goal
    state["bus_last_check"] = time.time()
    if simulation_mode():
        state["simulation"] = True
        state["no_desktop"] = False
    return state

# ─── SSE ───
SSE = []

def sse_push(evt, data):
    msg = f"event: {evt}\ndata: {json.dumps(data)}\n\n"
    for q in list(SSE):
        try: q.put_nowait(msg)
        except: SSE.remove(q)

# ─── State persistence ───

RUN_QUEUE = queue.Queue()
RUN_STATUS_LOCK = threading.Lock()
RUNNER_THREAD = None
RUN_STATUS = {
    "running": False,
    "paused": False,
    "pause_requested": False,
    "goal": "",
    "queued": 0,
    "last_goal": "",
    "last_satisfied": None,
    "last_error": "",
}

def run_status_snapshot():
    with RUN_STATUS_LOCK:
        status = dict(RUN_STATUS)
    status["queued"] = RUN_QUEUE.qsize()
    return status

def _run_worker_loop():
    while True:
        job = RUN_QUEUE.get()
        with RUN_STATUS_LOCK:
            RUN_STATUS.update({
                "running": True,
                "paused": False,
                "goal": job.get("goal", ""),
                "queued": RUN_QUEUE.qsize(),
                "last_error": "",
            })
        try:
            result = run(job.get("goal", ""), job.get("resume_state"), job.get("max_cycles"))
            with RUN_STATUS_LOCK:
                RUN_STATUS.update({
                    "last_goal": job.get("goal", ""),
                    "last_satisfied": result.get("satisfied"),
                    "last_error": "",
                })
        except Exception as e:
            print(f"[run-worker] {type(e).__name__}: {e}")
            sse_push("stop", {"outcome": False, "error": str(e)})
            with RUN_STATUS_LOCK:
                RUN_STATUS.update({
                    "last_goal": job.get("goal", ""),
                    "last_satisfied": False,
                    "last_error": str(e),
                })
        finally:
            with RUN_STATUS_LOCK:
                RUN_STATUS.update({"running": False, "goal": "", "queued": RUN_QUEUE.qsize()})
            RUN_QUEUE.task_done()

def ensure_run_worker():
    global RUNNER_THREAD
    with RUN_STATUS_LOCK:
        if RUNNER_THREAD and RUNNER_THREAD.is_alive():
            return
        RUNNER_THREAD = threading.Thread(target=_run_worker_loop, daemon=True, name="rod-runner")
        RUNNER_THREAD.start()

def enqueue_run(goal, resume_state=None, max_cycles=None):
    ensure_run_worker()
    RUN_QUEUE.put({"goal": goal, "resume_state": resume_state, "max_cycles": max_cycles})
    with RUN_STATUS_LOCK:
        RUN_STATUS["queued"] = RUN_QUEUE.qsize()
        RUN_STATUS["paused"] = False
        RUN_STATUS["pause_requested"] = False
        running = RUN_STATUS["running"]
    return {"started": True, "queued": RUN_QUEUE.qsize(), "running": running}

def request_pause():
    with RUN_STATUS_LOCK:
        RUN_STATUS["pause_requested"] = True
        running = RUN_STATUS["running"]
        queued = RUN_QUEUE.qsize()
    sse_push("pause", {"requested": True, "running": running})
    return {"pause_requested": True, "running": running, "queued": queued}

def run_pause_requested():
    with RUN_STATUS_LOCK:
        return bool(RUN_STATUS.get("pause_requested"))

def pause_run_state(state, node_id):
    state["_resume_node"] = node_id
    state["_paused"] = True
    save_state(state)
    with RUN_STATUS_LOCK:
        RUN_STATUS["paused"] = True
        RUN_STATUS["pause_requested"] = False
    sse_push("paused", {"node": node_id, "cycle": state.get("_cycle", 0)})
    return state

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

def append_trace(state):
    """Persist successful ROD trace for few-shot replay."""
    steps = state.get("plan", [])
    if not steps or state.get("step", 0) < len(steps):
        return
    entry = {
        "ts": time.time(),
        "goal": state.get("goal", ""),
        "plan": steps,
        "history": state.get("history", [])[-wiring_limit("history_depth", 10):],
    }
    try:
        with TRACES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        print(f"[trace] {e}")

def recent_traces(limit=3):
    if not TRACES_FILE.exists():
        return []
    lines = TRACES_FILE.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

# ─── LLM ───

def llm(system, user, temperature=None):
    body = {
        "model": MODEL.get("model", "local-model"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": MODEL.get("temperature", 0.3) if temperature is None else temperature,
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
    """Return all top-level JSON objects found in text."""
    if not text:
        return []
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1; continue
        depth, in_str, esc = 0, False, False
        for j in range(i, n):
            c = text[j]
            if esc: esc = False; continue
            if c == "\\" and in_str: esc = True; continue
            if c == '"': in_str = not in_str; continue
            if in_str: continue
            depth += (c == "{") - (c == "}")
            if depth == 0:
                try: out.append(json.loads(text[i:j + 1]))
                except json.JSONDecodeError: pass
                i = j + 1; break
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
    base_temp = MODEL.get("temperature", 0.3)
    bump = MODEL.get("temperature_bump", 0.15)
    max_retries = wiring_limit("llm_parse_retries", 2)
    content, reasoning, parsed, source = "", "", None, None
    patch = {}
    for attempt in range(max_retries + 1):
        temp = base_temp if attempt == 0 else min(1.0, base_temp + bump * attempt)
        reason_content, reason_trace, _ = llm(system, user, temperature=temp)
        rod_reasoning = (reason_trace or reason_content or "").strip()
        final_user = (
            user
            + "\n\nROD_REASONING_CONTENT:\n"
            + (rod_reasoning or "(none)")
            + "\n\nDECIDE NOW: emit exactly one content JSON object for this role. No prose."
        )
        content, final_trace, _ = llm(system, final_user, temperature=temp)
        reasoning = "\n\n".join(p for p in (rod_reasoning, final_trace.strip()) if p)
        attempt_patch = reasoning_patch(state, circuit, reasoning)
        if attempt_patch:
            patch = attempt_patch
        parsed, source = parse_circuit_response(circuit, content, reasoning)
        if parsed:
            break
    return {"content": content, "reasoning": reasoning, "parsed": parsed, "patch": patch, "parse_source": source}

# ─── Prompt assembly: static system, dynamic user (from wiring.json) ───

def _resolve_value(state, source):
    """Resolve a wiring request block source to a string value."""
    if source == "topology.nodes":
        return json.dumps([n["id"] for n in WIRING.get("topology", {}).get("nodes", [])])
    if source == "topology.summary":
        return json.dumps(wiring_summary(), ensure_ascii=True)
    if source == "traces.recent":
        if not state.get("replanning") and not state.get("replan_count"):
            return ""
        traces = recent_traces(wiring_limit("trace_few_shot", 2))
        if not traces:
            return ""
        return "\n\n".join(
            f"STRUCTURAL EXAMPLE ONLY - do not copy literals into the current goal\nGOAL: {t.get('goal','')}\nPLAN: {json.dumps(t.get('plan', []))}"
            for t in traces
        )
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
    if source == "state.last_actions_raw":
        actions = state.get("last_actions_raw", [])
        return json.dumps(actions) if actions else ""
    if source.startswith("state."):
        key = source[6:]
        if key == "current_step.description":
            return state.get("current_step", {}).get("description", "")
        if key == "current_step.done_when":
            return state.get("current_step", {}).get("done_when", "")
        value = state.get(key, "")
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=True)
        return value
    return ""

def load_system_prompt(circuit, state=None, node_type=None):
    """Compose system prompt: prompts.base + prompts.roles[key]."""
    prompts = WIRING.get("prompts", {})
    cfg = _prompt_cfg(node_type, circuit)
    base = prompts.get("base", "") if cfg.get("extends", "base") != "none" else ""
    role_key = cfg.get("role", circuit)
    role_text = cfg.get("system") or prompts.get("roles", {}).get(role_key, "")
    parts = [p.strip() for p in (base, role_text) if p and p.strip()]
    return "\n\n".join(parts)

def resolve_prompt_blocks(node_type, state):
    """Resolve node prompt input blocks for execution and dashboard inspection."""
    cfg = _prompt_cfg(node_type=node_type)
    blocks = cfg.get("user", {}).get("blocks", [])
    resolved = []
    for block in blocks:
        label = block.get("label", "")
        source = block.get("source", "")
        value = _resolve_value(state, source)
        included = True
        if not value and not block.get("always"):
            if block.get("empty_template"):
                value = block["empty_template"]
            else:
                included = False
                value = ""
        resolved.append({
            "label": label,
            "source": source,
            "value": value,
            "included": included,
            "always": bool(block.get("always")),
        })
    return resolved

def build_user_message(circuit, state, node_type=None):
    """Build dynamic user message from node.prompt.user.blocks."""
    parts = []
    for block in resolve_prompt_blocks(node_type, state):
        if block["included"]:
            parts.append(f"{block['label']}: {block['value']}")
    return "\n".join(parts)

def node_debug_context(node_id, state):
    """Return schema-independent node context for GUI/API inspection."""
    topo = WIRING.get("topology", {})
    node_cfg = topo_node_by_id(node_id) if node_id else None
    if not node_cfg:
        return {"id": node_id, "error": f"unknown node: {node_id}"}
    node_type = node_cfg.get("type", "")
    has_prompt = bool(node_cfg.get("prompt")) or node_type in LLM_NODE_TYPES
    incoming = [e for e in topo.get("edges", []) if e.get("to") == node_id]
    outgoing = [e for e in topo.get("edges", []) if e.get("from") == node_id]
    return {
        "id": node_id,
        "type": node_type,
        "label": node_cfg.get("label", ""),
        "circuit": circuit_for(node_type) if has_prompt else "",
        "config": node_cfg,
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "wired_inputs": resolve_prompt_blocks(node_type, state) if has_prompt else [],
        "reasoning": state.get("reasoning", {}),
        "reasoning_chain": state.get("reasoning_chain", []),
    }

def inspect_state(goal="", state=None, node_id=None):
    topo = WIRING["topology"]
    state = dict(state if state is not None else (load_state() or {}))
    if goal and not state.get("goal"):
        state["goal"] = goal
    node_id = node_id or state.get("_resume_node") or topo.get("cycle_start")
    return {
        "node": node_id,
        "state": state,
        "debug": node_debug_context(node_id, state),
        "wiring": wiring_summary(),
        "run": run_status_snapshot(),
    }

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

def apply_memory_action(existing_memory, target, value):
    """Apply act's remember verb without desktop or model side effects."""
    memory = dict(existing_memory or {})
    key = target or f"note_{len(memory) + 1}"
    text = str(value or "")
    if not text.strip():
        return False, memory, "FAILED: empty memory value"
    memory[key] = value
    return True, memory, f"stored {key} ({len(text)} chars)"

def _step_text(state):
    step = state.get("current_step", {})
    return f"{step.get('description', '')} {step.get('done_when', '')}".lower()

def _target_screen_line(state, target):
    target = (target or "").strip()
    if not target:
        return ""
    id_match = re.match(r"^\[?(\d+)\]?$", target)
    screen = state.get("screen", "") or ""
    if id_match:
        needle = f"[{id_match.group(1)}]"
        for line in screen.splitlines():
            if needle in line:
                return line.lower()
    return target.lower()

def _focused_title(state):
    screen = state.get("screen", "") or ""
    for line in screen.splitlines():
        if line.lower().startswith("focused:"):
            return line.split(":", 1)[1].strip().lower()
    return ""

def _screen_action_id_count(screen, meta=None):
    if isinstance(meta, dict) and isinstance(meta.get("elements"), list):
        return len(meta["elements"])
    return sum(1 for line in (screen or "").splitlines() if re.match(r"\s*\[\d+\]\s+", line))

def _browser_focused(state):
    title = _focused_title(state)
    return any(token in title for token in ("chrome", "edge", "firefox", "browser", "youtube", "grok"))

def _focuses_browser(actions):
    for action in actions:
        if action.get("verb") != "focus":
            continue
        target = (action.get("target") or action.get("value") or "").lower()
        if any(token in target for token in ("chrome", "edge", "firefox", "browser", "youtube", "grok")):
            return True
    return False

def _is_browser_navigation_step(state):
    text = _step_text(state)
    return any(w in text for w in ("go to ", "navigate", "url", ".com", "youtube", "website", "page loads", "page is loaded"))

def _is_playback_step(state):
    text = _step_text(state)
    return any(w in text for w in ("play ", "playing", "playback", "video"))

def _is_chat_message_step(state):
    text = _step_text(state)
    if _is_browser_navigation_step(state):
        return False
    return any(w in text for w in ("send ", "message", "prompt", "follow-up", "question", "chat"))

def normalize_action_chain(state, actions):
    """Apply deterministic safety normalizations that do not change task intent."""
    out = [dict(a) for a in actions]
    if _is_browser_navigation_step(state) and any(a.get("verb") == "write" and a.get("value") for a in out):
        def is_ctrl_l(action):
            combo = (action.get("target") or action.get("value") or "").lower()
            return (
                action.get("verb") == "hotkey"
                and "ctrl" in combo
                and "l" in combo
            )

        first_write = next((i for i, a in enumerate(out) if a.get("verb") == "write" and a.get("value")), len(out))
        prefix = out[:first_write]
        suffix = out[first_write:]
        focus_prefix = [a for a in prefix if a.get("verb") == "focus"]
        ctrl_l_prefix = [a for a in prefix if is_ctrl_l(a)]
        other_prefix = [a for a in prefix if a.get("verb") != "focus" and not is_ctrl_l(a)]
        if focus_prefix or ctrl_l_prefix:
            if not ctrl_l_prefix:
                ctrl_l_prefix = [{"verb": "hotkey", "target": "ctrl+l", "value": ""}]
            out = focus_prefix + other_prefix + ctrl_l_prefix + suffix

        has_ctrl_l = any(
            a.get("verb") == "hotkey"
            and "ctrl" in (a.get("target") or a.get("value") or "").lower()
            and "l" in (a.get("target") or a.get("value") or "").lower()
            for a in out
        )
        if not has_ctrl_l:
            insert_at = 0
            while insert_at < len(out) and out[insert_at].get("verb") == "focus":
                insert_at += 1
            out.insert(insert_at, {"verb": "hotkey", "target": "ctrl+l", "value": ""})
        has_enter = any(
            a.get("verb") in ("press", "hotkey")
            and "enter" in (a.get("target") or a.get("value") or "").lower()
            for a in out
        )
        if not has_enter:
            out.append({"verb": "press", "target": "enter", "value": ""})
    return out

def unsafe_chat_target(state, actions):
    if not _is_chat_message_step(state):
        return ""
    for a in actions:
        if a.get("verb") != "write":
            continue
        line = _target_screen_line(state, a.get("target", ""))
        if "address and search bar" in line:
            return "chat/message write targeted the browser address bar; observe or navigate until a chat input is visible"
    return ""

def unsafe_browser_navigation_context(state, actions):
    if not _is_browser_navigation_step(state):
        return ""
    if not any(a.get("verb") == "write" and a.get("value") for a in actions):
        return ""
    if _browser_focused(state) or _focuses_browser(actions):
        return ""
    if any(a.get("verb") == "write" and "address" in _target_screen_line(state, a.get("target", "")) for a in actions):
        return ""
    return "browser navigation/search requires a browser or address bar focused; focus/open browser first"

def unsafe_launch_then_content_write(state, actions):
    saw_run = False
    app_value = ""
    launch_submitted = False
    for action in actions:
        verb = action.get("verb", "")
        target = (action.get("target") or action.get("value") or "").lower()
        value = str(action.get("value") or "")
        if verb == "hotkey" and "win" in target and "r" in target:
            saw_run = True
            continue
        if saw_run and not app_value and verb == "write" and value:
            app_value = value.strip().lower()
            continue
        if saw_run and app_value and verb == "press" and "enter" in target:
            launch_submitted = True
            continue
        if launch_submitted and verb == "write" and value.strip().lower() != app_value:
            if len(value.strip()) > 20 or "summary" in _step_text(state):
                return "do not chain content writing immediately after launching an app; observe/focus the editor first"
    return ""

def _find_advance_hint(state, actions):
    """Match advance hints from wiring."""
    hints = WIRING.get("guards", {}).get("advance_hints", [])
    screen = (state.get("screen", "") or "").lower()
    for a in reversed(actions):
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

def _planner_ready_patch(state, steps, patch):
    """Apply plan_ready state patch — preserve progress on replan, reset on fresh plan."""
    out = {
        **patch,
        "plan": steps,
        "planner_retries": 0,
        "last_error": "",
        "plan_failed": False,
        "replanning": False,
        "_planned_goal": state.get("goal", ""),
        "reasoning_chain": [],
        "reasoning": {},
    }
    if state.get("replanning"):
        out.update({"step": 0, "retries": 0, "history": list(state.get("history", []))})
    else:
        out.update({"step": 0, "retries": 0, "history": []})
    return out

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
                return {"signals": ["plan_failed"], "patch": {**patch, "plan_failed": True}}
            return {"signals": ["retry_plan"], "patch": patch}
        steps = parsed["data"]["steps"]
        if not steps:
            return {"signals": ["plan_failed"], "patch": {**patch, "last_error": wiring_error("planner_empty"), "plan_failed": True}}
    except Exception as e:
        retries = state.get("planner_retries", 0) + 1
        max_r = wiring_limit("planner_retries", 3)
        patch = {"planner_retries": retries, "last_error": f"planner: {e}"}
        if retries >= max_r:
            return {"signals": ["plan_failed"], "patch": {**patch, "plan_failed": True}}
        return {"signals": ["retry_plan"], "patch": patch}
    return {"signals": ["plan_ready"], "patch": _planner_ready_patch(state, steps, patch)}

def node_scheduler(state, _):
    steps = state.get("plan", [])
    idx = state.get("step", 0)
    if idx >= len(steps):
        return {"signals": ["plan_complete"], "patch": {}}
    return {"signals": ["step_ready"], "patch": {"current_step": steps[idx], "step_goal": steps[idx]["description"]}}

def node_observe(state, _):
    if state.get("no_desktop"):
        s = state.get("screen") or WIRING.get("context", {}).get("screen_disabled", "(no desktop)")
        meta = {}
    else:
        obs_cfg = WIRING.get("observe", {})
        min_elements = obs_cfg.get("min_elements", 0)
        retries = obs_cfg.get("wait_retries", 0)
        wait_ms = obs_cfg.get("wait_ms", 500)
        s = observe_screen()
        meta = last_observation_snapshot()
        if min_elements > 0 and retries > 0:
            for _ in range(retries):
                if _screen_action_id_count(s, meta) >= min_elements:
                    break
                time.sleep(wait_ms / 1000.0)
                s = observe_screen()
                meta = last_observation_snapshot()
    patch = {"screen": s}
    if meta:
        patch["screen_meta"] = meta
    return {"signals": ["screen_ready"], "patch": patch}

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
        preview = preview_text(r.get("content") or "", "error_preview_chars", 1200).replace("\n", " ")
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

    actions = normalize_action_chain(state, actions)
    unsafe = unsafe_chat_target(state, actions)
    if unsafe:
        action_label = "; ".join(f"{a.get('verb','')} {a.get('target','')}" for a in actions)
        entry = {"attempt": len(history) + 1, "action": action_label, "outcome": f"BLOCKED: {unsafe}"}
        patch.update({"last_error": unsafe, "history": history + [entry]})
        return {"signals": ["act_failed"], "patch": patch}

    unsafe = unsafe_browser_navigation_context(state, actions)
    if unsafe:
        action_label = "; ".join(f"{a.get('verb','')} {a.get('target','')}" for a in actions)
        entry = {"attempt": len(history) + 1, "action": action_label, "outcome": f"BLOCKED: {unsafe}"}
        patch.update({"last_error": unsafe, "history": history + [entry]})
        return {"signals": ["act_failed"], "patch": patch}

    unsafe = unsafe_launch_then_content_write(state, actions)
    if unsafe:
        action_label = "; ".join(f"{a.get('verb','')} {a.get('target','')}" for a in actions)
        entry = {"attempt": len(history) + 1, "action": action_label, "outcome": f"BLOCKED: {unsafe}"}
        patch.update({"last_error": unsafe, "history": history + [entry]})
        return {"signals": ["act_failed"], "patch": patch}

    # Guard: repeat block
    block = check_repeat_block(state, actions)
    if block:
        action_label = "; ".join(f"{a.get('verb','')} {a.get('target','')}" for a in actions)
        entry = {"attempt": len(history) + 1, "action": action_label, "outcome": f"BLOCKED: {block}"}
        patch.update({"last_error": block, "history": history + [entry]})
        return {"signals": ["act_failed"], "patch": patch}

    # Execute (normalize verb: press with + -> hotkey)
    results = []
    failed = False
    chain_delay = int(WIRING.get("runtime", {}).get("action_chain_delay_ms", 0)) / 1000.0
    for i, a in enumerate(actions):
        verb = a.get("verb", "")
        target = a.get("target", "") or ""
        value = a.get("value", "") or ""
        prior = actions[:i]
        prior_run = any(
            pa.get("verb") == "hotkey"
            and "win" in (pa.get("target") or pa.get("value") or "").lower()
            and "r" in (pa.get("target") or pa.get("value") or "").lower()
            for pa in prior
        )
        screen_l = (state.get("screen") or "").lower()
        if verb == "write" and "focused: run" in screen_l and target:
            target = ""
            a["target"] = ""
        if verb == "write" and prior_run and target and target.strip().lower() == str(value).strip().lower():
            target = ""
            a["target"] = ""
        if verb == "press" and not (target or value) and any(pa.get("verb") == "write" for pa in prior):
            target = "enter"
            a["target"] = "enter"
        if verb == "click" and target.strip().lower() == "ok" and "focused: run" in screen_l:
            verb = "press"
            target = "enter"
            a["verb"] = "press"
            a["target"] = "enter"
        for norm in act_cfg.get("verb_normalize", []):
            if verb == norm.get("from") and norm.get("when_target_contains", "") in target:
                verb = norm.get("to", verb)
        if verb == "remember":
            ok_mem, memory, result = apply_memory_action(patch.get("memory") or state.get("memory"), target, value)
            if ok_mem:
                patch["memory"] = memory
        else:
            result = execute_verb(verb, target, value)
        label = target
        if verb == "write" and value:
            label = f"{target or 'focused'} value={preview_text(value)!r}"
        if verb == "remember" and value:
            label = f"{target or 'note'} value={preview_text(value)!r}"
        results.append(f"{verb} {label}: {result}")
        if str(result).upper().startswith("FAILED"):
            failed = True
            break
        if chain_delay and i < len(actions) - 1:
            time.sleep(chain_delay)

    ok = not failed and all(": FAILED" not in str(r).upper() and not str(r).upper().startswith("FAILED") for r in results)
    prefix = "OK: " if ok else "FAILED: "
    outcome = prefix + "; ".join(results)
    action_label = "; ".join(f"{a.get('verb','')} {a.get('target','')}" for a in actions)
    entry = {"attempt": len(history) + 1, "action": action_label, "outcome": outcome}
    patch.update({
        "last_actions": results,
        "last_actions_raw": actions,
        "last_outcome": outcome,
        "last_error": "",
        "history": history + [entry],
    })
    if not state.get("no_desktop") and WIRING.get("runtime", {}).get("refresh_screen_after_act", False):
        delay = int(WIRING.get("runtime", {}).get("act_post_delay_ms", 0)) / 1000.0
        if delay:
            time.sleep(delay)
        try:
            patch["screen"] = observe_screen()
        except Exception:
            pass
    return {"signals": ["acted"], "patch": patch}

def _verify_preflight_denied(state):
    """Deterministic deny before LLM — structural guard against false confirms."""
    outcome = (state.get("last_outcome") or "")
    if not outcome or not outcome.startswith("OK:"):
        return bool(outcome)
    return False

def _verify_preflight_confirmed(state):
    """Deterministic confirm for focus evidence: a focused window must already exist."""
    outcome = (state.get("last_outcome") or "")
    if not outcome.startswith("OK:"):
        return False
    done_when = (state.get("current_step", {}).get("done_when") or "").lower()
    actions = state.get("last_actions_raw", [])
    typed = " ".join((a.get("value") or "") for a in actions if a.get("verb") == "write").lower()
    submitted = " ".join(
        (a.get("target") or a.get("value") or "")
        for a in actions
        if a.get("verb") in ("press", "hotkey")
    ).lower()
    focused_title = _focused_title(state)
    screen_l = (state.get("screen") or "").lower()
    write_done = any(word in done_when for word in ("written", "write", "typed", "text", "summary"))
    editor_ready = any(word in focused_title for word in ("notepad", "editor")) or "document \"text editor\"" in screen_l
    if write_done and typed and editor_ready:
        return True
    playback_required = any(word in done_when for word in ("playing", "playback"))
    navigation_done = (
        not playback_required
        and any(word in done_when for word in ("load", "page", "navigate", "url", "website", "site", "youtube"))
    )
    ctrl_l_ready = any(
        a.get("verb") == "hotkey"
        and "ctrl" in (a.get("target") or a.get("value") or "").lower()
        and "l" in (a.get("target") or a.get("value") or "").lower()
        for a in actions
    ) and (_browser_focused(state) or _focuses_browser(actions))
    address_ready = ctrl_l_ready or any(
        a.get("verb") == "write"
        and "address" in _target_screen_line(state, a.get("target", ""))
        for a in actions
    )
    if navigation_done and address_ready and typed and typed in done_when and "enter" in submitted:
        return True
    if "open" in done_when and len(actions) >= 3:
        verbs = [a.get("verb", "") for a in actions]
        hotkey = (actions[0].get("target") or "").lower()
        pressed = " ".join((a.get("target") or a.get("value") or "") for a in actions if a.get("verb") == "press").lower()
        if verbs[:3] == ["hotkey", "write", "press"] and "win" in hotkey and "r" in hotkey and typed and typed in done_when and "enter" in pressed:
            return True
    if not any(word in done_when for word in ("open", "focused", "active window", "current window", "load", "page", "navigate", "url", "website", "site")):
        return False
    for action in actions:
        if action.get("verb") != "focus":
            continue
        target = (action.get("target") or "").strip().lower()
        target_words = [w for w in re.split(r"[^a-z0-9]+", target) if len(w) > 2]
        if target and (target in done_when or any(w in done_when for w in target_words)):
            return True
    return False

def node_verify(state, _):
    """Verify from descriptive step + act outcomes only — act is sole SCREEN consumer."""
    if _verify_preflight_denied(state):
        return {"signals": ["step_denied"], "patch": {"last_error": wiring_error("verify_preflight_denied")}}
    if _verify_preflight_confirmed(state):
        clear_keys = WIRING.get("reasoning", {}).get("clear_on_step_confirm", [])
        patch = clear_reasoning_patch(state, clear_keys)
        patch.update({"step": state.get("step", 0) + 1, "retries": 0, "last_error": ""})
        return {"signals": ["step_confirmed"], "patch": patch}
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
    if (
        _is_playback_step(state)
        and (state.get("last_outcome") or "").startswith("OK:")
        and any(a.get("verb") == "write" for a in state.get("last_actions_raw", []))
        and retries < max_r
    ):
        return {
            "signals": ["retry"],
            "patch": {
                "retries": retries + 1,
                "last_error": "playback not confirmed after search/navigation; observe results and click or play a matching video",
            },
        }
    if retries >= max_r:
        if replans >= max_replans:
            return {"signals": ["escalate"], "patch": {"retries": 0, "replan_count": 0}}
        return {"signals": ["replan"], "patch": {"retries": 0, "replan_count": replans + 1, "replanning": True}}

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
            return {"signals": ["replan"], "patch": {"retries": 0, "replan_count": replans + 1, "replanning": True, **r["patch"]}}
        return {"signals": ["retry"], "patch": patch}
    except Exception:
        return {"signals": ["retry"], "patch": {"retries": retries + 1}}

def node_satisfied(state, _):
    if "delegated_to" in state:
        return {"signals": ["idle"], "patch": {"satisfied": False, "delegated": True}}
    if state.get("plan_failed"):
        return {"signals": ["idle"], "patch": {"satisfied": False}}
    steps = state.get("plan", [])
    step = state.get("step", 0)
    if steps and step >= len(steps):
        return {"signals": ["idle"], "patch": {"satisfied": True}}
    return {"signals": ["idle"], "patch": {"satisfied": False}}

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
    if state.get("plan") and state.get("step", 0) >= len(state.get("plan", [])):
        append_trace(state)
    return {"signals": ["posted"], "patch": {}}

def _trigger_rod_run(slot, goal):
    """Wake a peer rod and start its autonomous loop."""
    port = http_port(int(slot))
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
        elif op == "set_observe":
            current.setdefault("observe", {})[payload["key"]] = payload["value"]
        elif op == "append_role_rule":
            role = str(payload.get("role", "")).strip()
            rule = str(payload.get("rule", "")).strip()
            roles = current.setdefault("prompts", {}).setdefault("roles", {})
            if not role or role not in roles:
                patch["last_error"] = f"unknown prompt role: {role}"
                return {"signals": ["modify_failed"], "patch": patch}
            if not rule:
                patch["last_error"] = "empty role rule"
                return {"signals": ["modify_failed"], "patch": patch}
            line = rule if rule.startswith("-") else f"- {rule}"
            if line not in roles[role]:
                roles[role] = roles[role].rstrip() + "\n" + line
        else:
            patch["last_error"] = f"unknown op: {op}"
            return {"signals": ["modify_failed"], "patch": patch}

        errs = validate_wiring(current)
        if errs:
            patch["last_error"] = wiring_error("self_modify_invalid") + ": " + "; ".join(errs[:5])
            return {"signals": ["modify_failed"], "patch": patch}

        # Write and hot-reload
        wiring_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        WIRING = current
        configure_runtime(WIRING)
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

# ─── Graph engine ───

def find_targets(node_id, signals, topo):
    targets = []
    for e in topo.get("edges", []):
        if e["from"] != node_id:
            continue
        if any(s in e["on"].split("|") for s in signals):
            targets.append(e["to"])
    return targets

def step_once(goal="", state=None, node_id=None):
    """Execute exactly one graph node and return a debuggable transition."""
    topo = WIRING["topology"]
    state = dict(state or {})
    if not state:
        if not goal:
            raise ValueError("goal required when state is empty")
        state = fresh_state(goal)
    if goal and not state.get("goal"):
        state["goal"] = goal
    node_id = node_id or state.pop("_resume_node", topo["cycle_start"])
    state.pop("_paused", None)
    node_cfg = topo_node_by_id(node_id)
    if not node_cfg:
        raise ValueError(f"dead end: no node '{node_id}'")
    handler = NODES.get(node_cfg["type"])
    if not handler:
        raise ValueError(f"no handler for type '{node_cfg['type']}'")

    before_debug = node_debug_context(node_id, state)
    sse_push("node", {"c": state.get("_cycle", 0) + 1, "id": node_id})
    result = handler(state, node_cfg)
    patch = result.get("patch", {})
    state.update(patch)
    signals = result.get("signals", [])
    targets = find_targets(node_id, signals, WIRING["topology"])
    next_node = targets[0] if targets else None
    terminal = (not next_node) or ("idle" in signals)
    state["_cycle"] = state.get("_cycle", 0) + 1
    state["_resume_node"] = node_id if terminal else next_node
    save_state(state)
    sse_push("result", {"c": state["_cycle"], "id": node_id, "s": signals})
    if terminal:
        sse_push("stop", {"outcome": state.get("satisfied", False)})
    next_debug = node_debug_context(next_node, state) if next_node else None
    return {
        "node": node_id,
        "type": node_cfg["type"],
        "executed": {
            "id": node_id,
            "type": node_cfg["type"],
            "label": node_cfg.get("label", ""),
            "circuit": before_debug.get("circuit", ""),
        },
        "signals": signals,
        "state_patch": patch,
        "state": state,
        "targets": targets,
        "next": None if terminal else next_node,
        "next_node": next_debug,
        "transition": {
            "from": node_id,
            "signals": signals,
            "targets": targets,
            "next": None if terminal else next_node,
            "terminal": terminal,
        },
        "debug": {
            "before": before_debug,
            "after": next_debug,
            "run": run_status_snapshot(),
        },
        "terminal": terminal,
        "satisfied": state.get("satisfied", False),
    }

def run(goal, resume_state=None, max_cycles=None):
    topo = WIRING["topology"]
    if resume_state:
        state = resume_state
        node_id = state.pop("_resume_node", topo["cycle_start"])
        state.pop("_paused", None)
    else:
        state = fresh_state(goal)
        node_id = topo["cycle_start"]
    cycle = 0
    max_cycles = max_cycles if max_cycles is not None else wiring_limit("max_cycles", 300)
    cycle_delay = int(WIRING.get("runtime", {}).get("cycle_delay_ms", 300)) / 1000.0

    print(f"\n{'='*50}\n  ROD [{WIRING.get('instance',{}).get('slot',0)}]: {goal}\n{'='*50}\n")

    while cycle < max_cycles:
        topo = WIRING["topology"]
        if run_pause_requested():
            print(f"\n[{cycle}] paused before {node_id}")
            return pause_run_state(state, node_id)
        cycle += 1
        node_cfg = topo_node_by_id(node_id)
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

        targets = find_targets(node_id, signals, topo)
        if not targets:
            state["_resume_node"] = node_id
            save_state(state)
            print(f"\n[{cycle}] terminal - no outgoing edge for {signals}")
            break
        node_id = targets[0]
        state["_resume_node"] = node_id
        save_state(state)
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
                "simulation": simulation_mode(),
                "permissions": WIRING.get("instance", {}).get("permissions", []),
                "run": run_status_snapshot(),
                "capabilities": wiring_summary().get("capabilities", {}),
            })
        elif self.path == "/wiring":
            self._j(WIRING)
        elif self.path == "/wiring-schema":
            try:
                self._j(json.loads((PROMPTS / "wiring-schema.json").read_text(encoding="utf-8")))
            except Exception as e:
                self._j({"error": str(e)}, 500)
        elif self.path == "/state":
            self._j(load_state() or {})
        elif self.path == "/bus":
            self._j(bus_read())
        elif self.path == "/smoke":
            # Programmatic smoke test — validates all endpoints work
            results = []
            try:
                nn = len(WIRING.get("topology", {}).get("nodes", []))
                werrs = validate_wiring(WIRING)
                entry_r = NODES.get("entry", lambda s, c: {})({"goal": "smoke"}, {})
                inspect_r = inspect_state(goal="smoke", state={}, node_id=WIRING.get("topology", {}).get("cycle_start"))
                summary = wiring_summary()
                mem_ok, mem_state, _ = apply_memory_action({}, "note", "value")
                mem_bad, _, _ = apply_memory_action({}, "note", "")
                results = [
                    {"test": "health", "ok": True},
                    {"test": "wiring", "ok": nn > 0, "nodes": nn},
                    {"test": "schema", "ok": (PROMPTS / "wiring-schema.json").exists()},
                    {"test": "wiring_valid", "ok": not werrs, "errors": len(werrs)},
                    {"test": "node/entry", "ok": "signals" in entry_r},
                    {"test": "inspect", "ok": bool(inspect_r.get("debug", {}).get("id"))},
                    {"test": "capability/step_debug", "ok": bool(summary.get("capabilities", {}).get("step_debug"))},
                    {"test": "capability/state_memory", "ok": bool(summary.get("capabilities", {}).get("state_memory"))},
                    {"test": "remember/store", "ok": mem_ok and mem_state.get("note") == "value"},
                    {"test": "remember/reject_empty", "ok": not mem_bad},
                    {"test": "html", "ok": (ROOT / "wiring-editor.html").exists()},
                ]
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
        cl = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(cl)) if cl > 0 else {}
        if self.path.startswith("/node/"):
            t = self.path[6:]
            h = NODES.get(t)
            if not h: self._j({"error": f"unknown: {t}"}, 404); return
            try:
                input_state = dict(body.get("state", {}))
                node_cfg = topo_node(t)
                before = node_debug_context(node_cfg.get("id"), input_state) if node_cfg else {"type": t}
                r = h(input_state, body.get("config", {}))
                patch = r.pop("patch", {})
                output_state = {**input_state, **patch}
                r["node_type"] = t
                r["state_patch"] = patch
                r["state"] = output_state
                r["debug"] = {
                    "before": before,
                    "after": node_debug_context(node_cfg.get("id"), output_state) if node_cfg else {"type": t},
                }
                if body.get("save"):
                    save_state(output_state)
                self._j(r)
            except Exception as e: self._j({"error": str(e)}, 500)
        elif self.path == "/step":
            try:
                self._j(step_once(
                    goal=body.get("goal", ""),
                    state=body.get("state"),
                    node_id=body.get("node"),
                ))
            except Exception as e:
                self._j({"error": str(e)}, 500)
        elif self.path == "/inspect":
            try:
                self._j(inspect_state(
                    goal=body.get("goal", ""),
                    state=body.get("state"),
                    node_id=body.get("node"),
                ))
            except Exception as e:
                self._j({"error": str(e)}, 500)
        elif self.path == "/state":
            state_body = body.get("state") if isinstance(body, dict) and "state" in body else body
            if not isinstance(state_body, dict):
                self._j({"error": "state must be object"}, 400); return
            save_state(state_body)
            self._j({"saved": True, "state": state_body})
        elif self.path == "/run":
            goal = body.get("goal", "")
            if not goal: self._j({"error": "no goal"}, 400); return
            self._j(enqueue_run(goal))
        elif self.path == "/resume":
            s = load_state()
            if not s: self._j({"error": "no saved state"}, 404); return
            s.pop("_paused", None)
            queued = enqueue_run(s.get("goal",""), resume_state=s)
            self._j({"resumed": True, "goal": s.get("goal",""), **queued})
        elif self.path == "/pause":
            self._j(request_pause())
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
        elif self.path == "/push":
            # AI/external push: send arbitrary data to dashboard via SSE
            sse_push("push", body)
            self._j({"pushed": True})
        elif self.path == "/wiring":            # Hot-reload: POST new wiring.json (validates against schema)
            if not body:
                self._j({"error": "wiring body required"}, 400)
                return
            errs = validate_wiring(body)
            if errs:
                self._j({"error": "validation failed", "details": errs}, 400)
                return
            try:
                (PROMPTS / "wiring.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
                WIRING = body
                apply_instance_env()
                configure_runtime(WIRING)
                sse_push("wiring_modified", {"source": "api"})
                self._j({
                    "reloaded": True,
                    "nodes": len(WIRING.get("topology", {}).get("nodes", [])),
                    "summary": wiring_summary(),
                    "run": run_status_snapshot(),
                })
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
    port = int(args[0]) if args and args[0].isdigit() else http_port()
    srv = ThreadingHTTPServer((http_bind(), port), H)
    print_listen_urls(port)

    if "--resume" in args:
        s = load_state()
        if not s: print("No state.json to resume from"); sys.exit(1)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        run(s.get("goal", ""), s)
    elif "--run" in args:
        idx = args.index("--run")
        max_c = int(args[args.index("--max-cycles") + 1]) if "--max-cycles" in args else None
        goal_parts = []
        i = idx + 1
        while i < len(args):
            if args[i] == "--max-cycles": i += 2; continue
            if args[i].startswith("--"): break
            goal_parts.append(args[i]); i += 1
        goal = " ".join(goal_parts)
        if not goal: print("Usage: python server.py --run \"goal\" [--max-cycles N]"); sys.exit(1)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        run(goal, max_cycles=max_c)
    else:
        print(f"endgame-ai [{WIRING.get('instance',{}).get('slot',0)}] port={port} nodes: {list(NODES.keys())}")
        srv.serve_forever()
