"""Runtime helpers for endgame-ai's exec-node architecture.

The engine owns graph walking and HTTP. Nodes are bare scripts that receive these
helpers in their exec namespace and set `signals` plus `patch`.
"""
from __future__ import annotations

import base64
import fnmatch
import json
import os
import pathlib
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
PROMPTS = ROOT / "prompts"
NODES_DIR = ROOT / "nodes"
WIRING_PATH = pathlib.Path(os.environ.get("ENDGAME_WIRING", str(PROMPTS / "wiring.json")))
if not WIRING_PATH.is_absolute():
    WIRING_PATH = (ROOT / WIRING_PATH).resolve()
STATE_FILE = pathlib.Path(os.environ.get("ENDGAME_STATE", str(ROOT / "state.json")))
if not STATE_FILE.is_absolute():
    STATE_FILE = (ROOT / STATE_FILE).resolve()
BUS_FILE = pathlib.Path(os.environ.get("ENDGAME_BUS", str(ROOT / "bus.json")))
if not BUS_FILE.is_absolute():
    BUS_FILE = (ROOT / BUS_FILE).resolve()
MODEL_PATH = pathlib.Path(os.environ.get("ENDGAME_MODEL", str(PROMPTS / "model.json")))
if not MODEL_PATH.is_absolute():
    MODEL_PATH = (ROOT / MODEL_PATH).resolve()
TRACES_FILE = PROMPTS / "traces.jsonl"
CODEBASE_SNAPSHOT = ROOT / "codebase_snapshot.txt"

EVENTS: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=1000)
_LAST_STATE: dict[str, Any] = {}
_MODEL_LOCK = threading.RLock()

TEXT_SUFFIXES = {
    ".py", ".json", ".html", ".htm", ".css", ".js", ".md", ".txt",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".bat", ".ps1", ".sh"
}
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "venv", ".venv", "node_modules", "dist", "build"}
EXCLUDE_FILES = {"state.json", "bus.json", "codebase_snapshot.txt"}
EXCLUDE_PATTERNS = ["*.pyc", "*.pyo", "*.zip", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.ico", "*.exe", "*.dll", "*.so"]

DEFAULT_BASE_PROMPT = 'You are a circuit inside Endgame-AI, a local closed-loop desktop automation controller.\nYou are not a general chat assistant. You transform the provided runtime state into the exact machine record required by your circuit.\n\nGLOBAL OUTPUT CONTRACT\n- Output exactly one JSON object and nothing else: no markdown, no code fences, no comments, no apologies, no prose outside JSON.\n- Use only the record_type and data schema required by your role.\n- Never invent verbs, node signals, patch operations, function names, Python calls, UI endpoints, or extra top-level keys.\n- Treat SCREEN as the current truth. Treat HISTORY, MEMORY, and LAST_ERROR as helpful but possibly stale.\n- The engine routes node signals; your JSON does not choose graph edges directly.\n- Verification decides completion. The actor must never declare a task DONE.\n- Coordinates are not part of the action contract. Refer to visible element IDs/tokens/names from SCREEN or to window titles.'

DEFAULT_ROLE_PROMPTS = {'planner': 'ROLE: Agentic Planner / Task Decomposer.\n\nCAPABILITY\nYou convert a human GOAL into an ordered plan for a desktop agent. You do not click, type, verify, or self-modify.\n\nREQUIRED JSON\n{"record_type":"task","data":{"steps":[{"description":"...","done_when":"..."}]}}\n\nPLANNING RULES\n- Produce 1 to 8 steps.\n- Each step must be a small action objective that the actor can execute using the allowed desktop verbs.\n- description: imperative, concrete, and independent enough for one observe-act-verify loop.\n- done_when: observable evidence from the screen, window title, saved state, memory, or verb outcome.\n- Do not include invented fields. Do not put actions arrays here.\n- Prefer direct app/navigation steps over vague exploration.\n- If the goal is already satisfied from context, still return one verification-oriented step with observable done_when.', 'unified': 'ROLE: Agentic Actor / Desktop Verb Controller.\n\nCAPABILITY\nYou choose executable desktop verb calls for the current SUBTASK using SCREEN. You are the only LLM role allowed to emit actions.\n\nREQUIRED JSON\n{"record_type":"action","data":{"conclusion":"EXECUTE","actions":[{"verb":"click","target":"...","value":""}]}}\nOR\n{"record_type":"action","data":{"conclusion":"CANNOT","actions":[]}}\n\nALLOWED VERBS\n- click: target = visible element id/token/name. value = empty. Clicks the resolved UI element.\n- write: target = writable element id/name, or empty to write into current focus. value = exact text to type. Existing text is selected first.\n- press: target = empty. value = one key such as enter, tab, esc, backspace, delete, up, down, left, right, space.\n- hotkey: target = empty. value = keys joined by + or comma, such as ctrl+l, ctrl+s, alt+tab, win+r.\n- focus: target = visible window token/title. value = empty. Brings that window to foreground.\n- open_url: target = optional browser/app name. value = full URL or domain/path to open.\n- scroll: target = scrollable element id/name. value = signed integer wheel amount; positive/negative direction depends on platform.\n- wait: target = empty. value = milliseconds from 100 to 30000.\n- launch: target or value = app command/name such as notepad, chrome, opera, calc.\n- remember: target = memory key. value = information to persist for later steps.\n- llm_request: target = external request label. value = exact prompt/request for the relay/browser-AI slot.\n- llm_wait_response: target = empty. value = empty. Waits for relay/browser-AI response and stores it in memory.\n- copy_codebase: target = empty. value = empty. Writes and copies a full codebase snapshot.\n- browser_ai_handoff: target = optional browser-AI label. value = exact request to hand over to browser AI such as Grok. The executor opens/focuses the browser AI, submits the request, waits, and stores the response in MEMORY.grok_response.\n\nBROWSER-AI HANDOVER RULES\n- Use browser_ai_handoff when the user explicitly asks to hand control/work to Grok or another browser AI.\n- After handoff, local LM Studio remains the desktop operator/fallback: if Grok is closed or UI changes, reopen/focus browser AI and resubmit the current request.\n- Do not invent Grok responses; wait for browser_ai_handoff or llm_wait_response evidence.\n\nACTION RULES\n- conclusion must be EXECUTE when actions is non-empty, otherwise CANNOT with actions=[].\n- Never output DONE, FINISHED, SUCCESS, VERIFY, or raw Python. Completion is verifier\'s job.\n- Use only the verbs above exactly as spelled.\n- Prefer 1 to 3 actions. Use a short chain only when the actions are causally immediate.\n- Use wait after launch/open_url or when the UI is loading.\n- If an element token like [12] is visible, prefer that exact token as target.\n- If the target is ambiguous, choose a focus/click step that reduces ambiguity rather than inventing a target.\n- For text entry: focus/click the writable target first if needed, then write, then press enter only if submission is required.\n- For codebase or self-improvement workflows, use copy_codebase only when the step explicitly needs the repository snapshot.', 'verifier': 'ROLE: Verifier / Evidence Judge.\n\nCAPABILITY\nYou decide whether the current step\'s DONE_WHEN condition is satisfied using SCREEN, LAST_ACTIONS, LAST_OUTCOME, MEMORY, and visible evidence. You do not execute actions.\n\nREQUIRED JSON\n{"record_type":"verdict","data":{"confirmed":true,"evidence":"...","reason":"..."}}\n\nVERIFICATION RULES\n- confirmed must be true only when evidence is concrete and directly matches DONE_WHEN.\n- confirmed must be false when evidence is missing, ambiguous, contradicted, or only predicted.\n- evidence: short factual observation, outcome text, or memory key that supports the verdict.\n- reason: explain the match or the gap in one sentence.\n- Do not invent observations. SCREEN and LAST_OUTCOME are the source of truth.\n- Do not output actions, plans, or patch ops.', 'reflector': 'ROLE: Reflector / Failure Diagnostician.\n\nCAPABILITY\nYou analyze why the last action or verification failed and decide whether the scheduler should retry the same step or planner should replan. You do not execute actions.\n\nREQUIRED JSON\n{"record_type":"diagnosis","data":{"diagnosis":"...","suggestion":"...","should_replan":false}}\n\nREFLECTION RULES\n- diagnosis: concrete cause of failure from LAST_ERROR, HISTORY, SCREEN, or MEMORY.\n- suggestion: one tactical correction for the next attempt.\n- should_replan = false when the same step can be retried with a better target, wait, focus, or verb choice.\n- should_replan = true only when the current step is structurally wrong, impossible, or missing prerequisites.\n- Do not output actions arrays or wiring patches.', 'self_modify': 'ROLE: Self-Modify / Wiring Patch Engineer.\n\nCAPABILITY\nYou propose exactly one safe graph/prompt/node-file modification when repeated execution failures show the current wiring is insufficient. You do not run desktop actions.\n\nREQUIRED JSON\n{"record_type":"wiring_patch","data":{"op":"add_edge","payload":{"from":"node_id","to":"node_id","on":"signal"}}}\n\nSUPPORTED OPS AND PAYLOADS\n- add_node: {"id":"node_id","type":"node_type","label":"Label","code":"optional python node code","overwrite":false,"edge_from":"optional_node","on":"signal","edge_to":"optional_node","edge_to_on":"signal"}\n- create_node_file: {"type":"node_type","code":"python code","overwrite":false}\n- update_node: {"id":"node_id","set":{"label":"...","type":"...","circuit":"...","prompt":{}}}\n- remove_node: {"id":"node_id"}\n- add_edge: {"from":"node_id","to":"node_id","on":"signal"}\n- remove_edge: {"from":"node_id","to":"node_id","on":"optional_signal"}\n- add_rule: {"rule":{"id":"rule_id","phase":"verify|act","verdict":"confirm|reject","description":"...","match":{}}}\n- update_rule: {"id":"rule_id","set":{}}\n- remove_rule: {"id":"rule_id"}\n- set_limit: {"key":"limit_name","value":1}\n- set_guard: {"key":"guard_name","value":true}\n- set_observe: {"key":"observe_name","value":1}\n- set_prompt_base: {"text":"complete replacement base prompt"}\n- set_role: {"role":"planner|unified|verifier|reflector|self_modify","text":"complete replacement role prompt"}\n- append_role_rule: {"role":"planner|unified|verifier|reflector|self_modify","rule":"one additional rule"}\n\nPATCH RULES\n- Emit one op only.\n- Never remove goal_inbox, planner, scheduler, observe, act, verify, reflect, self_modify, bus_post, or satisfied unless the goal explicitly asks for a destructive refactor.\n- Node ids and types must be Python/wiring identifiers: letters, numbers, underscore; ids may also use hyphen.\n- Python code for create_node_file/add_node must be a complete exec-node script that sets patch and signals.\n- Preserve existing contracts unless fixing a specific failure.\n- Prefer prompt or wiring patches over large code patches.'}

DEFAULT_VERBS = {'click': {'target_field': 'target', 'value_field': 'value', 'requires_target': True, 'description': 'Click a resolved visible UI element by id/token/name.'}, 'write': {'target_field': 'target', 'value_field': 'value', 'requires_value': True, 'description': 'Type text into target or current focus after Ctrl+A.'}, 'press': {'key_field': 'value', 'description': 'Press one key named in value.'}, 'hotkey': {'key_field': 'value', 'description': 'Press a key chord in value, e.g. ctrl+l.'}, 'focus': {'title_field': 'target', 'description': 'Focus a window by token/title.'}, 'open_url': {'browser_field': 'target', 'url_field': 'value', 'requires_value': True, 'description': 'Open a URL/domain, optionally in a named browser.'}, 'scroll': {'target_field': 'target', 'amount_field': 'value', 'requires_target': True, 'description': 'Scroll a resolved element by signed wheel amount.'}, 'wait': {'amount_field': 'value', 'description': 'Wait milliseconds, clamped 100..30000.'}, 'launch': {'target_field': 'target', 'value_field': 'value', 'description': 'Launch an app command/name.'}, 'remember': {'target_field': 'target', 'value_field': 'value', 'description': 'Store value in memory[target].'}, 'llm_request': {'target_field': 'target', 'value_field': 'value', 'description': 'Write a request for the external LLM relay.'}, 'llm_wait_response': {'target_field': 'target', 'value_field': 'value', 'description': 'Wait for external LLM response and store it in memory.'}, 'copy_codebase': {'target_field': 'target', 'value_field': 'value', 'description': 'Write/copy a full repository snapshot.'}, 'browser_ai_handoff': {'target_field': 'target', 'value_field': 'value', 'description': 'Open a browser AI chat, submit a request, and return/store its response.'}}


# ─── IO ────────────────────────────────────────────────────────────────────

def atomic_write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def atomic_write_json(path: pathlib.Path, data: Any, indent: int | None = 2) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=indent))


def read_json(path: pathlib.Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + f".bad.{int(time.time())}")
        try:
            shutil.copyfile(path, backup)
        except OSError:
            pass
        return default


def load_wiring() -> dict[str, Any]:
    w = read_json(WIRING_PATH, {})
    if not w:
        w = default_wiring()
        save_wiring(w)
    slot = os.environ.get("ENDGAME_SLOT")
    perms = os.environ.get("ENDGAME_PERMISSIONS")
    if slot is not None or perms is not None:
        inst = dict(w.get("instance", {}))
        if slot is not None:
            try:
                inst["slot"] = int(slot)
            except ValueError:
                inst["slot"] = slot
        if perms is not None:
            inst["permissions"] = [p.strip() for p in perms.split(",") if p.strip()]
        w = {**w, "instance": inst}
    return w


def save_wiring(wiring: dict[str, Any]) -> None:
    atomic_write_json(WIRING_PATH, wiring, indent=2)


def load_model() -> dict[str, Any]:
    with _MODEL_LOCK:
        return read_json(MODEL_PATH, default_model())


def save_model(model: dict[str, Any]) -> None:
    with _MODEL_LOCK:
        atomic_write_json(MODEL_PATH, model, indent=2)


def load_state() -> dict[str, Any]:
    return read_json(STATE_FILE, {})


def save_state(state: dict[str, Any]) -> None:
    global _LAST_STATE
    _LAST_STATE = dict(state or {})
    atomic_write_json(STATE_FILE, state, indent=2)


def remember_state(state: dict[str, Any]) -> None:
    global _LAST_STATE
    _LAST_STATE = dict(state or {})


def last_state() -> dict[str, Any]:
    return dict(_LAST_STATE or load_state() or {})


def sse_push(kind: str, payload: dict[str, Any] | None = None) -> None:
    item = {"type": kind, "payload": payload or {}, "ts": time.time()}
    try:
        EVENTS.put_nowait(item)
    except queue.Full:
        try:
            EVENTS.get_nowait()
            EVENTS.put_nowait(item)
        except queue.Empty:
            pass

# ─── Defaults ──────────────────────────────────────────────────────────────

def default_model() -> dict[str, Any]:
    return {
        "transport": "openai",
        "host": "http://localhost:1234",
        "model": "nvidia-nemotron-3-nano-4b",
        "temperature": 0.3,
        "max_tokens": 2048,
        "timeout": 900,
        "file_proxy": {
            "request_path": "comms/slot1_cognition/request.json",
            "response_path": "comms/slot1_cognition/response.json",
            "archive_dir": "comms/slot1_cognition/archive",
            "poll_interval_ms": 1000,
        },
        "browser_ai": {
            "browser": "opera",
            "url": "https://grok.com",
            "domain": "grok.com",
            "open_wait_ms": 5000,
            "response_wait_ms": 15000,
            "response_min_chars": 20,
            "retries": 2,
            "submit_key": "enter",
            "input_hints": ["ask", "message", "prompt", "chat", "grok", "anything", "what do you want"],
        },
    }


def default_wiring() -> dict[str, Any]:
    return {
        "schema": "endgame-topology/v1",
        "instance": {"slot": 1, "permissions": ["desktop_exec"]},
        "moe": {"required_permission": "desktop_exec", "delegate_keywords": ["chrome", "browser", "grok"], "default_exec_slot": 1},
        "topology": {
            "cycle_start": "goal_inbox",
            "nodes": [
                {"id": "goal_inbox", "type": "entry", "label": "Goal input"},
                {"id": "moe_route", "type": "moe_route", "label": "Route goal to slot"},
                {"id": "planner", "type": "planner", "label": "Decompose goal → steps", "circuit": "planner"},
                {"id": "scheduler", "type": "scheduler", "label": "Next step or done"},
                {"id": "bus_check", "type": "bus_check", "label": "Poll bus"},
                {"id": "observe", "type": "observe", "label": "Screen capture"},
                {"id": "act", "type": "act", "label": "LLM decide + execute", "circuit": "unified"},
                {"id": "verify", "type": "verify", "label": "Verify evidence", "circuit": "verifier"},
                {"id": "reflect", "type": "reflect", "label": "Diagnose", "circuit": "reflector"},
                {"id": "self_modify", "type": "self_modify", "label": "Alter own wiring", "circuit": "self_modify"},
                {"id": "copy_codebase", "type": "copy_codebase", "label": "Copy full codebase"},
                {"id": "satisfied", "type": "satisfied", "label": "Rest"},
                {"id": "bus_post", "type": "bus_post", "label": "Post telemetry"},
                {"id": "llm_request_check", "type": "llm_request_check", "label": "Relay request check"},
                {"id": "llm_response_write", "type": "llm_response_write", "label": "Relay response write"},
            ],
            "edges": [
                {"from": "goal_inbox", "to": "moe_route", "on": "ready"},
                {"from": "moe_route", "to": "planner", "on": "self"},
                {"from": "moe_route", "to": "bus_post", "on": "delegated"},
                {"from": "planner", "to": "scheduler", "on": "plan_ready"},
                {"from": "planner", "to": "planner", "on": "retry_plan"},
                {"from": "planner", "to": "bus_post", "on": "plan_failed"},
                {"from": "scheduler", "to": "bus_check", "on": "step_ready"},
                {"from": "scheduler", "to": "bus_post", "on": "plan_complete"},
                {"from": "bus_post", "to": "satisfied", "on": "posted"},
                {"from": "bus_check", "to": "observe", "on": "no_interrupt"},
                {"from": "bus_check", "to": "planner", "on": "interrupt"},
                {"from": "observe", "to": "act", "on": "screen_ready"},
                {"from": "act", "to": "verify", "on": "acted"},
                {"from": "act", "to": "reflect", "on": "act_failed"},
                {"from": "verify", "to": "scheduler", "on": "step_confirmed"},
                {"from": "verify", "to": "reflect", "on": "step_denied"},
                {"from": "reflect", "to": "scheduler", "on": "retry"},
                {"from": "reflect", "to": "planner", "on": "replan"},
                {"from": "reflect", "to": "self_modify", "on": "escalate"},
                {"from": "reflect", "to": "bus_post", "on": "give_up"},
                {"from": "self_modify", "to": "planner", "on": "modified"},
                {"from": "self_modify", "to": "reflect", "on": "modify_failed"},
                {"from": "copy_codebase", "to": "satisfied", "on": "copied"},
            ],
        },
        "prompts": {"base": DEFAULT_BASE_PROMPT, "roles": dict(DEFAULT_ROLE_PROMPTS)},
        "reasoning": {
            "store_as": {"planner": "planner", "unified": "act", "verifier": "verify", "reflector": "reflect", "self_modify": "self_modify"},
            "expected_record_type": {"planner": "task", "unified": "action", "verifier": "verdict", "reflector": "diagnosis", "self_modify": "wiring_patch"},
            "chain_depth": 32,
            "clear_on_step_confirm": ["verify", "reflect", "act"],
        },
        "runtime": {
            "http_port_base": 9077,
            "http_port_slot_offset": True,
            "http_bind": "0.0.0.0",
            "cycle_delay_ms": 300,
            "action_chain_delay_ms": 120,
            "llm_request_path": "comms/llm_proxy/request.json",
            "llm_response_path": "comms/llm_proxy/response.json",
            "llm_archive_dir": "comms/llm_proxy/archive",
            "llm_wait_timeout_ms": 60000,
            "llm_response_memory_key": "llm_response",
            "llm_response_min_chars": 20,
            "initial_state": {"step": 0, "retries": 0, "history": [], "memory": {}, "reasoning": {}, "reasoning_chain": [], "last_error": ""},
        },
        "act": {"valid_conclusions": ["EXECUTE", "CANNOT"], "reject_conclusions": ["DONE", "FINISHED", "SUCCESS", "VERIFY"], "verb_normalize": []},
        "errors": {
            "parse_failed": "parse_failed: respond with JSON only",
            "act_done_rejected": "DONE is invalid — output EXECUTE with one action; verify confirms step completion",
            "act_cannot": "CANNOT",
            "act_bad_conclusion": "bad conclusion: {conclusion}",
            "act_unknown_verb": "unknown verb: {verb}; use only the allowed verb contract",
            "act_bad_action_shape": "bad action object: each action needs verb plus target/value strings",
            "planner_parse_failed": "planner: parse_failed — respond with JSON only",
            "planner_empty": "planner: empty plan",
            "self_modify_invalid": "LLM returned invalid patch",
        },
        "limits": {"max_attempts": 7, "max_replans": 3, "max_self_modify": 3, "max_cycles": 300, "history_depth": 40, "planner_retries": 3, "llm_parse_retries": 2, "context_window_tokens": 17920, "context_reserve_tokens": 2560},
        "verbs": {k: dict(v) for k, v in DEFAULT_VERBS.items()},
        "observe": {"min_elements": 3, "wait_retries": 6, "wait_ms": 750, "post_action_delay_ms": 250},
        "rules": [
            {"id": "confirm_remember_action", "phase": "verify", "verdict": "confirm", "description": "Remember verb has no side effect; OK=data captured", "match": {"outcome_ok": True, "actions_all_verb": "remember"}},
            {"id": "confirm_copy_codebase", "phase": "verify", "verdict": "confirm", "description": "Codebase snapshot copied/written", "match": {"outcome_ok": True, "actions_include_verb": "copy_codebase"}},
            {"id": "confirm_llm_request_written", "phase": "verify", "verdict": "confirm", "description": "llm_request wrote external-AI handoff file", "match": {"outcome_ok": True, "actions_include_verb": "llm_request"}},
            {"id": "confirm_browser_ai_handoff", "phase": "verify", "verdict": "confirm", "description": "Browser-AI handoff returned a stored response", "match": {"outcome_ok": True, "actions_include_verb": "browser_ai_handoff"}},
        ],
    }

# ─── Config / topology ─────────────────────────────────────────────────────

def http_port(wiring: dict[str, Any] | None = None, slot: int | None = None) -> int:
    wiring = wiring or load_wiring()
    rt = wiring.get("runtime", {})
    base = int(rt.get("http_port_base", 9077))
    if slot is None:
        slot = int(wiring.get("instance", {}).get("slot", 1) or 1)
    return base + (slot - 1 if rt.get("http_port_slot_offset", True) else 0)


def wiring_limit(key: str, default: int = 0, wiring: dict[str, Any] | None = None) -> int:
    wiring = wiring or load_wiring()
    try:
        return int(wiring.get("limits", {}).get(key, default))
    except (TypeError, ValueError):
        return default


def wiring_error(key: str, wiring: dict[str, Any] | None = None, **kwargs: Any) -> str:
    wiring = wiring or load_wiring()
    text = wiring.get("errors", {}).get(key, key)
    try:
        return str(text).format(**kwargs)
    except Exception:
        return str(text)


def topo_node_by_id(node_id: str, wiring: dict[str, Any] | None = None) -> dict[str, Any] | None:
    wiring = wiring or load_wiring()
    for n in wiring.get("topology", {}).get("nodes", []):
        if n.get("id") == node_id:
            return n
    return None


def find_targets(node_id: str, signals: list[str], topo: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for e in topo.get("edges", []):
        if e.get("from") != node_id:
            continue
        ons = [s.strip() for s in str(e.get("on", "")).split("|")]
        if "*" in ons or any(s in ons for s in signals):
            targets.append(e.get("to"))
    return [t for t in targets if t]


def available_node_types() -> list[str]:
    NODES_DIR.mkdir(exist_ok=True)
    return sorted(p.stem for p in NODES_DIR.glob("*.py") if p.name != "__init__.py")


def wiring_summary(wiring: dict[str, Any] | None = None) -> dict[str, Any]:
    wiring = wiring or load_wiring()
    topo = wiring.get("topology", {})
    return {
        "schema": wiring.get("schema"),
        "path": str(WIRING_PATH),
        "nodes": len(topo.get("nodes", [])),
        "edges": len(topo.get("edges", [])),
        "node_types": available_node_types(),
        "cycle_start": topo.get("cycle_start"),
        "port": http_port(wiring),
    }


def validate_wiring(wiring: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    topo = wiring.get("topology")
    if not isinstance(topo, dict):
        return ["topology must be object"]
    nodes = topo.get("nodes", [])
    edges = topo.get("edges", [])
    if not isinstance(nodes, list):
        errs.append("topology.nodes must be array")
        nodes = []
    ids: set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errs.append(f"nodes[{i}] must be object")
            continue
        nid = n.get("id")
        ntype = n.get("type")
        if not isinstance(nid, str) or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-]*$", nid):
            errs.append(f"nodes[{i}].id invalid")
        if nid in ids:
            errs.append(f"duplicate node id {nid}")
        ids.add(nid)
        if not isinstance(ntype, str) or not ntype:
            errs.append(f"node {nid}.type missing")
    if topo.get("cycle_start") not in ids:
        errs.append("topology.cycle_start must reference a node")
    if not isinstance(edges, list):
        errs.append("topology.edges must be array")
        edges = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errs.append(f"edges[{i}] must be object")
            continue
        if e.get("from") not in ids or e.get("to") not in ids:
            errs.append(f"edge {i} references unknown node")
        if not e.get("on"):
            errs.append(f"edge {i}.on missing")
    return errs


def node_debug_context(node_id: str | None, state: dict[str, Any], wiring: dict[str, Any] | None = None) -> dict[str, Any]:
    wiring = wiring or load_wiring()
    if not node_id:
        return {}
    node_cfg = topo_node_by_id(node_id, wiring)
    if not node_cfg:
        return {"id": node_id, "error": f"unknown node: {node_id}"}
    topo = wiring.get("topology", {})
    return {
        "id": node_id,
        "type": node_cfg.get("type"),
        "label": node_cfg.get("label", ""),
        "circuit": circuit_for_node(node_cfg),
        "config": node_cfg,
        "incoming_edges": [e for e in topo.get("edges", []) if e.get("to") == node_id],
        "outgoing_edges": [e for e in topo.get("edges", []) if e.get("from") == node_id],
        "wired_inputs": resolve_prompt_blocks(node_cfg, state, wiring),
        "reasoning": state.get("reasoning", {}),
        "reasoning_chain": state.get("reasoning_chain", []),
    }


def fresh_state(goal: str, wiring: dict[str, Any] | None = None) -> dict[str, Any]:
    wiring = wiring or load_wiring()
    state = dict(wiring.get("runtime", {}).get("initial_state", {}) or {})
    state["goal"] = goal
    state.setdefault("step", 0)
    state.setdefault("retries", 0)
    state.setdefault("history", [])
    state.setdefault("memory", {})
    state.setdefault("reasoning", {})
    state.setdefault("reasoning_chain", [])
    state.setdefault("last_error", "")
    return state

# ─── Prompting / LLM ───────────────────────────────────────────────────────

def circuit_for_node(node_cfg: dict[str, Any]) -> str:
    if node_cfg.get("circuit"):
        return str(node_cfg.get("circuit"))
    mapping = {"planner": "planner", "act": "unified", "verify": "verifier", "reflect": "reflector", "self_modify": "self_modify"}
    return mapping.get(str(node_cfg.get("type", "")), str(node_cfg.get("type", "")))


def _get_path_value(data: Any, path: str, wiring: dict[str, Any]) -> Any:
    if path == "traces.recent":
        return recent_traces(wiring_limit("trace_few_shot", 6, wiring))
    if path == "topology.nodes":
        return wiring.get("topology", {}).get("nodes", [])
    if path == "topology.summary":
        return wiring_summary(wiring)
    if path == "reasoning.chain":
        return data.get("reasoning_chain", [])
    cur: Any = data
    parts = path.split(".")
    if parts and parts[0] == "state":
        cur = data
        parts = parts[1:]
    elif parts and parts[0] == "reasoning":
        cur = data.get("reasoning", {})
        parts = parts[1:]
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        else:
            return None
    return cur


def _render_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, indent=2)


def resolve_prompt_blocks(node_cfg: dict[str, Any], state: dict[str, Any], wiring: dict[str, Any] | None = None) -> list[dict[str, str]]:
    wiring = wiring or load_wiring()
    blocks = node_cfg.get("prompt", {}).get("user", {}).get("blocks")
    if not blocks:
        # Default blocks per circuit.
        circuit = circuit_for_node(node_cfg)
        defaults = {
            "planner": [("GOAL", "state.goal"), ("LAST_ERROR", "state.last_error"), ("HISTORY", "state.history"), ("MEMORY", "state.memory")],
            "unified": [("SUBTASK", "state.step_goal"), ("DONE_WHEN", "state.current_step.done_when"), ("SCREEN", "state.screen"), ("LAST_ERROR", "state.last_error"), ("MEMORY", "state.memory")],
            "verifier": [("STEP", "state.current_step.description"), ("DONE_WHEN", "state.current_step.done_when"), ("SCREEN", "state.screen"), ("LAST_ACTIONS", "state.last_actions"), ("LAST_OUTCOME", "state.last_outcome"), ("MEMORY", "state.memory")],
            "reflector": [("GOAL", "state.goal"), ("STEP", "state.current_step.description"), ("LAST_ERROR", "state.last_error"), ("HISTORY", "state.history"), ("MEMORY", "state.memory")],
            "self_modify": [("GOAL", "state.goal"), ("LAST_ERROR", "state.last_error"), ("CURRENT_WIRING", "topology.summary"), ("CURRENT_NODES", "topology.nodes")],
        }
        blocks = [{"label": label, "source": source} for label, source in defaults.get(circuit, [])]
    out = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        label = str(b.get("label", "VALUE"))
        value = _get_path_value(state, str(b.get("source", "")), wiring)
        text = _render_value(value)
        if text or b.get("always"):
            out.append({"label": label, "value": text or str(b.get("empty_template", ""))})
    return out


def build_user_message(circuit: str, state: dict[str, Any], node_cfg: dict[str, Any] | None = None, wiring: dict[str, Any] | None = None) -> str:
    wiring = wiring or load_wiring()
    node_cfg = node_cfg or {"type": circuit, "circuit": circuit}
    body = []
    for item in resolve_prompt_blocks(node_cfg, state, wiring):
        body.append(f"{item['label']}:\n{item['value']}")
    return "\n\n".join(body)


def load_system_prompt(circuit: str, state: dict[str, Any] | None = None, node_cfg: dict[str, Any] | None = None, wiring: dict[str, Any] | None = None) -> str:
    wiring = wiring or load_wiring()
    prompts = wiring.get("prompts", {})
    base = prompts.get("base", "")
    role = prompts.get("roles", {}).get(circuit, prompts.get("roles", {}).get(str(circuit), ""))
    return (base + "\n\n" + role).strip()


def llm(system: str, user: str, temperature: float | None = None, model_override: dict[str, Any] | None = None) -> tuple[str, str]:
    model = {**load_model(), **(model_override or {})}
    transport = model.get("transport", "openai")
    if transport == "file_proxy":
        return llm_file_proxy(system, user, model)
    if transport == "browser_ai":
        return llm_browser_ai(system, user, model)
    return llm_openai_compatible(system, user, model, temperature)


def llm_openai_compatible(system: str, user: str, model: dict[str, Any], temperature: float | None = None) -> tuple[str, str]:
    host = str(model.get("host", "http://localhost:1234")).rstrip("/")
    url = host + "/v1/chat/completions"
    payload = {
        "model": model.get("model", "local-model"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": model.get("temperature", 0.3) if temperature is None else temperature,
        "max_tokens": model.get("max_tokens", 2048),
        "stream": False,
    }
    for key in ("top_p", "presence_penalty", "frequency_penalty", "stop"):
        if key in model:
            payload[key] = model[key]
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    timeout = float(model.get("timeout", 120))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8", errors="replace"))
        msg = resp.get("choices", [{}])[0].get("message", {})
        return msg.get("content", ""), msg.get("reasoning_content", "")
    except Exception as e:
        raise RuntimeError(f"llm_openai: {e}")


def _llm_response_content(resp: dict[str, Any]) -> str:
    """Read both compact and OpenAI-compatible file-proxy response shapes."""
    if not isinstance(resp, dict):
        return ""
    choices = resp.get("choices")
    if isinstance(choices, list) and choices:
        msg = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            return str(msg.get("content") or msg.get("reasoning_content") or "")
    return str(resp.get("content") or resp.get("response") or resp.get("text") or "")


def _new_llm_request_id() -> str:
    return f"llm-{int(time.time() * 1000)}-{os.getpid()}-{threading.get_ident() % 100000}"


def llm_file_proxy(system: str, user: str, model: dict[str, Any]) -> str:
    """File handoff transport for any outside AI agent.

    The engine writes an OpenAI-like request.json with status=pending and waits for
    a response.json.  Older compact response formats remain accepted so existing
    agents do not break.
    """
    cfg = model.get("file_proxy", {})
    req_path = ROOT / cfg.get("request_path", "comms/slot1_cognition/request.json")
    resp_path = ROOT / cfg.get("response_path", "comms/slot1_cognition/response.json")
    archive = ROOT / cfg.get("archive_dir", "comms/slot1_cognition/archive")
    archive.mkdir(parents=True, exist_ok=True)
    req_path.parent.mkdir(parents=True, exist_ok=True)
    resp_path.parent.mkdir(parents=True, exist_ok=True)
    request_id = _new_llm_request_id()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    request_payload = {
        "id": request_id,
        "status": "pending",
        "created_at": time.time(),
        "transport": "file_proxy",
        "model": model.get("model"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # Backward-compatible fields for simple watchers.
        "system": system,
        "user": user,
    }
    atomic_write_json(req_path, request_payload, indent=2)
    deadline = time.time() + float(model.get("timeout", 120))
    poll = max(0.05, int(cfg.get("poll_interval_ms", 1000)) / 1000.0)
    while time.time() < deadline:
        if resp_path.exists():
            resp = read_json(resp_path, {})
            if resp.get("id") not in (None, "", request_id):
                time.sleep(poll)
                continue
            content = _llm_response_content(resp)
            try:
                archived_req = archive / f"request.{stamp}.{request_id}.json"
                archived_resp = archive / f"response.{stamp}.{request_id}.json"
                if req_path.exists():
                    shutil.copy2(req_path, archived_req)
                shutil.move(str(resp_path), str(archived_resp))
            except OSError:
                pass
            return content
        time.sleep(poll)
    raise TimeoutError(f"file_proxy timed out waiting for {resp_path}")


def _browser_ai_prompt(system: str, user: str) -> str:
    return (
        "You are acting as the browser-hosted cognition backend for Endgame-AI.\n"
        "Endgame-AI will operate the desktop; you supply only the JSON record requested by the role contract.\n"
        "Return exactly one JSON object and nothing else. Do not use markdown.\n"
        "Put the JSON between ENDGAME_JSON_START and ENDGAME_JSON_END only if your UI adds surrounding text.\n\n"
        "SYSTEM CONTRACT:\n" + system + "\n\n"
        "RUNTIME INPUT:\n" + user + "\n\n"
        "DECIDE NOW. Return the required JSON object."
    )


def _select_browser_ai_input(screen: str, hints: list[str]) -> str:
    """Pick the most likely chat textbox token from a rendered SCREEN string."""
    best: tuple[int, str] | None = None
    for line in str(screen or "").splitlines():
        m = re.match(r"\s*\[?(\d+)\]?\s+([A-Za-z]+)\s+\"(.*?)\"", line)
        if not m:
            continue
        token, role, name = m.group(1), m.group(2).lower(), m.group(3).lower()
        role_score = 0
        if role in {"edit", "combobox", "document"}:
            role_score += 50
        elif role in {"pane", "custom"}:
            role_score += 8
        score = role_score + sum(15 for h in hints if h.lower() in name)
        if not name.strip():
            score += 5 if role in {"edit", "document"} else 0
        if best is None or score > best[0]:
            best = (score, token)
    return best[1] if best and best[0] > 0 else ""


def _extract_browser_ai_content(screen: str, min_chars: int = 1) -> str:
    """Return a JSON-bearing text span from browser observation if possible."""
    raw = str(screen or "")
    marker = re.search(r"ENDGAME_JSON_START\s*(.*?)\s*ENDGAME_JSON_END", raw, flags=re.S | re.I)
    if marker:
        return marker.group(1).strip()
    obj = extract_json_object(raw)
    if obj is not None:
        return json.dumps(obj, ensure_ascii=False)
    # Fallback: strip obvious observation boilerplate but keep enough text for caller parse/retry.
    lines = []
    skip_prefixes = ("PROBE:", "WINDOWS:", "WINDOW_FOCUS:", "OVERLAYS:", "DESKTOP_TREE:")
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith(skip_prefixes):
            continue
        if re.match(r"^[*-]?\s*\[W\d+\]", s):
            continue
        lines.append(s)
    text = "\n".join(lines).strip()
    return text if len(text) >= min_chars else raw.strip()


def llm_browser_ai(system: str, user: str, model: dict[str, Any]) -> str:
    """Use a browser-hosted AI chat such as grok.com as the cognition backend.

    This is intentionally implemented through the same desktop verbs as normal
    tasks: open/focus browser, click a chat input, paste the role+runtime prompt,
    submit, wait, observe, and extract a JSON response.  If the chat window is
    closed or the UI changed, every call re-opens the configured URL and retries
    with alternate input-target hints.
    """
    cfg = dict(model.get("browser_ai") or {})
    browser = str(cfg.get("browser", "opera"))
    url = str(cfg.get("url", "https://grok.com"))
    domain = str(cfg.get("domain", "grok.com")).lower()
    wait_ms = int(cfg.get("response_wait_ms", 15000) or 15000)
    retries = max(1, int(cfg.get("retries", 2) or 2))
    min_chars = max(1, int(cfg.get("response_min_chars", 20) or 20))
    hints = list(cfg.get("input_hints") or ["ask", "message", "prompt", "chat", "grok", "anything", "what do you want"])
    prompt = _browser_ai_prompt(system, user)
    last_error = ""
    for attempt in range(retries):
        screen = observe_screen()
        if domain not in screen.lower():
            out = execute_verb("open_url", browser, url)
            if str(out).upper().startswith("FAILED"):
                last_error = str(out)
            execute_verb("wait", "", str(int(cfg.get("open_wait_ms", 5000) or 5000)))
            screen = observe_screen()
        target = _select_browser_ai_input(screen, hints)
        if target:
            click_out = execute_verb("click", target, "")
            if str(click_out).upper().startswith("FAILED"):
                last_error = str(click_out)
        write_out = execute_verb("write", target, prompt)
        if str(write_out).upper().startswith("FAILED") and target:
            # Some browser inputs expose unstable child tokens; retry by writing to current focus.
            last_error = str(write_out)
            write_out = execute_verb("write", "", prompt)
        if str(write_out).upper().startswith("FAILED"):
            last_error = str(write_out)
            execute_verb("open_url", browser, url)
            execute_verb("wait", "", str(int(cfg.get("open_wait_ms", 5000) or 5000)))
            continue
        submit_key = str(cfg.get("submit_key", "enter"))
        submit_out = execute_verb("press", "", submit_key)
        if str(submit_out).upper().startswith("FAILED"):
            last_error = str(submit_out)
        execute_verb("wait", "", str(wait_ms))
        response_screen = observe_screen()
        content = _extract_browser_ai_content(response_screen, min_chars=min_chars)
        if len(content.strip()) >= min_chars or extract_json_object(content) is not None:
            return content, ""
        last_error = f"browser_ai response too short after attempt {attempt + 1}"
    raise RuntimeError(f"browser_ai failed: {last_error or 'no response extracted'}")


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def reasoning_patch(circuit: str, content: str, parsed: dict[str, Any] | None, state: dict[str, Any], wiring: dict[str, Any]) -> dict[str, Any]:
    store_as = wiring.get("reasoning", {}).get("store_as", {}).get(circuit, circuit)
    reasoning = dict(state.get("reasoning", {}) or {})
    rec = {"content": content, "parsed": parsed, "ts": time.time()}
    reasoning[store_as] = rec
    chain = list(state.get("reasoning_chain", []) or [])
    chain.append({"circuit": circuit, "content": content[:4000], "parsed": parsed, "ts": time.time()})
    depth = int(wiring.get("reasoning", {}).get("chain_depth", 32) or 32)
    return {"reasoning": reasoning, "reasoning_chain": chain[-depth:]}


def call_node(node_cfg: dict[str, Any], state: dict[str, Any], wiring: dict[str, Any] | None = None) -> dict[str, Any]:
    """ROD two-call pattern: Call 1 lets model reason, Call 2 echoes that reasoning back for clean JSON."""
    wiring = wiring or load_wiring()
    circuit = circuit_for_node(node_cfg)
    system = load_system_prompt(circuit, state, node_cfg, wiring)
    user = build_user_message(circuit, state, node_cfg, wiring)
    model_cfg = load_model()
    base_temp = model_cfg.get("temperature", 0.3)
    bump = model_cfg.get("temperature_bump", 0.15)
    max_retries = wiring_limit("llm_parse_retries", 2, wiring)
    content, reasoning, parsed = "", "", None
    patch = {}
    for attempt in range(max_retries + 1):
        temp = base_temp if attempt == 0 else min(1.0, base_temp + bump * attempt)
        # Call 1: model reasons freely
        rod_content, rod_reasoning = llm(system, user, temperature=temp)
        rod_output = (rod_reasoning or rod_content or "").strip()
        # Call 2: echo reasoning back, model sees its own prior thought and produces clean output
        rod_user = user + "\n\nROD_REASONING_CONTENT:\n" + (rod_output or "(none)")
        content, _ = llm(system, rod_user, temperature=temp)
        reasoning = rod_output
        parsed = extract_json_object(content)
        if not parsed:
            # Fallback: check if JSON is in reasoning itself
            parsed = extract_json_object(reasoning)
        if parsed:
            break
    patch = reasoning_patch(circuit, content, parsed, state, wiring)
    append_trace({"circuit": circuit, "node": node_cfg.get("id"), "user": user[-4000:], "reasoning": reasoning[:4000], "content": content, "parsed": parsed})
    return {"content": content, "reasoning": reasoning, "parsed": parsed, "patch": patch}

# ─── Actions / observation ─────────────────────────────────────────────────

def observe_screen() -> str:
    try:
        from actions import configure_runtime, observe_screen as _observe
        configure_runtime(load_wiring())
        return _observe()
    except Exception as e:
        return f"(desktop observation unavailable: {type(e).__name__}: {e})"


def last_observation_snapshot() -> dict[str, Any]:
    try:
        from actions import last_observation_snapshot as _snap
        return _snap() or {}
    except Exception:
        return {}


def get_focused_title() -> str:
    try:
        from actions import get_focused_title as _title
        return _title()
    except Exception:
        return ""


def apply_memory_action(existing_memory: dict[str, Any], target: str, value: str) -> tuple[bool, dict[str, Any], str]:
    memory = dict(existing_memory or {})
    key = target or f"note_{len(memory) + 1}"
    text = str(value or "")
    if not text.strip():
        return False, memory, "FAILED: empty memory value"
    memory[key] = text
    return True, memory, f"stored {key} ({len(text)} chars)"


def execute_verb(verb: str, target: str = "", value: str = "") -> str:
    verb = (verb or "").strip()
    if verb == "remember":
        return "remember is handled by act node"
    if verb == "llm_request":
        return write_llm_request(target, value)
    if verb == "llm_wait_response":
        ok, text = wait_llm_response()
        return text if ok else "FAILED: " + text
    if verb == "copy_codebase":
        ok, info = copy_codebase_to_clipboard()
        return info.get("message", "copied") if ok else "FAILED: " + info.get("message", "copy failed")
    if verb == "browser_ai_handoff":
        request = value or target
        if not str(request).strip():
            return "FAILED: empty browser_ai_handoff request"
        handoff_system = (
            "ROLE: External Browser AI Brain / Handover Controller.\n"
            "You receive a human goal from Endgame-AI. Reply with a concise operational response. "
            "If you want Endgame-AI to execute desktop actions, return a JSON object with clear next_step fields; "
            "otherwise answer the request directly. Do not claim you performed desktop actions yourself."
        )
        model = load_model()
        try:
            response, _ = llm_browser_ai(handoff_system, str(request), model)
            return "browser_ai_response: " + response
        except Exception as e:
            return f"FAILED: browser_ai_handoff: {type(e).__name__}: {e}"
    try:
        from actions import configure_runtime, execute_verb as _execute
        configure_runtime(load_wiring())
        return _execute(verb, target, value)
    except Exception as e:
        return f"FAILED: {type(e).__name__}: {e}"

# ─── Rule evaluation ───────────────────────────────────────────────────────

def _action_text(a: dict[str, Any]) -> str:
    return f"{a.get('verb','')} {a.get('target','')} {a.get('value','')}".lower()


def _actions(state: dict[str, Any]) -> list[dict[str, Any]]:
    acts = state.get("last_actions_raw") or state.get("last_actions") or []
    return acts if isinstance(acts, list) else []


def _contains_any(text: str, needles: list[str]) -> bool:
    t = (text or "").lower()
    return any(str(n).lower() in t for n in needles)


def _check_condition(key: str, expected: Any, state: dict[str, Any]) -> bool:
    acts = _actions(state)
    outcome = str(state.get("last_outcome", ""))
    screen = str(state.get("screen", ""))
    done = str((state.get("current_step") or {}).get("done_when", ""))
    proof = " ".join([outcome, screen, str(state.get("post_action_title", ""))]).lower()
    if key == "outcome_ok":
        ok = bool(outcome) and not outcome.strip().upper().startswith(("FAILED", "BLOCKED", "CANNOT"))
        return ok is bool(expected)
    if key == "outcome_failed":
        failed = outcome.strip().upper().startswith(("FAILED", "BLOCKED", "CANNOT"))
        return failed is bool(expected)
    if key == "actions_include_verb":
        return any(a.get("verb") == expected for a in acts)
    if key == "actions_all_verb":
        return bool(acts) and all(a.get("verb") == expected for a in acts)
    if key == "actions_verb_absent":
        return not any(a.get("verb") == expected for a in acts)
    if key == "actions_wrote_nonempty":
        return any(a.get("verb") == "write" and str(a.get("value", "")).strip() for a in acts) is bool(expected)
    if key == "actions_pressed":
        return any(a.get("verb") in {"press", "hotkey"} and str(expected).lower() in _action_text(a) for a in acts)
    if key in {"actions_hotkey_contains", "actions_hotkey_absent"}:
        needles = [str(x).lower() for x in expected]
        hit = any(a.get("verb") == "hotkey" and all(n in _action_text(a) for n in needles) for a in acts)
        return not hit if key.endswith("absent") else hit
    if key == "done_when_matches":
        return _contains_any(done, expected)
    if key == "done_when_absent":
        return not _contains_any(done, expected)
    if key == "screen_contains":
        return _contains_any(screen, expected)
    if key == "focused_title_matches":
        return _contains_any(str(state.get("post_action_title", "")) or screen, expected)
    if key == "memory_has_key":
        return str(expected) in (state.get("memory") or {})
    if key == "memory_key_min_length":
        mem = state.get("memory") or {}
        return any(len(str(v)) >= int(expected) for v in mem.values())
    if key in {"chain_is_launch", "chain_is_navigation", "chain_is_save", "screen_contains_domain_needle", "outcome_contains_domain_needle", "focused_contains_action_target", "focused_has_writable", "memory_response_evidence", "chain_wrote_and_submitted"}:
        # Lightweight structural approximations for the shipped rules.
        if key == "chain_is_launch":
            return any(a.get("verb") == "launch" for a in acts) or ("win" in proof and "enter" in proof)
        if key == "chain_is_navigation":
            return any(a.get("verb") == "open_url" or re.search(r"https?://|\w+\.\w+", str(a.get("value", ""))) for a in acts)
        if key == "chain_is_save":
            return any(a.get("verb") == "hotkey" and "ctrl" in _action_text(a) and "s" in _action_text(a) for a in acts)
        if key in {"screen_contains_domain_needle", "outcome_contains_domain_needle"}:
            needles = set(re.findall(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b", f"{state.get('goal','')} {done}".lower()))
            hay = screen.lower() if key.startswith("screen") else outcome.lower()
            return any(n in hay or n.split(".", 1)[0] in hay for n in needles)
        if key == "focused_contains_action_target":
            title = (state.get("post_action_title") or "").lower()
            return any(str(a.get("target", "")).lower() in title for a in acts if a.get("target"))
        if key == "focused_has_writable":
            return any(word in screen.lower() for word in ["edit", "document", "textarea", "input"])
        if key == "memory_response_evidence":
            return bool((state.get("memory") or {}).get("llm_response"))
        if key == "chain_wrote_and_submitted":
            return any(a.get("verb") == "write" for a in acts) and any(a.get("verb") in {"press", "hotkey"} and "enter" in _action_text(a) for a in acts)
    # Unknown conditions default false, not exception, so self-modified rules cannot crash the engine.
    return False


def evaluate_rules(phase: str, state: dict[str, Any], wiring: dict[str, Any] | None = None) -> dict[str, Any] | None:
    wiring = wiring or load_wiring()
    rules = [r for r in wiring.get("rules", []) if r.get("phase") == phase]
    ordered = [r for r in rules if r.get("verdict") in {"deny", "reject"}] + [r for r in rules if r.get("verdict") not in {"deny", "reject"}]
    for rule in ordered:
        match = rule.get("match") or {}
        if isinstance(match, dict) and all(_check_condition(k, v, state) for k, v in match.items()):
            return rule
    return None


def normalize_actions_from_wiring(state: dict[str, Any], actions: list[dict[str, Any]], act_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    # Keep a hook compatible with old wiring; most normalizers are intentionally simple.
    out = []
    for a in actions:
        cur = dict(a)
        for n in act_cfg.get("verb_normalize", []) or []:
            if n.get("from") and cur.get("verb") != n.get("from"):
                continue
            if n.get("to"):
                cur["verb"] = n.get("to")
            if "target_set" in n:
                cur["target"] = n.get("target_set") or ""
            if "value_set" in n:
                cur["value"] = n.get("value_set") or ""
        out.append(cur)
    return out

# ─── LLM proxy / bus / traces ──────────────────────────────────────────────

def write_llm_request(target: str, value: str) -> str:
    wiring = load_wiring()
    rt = wiring.get("runtime", {})
    path = ROOT / rt.get("llm_request_path", "comms/llm_proxy/request.json")
    request_id = _new_llm_request_id()
    request_text = str(value or "")
    state_snapshot = last_state()
    payload = {
        "id": request_id,
        "status": "pending",
        "created_at": time.time(),
        "target": target,
        "request": request_text,
        "value": request_text,
        "state": state_snapshot,
        "messages": [
            {"role": "system", "content": "ROLE: External AI Agent. Read this Endgame-AI request, complete the requested cognition/work, and write response.json with the same id."},
            {"role": "user", "content": request_text},
        ],
    }
    atomic_write_json(path, payload, indent=2)
    return f"llm_request written: {path} id={request_id}"


def wait_llm_response() -> tuple[bool, str]:
    wiring = load_wiring()
    rt = wiring.get("runtime", {})
    path = ROOT / rt.get("llm_response_path", "comms/llm_proxy/response.json")
    timeout = int(rt.get("llm_wait_timeout_ms", 60000)) / 1000.0
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            data = read_json(path, {})
            text = _llm_response_content(data)
            try:
                archive = ROOT / rt.get("llm_archive_dir", "comms/llm_proxy/archive")
                archive.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(archive / f"response.{int(time.time())}.json"))
            except OSError:
                pass
            return True, text
        time.sleep(0.5)
    return False, f"timeout waiting for {path}"


def bus_read() -> list[dict[str, Any]]:
    data = read_json(BUS_FILE, [])
    return data if isinstance(data, list) else []


def bus_write(item: dict[str, Any], wiring: dict[str, Any] | None = None) -> None:
    wiring = wiring or load_wiring()
    items = bus_read()
    items.append({**item, "ts": time.time()})
    max_items = wiring_limit("bus_max", 400, wiring)
    atomic_write_json(BUS_FILE, items[-max_items:], indent=2)


def append_trace(item: dict[str, Any]) -> None:
    TRACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRACES_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**item, "ts": time.time()}, ensure_ascii=False) + "\n")


def recent_traces(limit: int = 6) -> list[dict[str, Any]]:
    if not TRACES_FILE.exists():
        return []
    try:
        lines = TRACES_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(x) for x in lines if x.strip()]
    except Exception:
        return []

# ─── Codebase clipboard feature ────────────────────────────────────────────

def should_include_code_file(path: pathlib.Path, root: pathlib.Path = ROOT) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDE_FILES:
        return False
    if any(fnmatch.fnmatch(path.name, pat) for pat in EXCLUDE_PATTERNS):
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        sample = path.read_bytes()[:2048]
        sample.decode("utf-8")
        return True
    except Exception:
        return False


def collect_codebase_text(root: pathlib.Path = ROOT) -> tuple[str, dict[str, Any]]:
    files: list[pathlib.Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and should_include_code_file(p, root):
            files.append(p)
    chunks = []
    total = 0
    for p in files:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            text = f"<unreadable: {type(e).__name__}: {e}>"
        total += len(text)
        chunks.append(f"===== FILE: {rel} =====\n{text.rstrip()}\n===== END FILE: {rel} =====")
    manifest = {
        "root": str(root),
        "files": [p.relative_to(root).as_posix() for p in files],
        "file_count": len(files),
        "char_count": sum(len(c) for c in chunks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    header = "ENDGAME-AI FULL CODEBASE SNAPSHOT\n" + json.dumps(manifest, ensure_ascii=False, indent=2)
    return header + "\n\n" + "\n\n".join(chunks) + "\n", manifest


def copy_text_to_clipboard(text: str) -> tuple[bool, str]:
    system = platform.system().lower()
    commands = []
    if system == "windows":
        commands = [["clip"]]
    elif system == "darwin":
        commands = [["pbcopy"]]
    else:
        commands = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in commands:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=15)
                return True, "clipboard command: " + " ".join(cmd)
            except Exception as e:
                last = f"{cmd[0]} failed: {e}"
        else:
            last = f"{cmd[0]} not found"
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True, "tkinter clipboard"
    except Exception as e:
        return False, f"clipboard unavailable ({last if 'last' in locals() else 'no command'}; tkinter: {e})"


def copy_codebase_to_clipboard(root: pathlib.Path = ROOT) -> tuple[bool, dict[str, Any]]:
    text, manifest = collect_codebase_text(root)
    atomic_write_text(CODEBASE_SNAPSHOT, text)
    ok, method = copy_text_to_clipboard(text)
    msg = f"{manifest['file_count']} files, {len(text)} chars written to {CODEBASE_SNAPSHOT}"
    if ok:
        msg += f" and copied via {method}"
    else:
        msg += f"; clipboard fallback failed: {method}"
    info = {**manifest, "snapshot_path": str(CODEBASE_SNAPSHOT), "copied_to_clipboard": ok, "message": msg}
    sse_push("codebase", info)
    return ok, info


def scaffold_node_file(node_type: str, code: str | None = None, overwrite: bool = False) -> pathlib.Path:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", node_type or ""):
        raise ValueError("node_type must be a Python identifier")
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    path = NODES_DIR / f"{node_type}.py"
    if path.exists() and not overwrite:
        raise FileExistsError(f"node already exists: {path}")
    if code is None:
        code = f'''"""Generated endgame-ai node: {node_type}."""\n# Inputs: state, config, wiring, and runtime helpers.\npatch = {{"{node_type}_ran_at": time.time()}}\nsignals = ["done"]\n'''
    atomic_write_text(path, code.rstrip() + "\n")
    return path

# ─── Wiring patches / self-modify ──────────────────────────────────────────

def _require_id(value: Any, label: str = "id") -> str:
    text = str(value or "").strip()
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-]*$", text):
        raise ValueError(f"invalid {label}: {value!r}")
    return text


def apply_wiring_patch(current: dict[str, Any], parsed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    data = parsed.get("data") or {}
    op = str(data.get("op") or "").strip()
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    topo = current.setdefault("topology", {}).setdefault("nodes", []) and current.setdefault("topology", {})
    if op == "add_node":
        node_id = _require_id(payload.get("id"))
        node_type = _require_id(payload.get("type", node_id), "type")
        nodes = current.setdefault("topology", {}).setdefault("nodes", [])
        if any(n.get("id") == node_id for n in nodes):
            raise ValueError(f"node exists: {node_id}")
        node = {"id": node_id, "type": node_type, "label": payload.get("label", node_id)}
        for k in ("circuit", "prompt"):
            if k in payload:
                node[k] = payload[k]
        nodes.append(node)
        if payload.get("code"):
            scaffold_node_file(node_type, str(payload["code"]), overwrite=bool(payload.get("overwrite")))
        if payload.get("edge_from"):
            current["topology"].setdefault("edges", []).append({"from": _require_id(payload["edge_from"], "edge_from"), "to": node_id, "on": str(payload.get("on") or "ready")})
        if payload.get("edge_to"):
            current["topology"].setdefault("edges", []).append({"from": node_id, "to": _require_id(payload["edge_to"], "edge_to"), "on": str(payload.get("edge_to_on") or "done")})
    elif op == "create_node_file":
        node_type = _require_id(payload.get("type") or payload.get("node_type"), "type")
        path = scaffold_node_file(node_type, payload.get("code"), overwrite=bool(payload.get("overwrite")))
        payload = {**payload, "path": str(path)}
    elif op == "update_node":
        node_id = _require_id(payload.get("id"))
        node = next((n for n in current.get("topology", {}).get("nodes", []) if n.get("id") == node_id), None)
        if not node:
            raise ValueError(f"unknown node: {node_id}")
        updates = payload.get("set") or {k: v for k, v in payload.items() if k != "id"}
        for k, v in updates.items():
            if k in {"label", "type", "circuit", "prompt"}:
                node[k] = v
    elif op == "remove_node":
        node_id = _require_id(payload.get("id"))
        topo = current.setdefault("topology", {})
        topo["nodes"] = [n for n in topo.get("nodes", []) if n.get("id") != node_id]
        topo["edges"] = [e for e in topo.get("edges", []) if e.get("from") != node_id and e.get("to") != node_id]
    elif op == "add_edge":
        edge = {"from": _require_id(payload.get("from"), "from"), "to": _require_id(payload.get("to"), "to"), "on": str(payload.get("on") or "ready")}
        current.setdefault("topology", {}).setdefault("edges", []).append(edge)
    elif op == "remove_edge":
        topo = current.setdefault("topology", {})
        frm, to, on = payload.get("from"), payload.get("to"), payload.get("on")
        topo["edges"] = [e for e in topo.get("edges", []) if not (e.get("from") == frm and e.get("to") == to and (on is None or e.get("on") == on))]
    elif op in {"set_limit", "set_guard", "set_observe"}:
        section = {"set_limit": "limits", "set_guard": "guards", "set_observe": "observe"}[op]
        current.setdefault(section, {})[str(payload.get("key"))] = payload.get("value")
    elif op in {"set_prompt_base", "set_role", "append_role_rule"}:
        prompts = current.setdefault("prompts", {})
        if op == "set_prompt_base":
            prompts["base"] = str(payload.get("text") or "")
        else:
            role = str(payload.get("role") or "")
            roles = prompts.setdefault("roles", {})
            if op == "set_role":
                roles[role] = str(payload.get("text") or "")
            else:
                roles[role] = (roles.get(role, "").rstrip() + "\n- " + str(payload.get("rule") or "")).strip()
    elif op in {"add_rule", "update_rule", "remove_rule"}:
        rules = current.setdefault("rules", [])
        if op == "add_rule":
            rule = payload.get("rule") or payload
            if not isinstance(rule, dict) or not rule.get("id"):
                raise ValueError("add_rule requires rule object/id")
            rules.append(rule)
        elif op == "update_rule":
            rid = str(payload.get("id"))
            rule = next((r for r in rules if r.get("id") == rid), None)
            if not rule:
                raise ValueError(f"unknown rule: {rid}")
            rule.update(payload.get("set") or {})
        else:
            rid = str(payload.get("id"))
            current["rules"] = [r for r in rules if r.get("id") != rid]
    else:
        raise ValueError(f"unsupported patch op: {op}")
    return op, payload

# ─── Misc ──────────────────────────────────────────────────────────────────

def preview_text(text: str, limit_key: str = "error_preview_chars", default: int = 1200) -> str:
    limit = wiring_limit(limit_key, default)
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + "…"


def format_exception(e: BaseException) -> str:
    return "".join(traceback.format_exception(type(e), e, e.__traceback__))
