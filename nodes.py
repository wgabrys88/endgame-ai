"""nodes — the engine core. Hot-swappable node modules + the cognition/execution helpers
they call. Intent-based: every LLM reply is a typed record {record_type, data} validated
against the wiring contract. No constrained mode, no safety gate — this is an unconstrained
organism with full control of the machine.

A node is a plain Python file in NODES_DIR. It runs in a namespace that exposes the engine
helpers below plus `ctx`, `state`, `wiring`, `config`. It sets two names: `patch` (dict to
merge into state) and `signals` (list; first signal routes the graph). Nodes are re-read on
every execution, so editing a node file hot-swaps behavior with no restart.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import time
from typing import Any

import actions

ROOT = pathlib.Path(__file__).parent.resolve()
SEED_DIR = ROOT / "seed_nodes"
NODES_DIR = ROOT / "live_nodes"


# ─── node files ─────────────────────────────────────────────────────────────

def ensure_nodes():
    """Copy seed nodes into the mutable live dir on first run. live_nodes is what runs."""
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    if not any(NODES_DIR.glob("*.py")) and SEED_DIR.exists():
        for f in SEED_DIR.glob("*.py"):
            shutil.copy2(f, NODES_DIR / f.name)


def node_path(node_type: str) -> pathlib.Path:
    return NODES_DIR / f"{node_type}.py"


def list_node_types() -> list[str]:
    return sorted(p.stem for p in NODES_DIR.glob("*.py"))


def execute_node(node_cfg: dict, ctx) -> tuple[str, dict]:
    """Run one node by its type. Returns (signal, patch). Re-reads the file each call."""
    node_type = node_cfg.get("type", "")
    path = node_path(node_type)
    if not path.exists():
        raise FileNotFoundError(f"no node module for type '{node_type}' at {path}")
    src = path.read_text(encoding="utf-8")
    ns: dict[str, Any] = {
        "ctx": ctx, "state": ctx.state, "wiring": ctx.wiring, "config": node_cfg,
        "call_node": lambda cfg=node_cfg: call_node(cfg, ctx),
        "observe_screen": observe_screen, "execute_verb": execute_verb,
        "get_focused_title": get_focused_title, "last_observation_snapshot": last_observation_snapshot,
        "wiring_limit": wiring_limit, "evaluate_rules": evaluate_rules,
        "apply_memory_action": apply_memory_action, "apply_wiring_patch": apply_wiring_patch,
        "save_wiring": save_wiring, "validate_wiring": validate_wiring,
        "preview_text": preview_text, "time": time, "json": json, "re": re,
        "patch": {}, "signals": ["idle"],
    }
    exec(compile(src, str(path), "exec"), ns)
    patch = ns.get("patch", {}) or {}
    signals = ns.get("signals", []) or ["idle"]
    return (signals[0] if signals else "idle"), patch


# ─── cognition: ROD call + intent-record contract ───────────────────────────

def circuit_for(node_cfg: dict) -> str:
    return str(node_cfg.get("circuit") or node_cfg.get("type", ""))


def _render(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, indent=2)


def _block_value(state: dict, source: str) -> Any:
    cur: Any = state
    parts = source.split(".")
    if parts and parts[0] == "state":
        parts = parts[1:]
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


# Per-circuit user-message blocks. Intent-based: the actor sees SCREEN; the verifier sees
# the step intent + evidence; the planner sees the goal; etc.
_BLOCKS = {
    "planner":   [("GOAL", "goal"), ("LAST_ERROR", "last_error"), ("HISTORY", "history"), ("MEMORY", "memory")],
    "unified":   [("SUBTASK", "step_goal"), ("DONE_WHEN", "current_step.done_when"), ("SCREEN", "screen"), ("LAST_ERROR", "last_error"), ("MEMORY", "memory")],
    "verifier":  [("STEP", "current_step.description"), ("DONE_WHEN", "current_step.done_when"), ("SCREEN", "screen"), ("LAST_ACTIONS", "last_actions"), ("LAST_OUTCOME", "last_outcome"), ("MEMORY", "memory")],
    "reflector": [("GOAL", "goal"), ("STEP", "current_step.description"), ("LAST_ERROR", "last_error"), ("HISTORY", "history"), ("MEMORY", "memory")],
    "self_modify": [("GOAL", "goal"), ("LAST_ERROR", "last_error"), ("LAST_DIAGNOSIS", "last_diagnosis"), ("CURRENT_WIRING", "wiring_summary")],
}


def build_user_message(circuit: str, state: dict, wiring: dict) -> str:
    body = []
    for label, source in _BLOCKS.get(circuit, []):
        if source == "wiring_summary":
            value = {"transport": wiring.get("model", {}).get("transport"), "verbs": list(wiring.get("verbs", {}).keys())}
        else:
            value = _block_value(state, source)
        text = _render(value)
        if text:
            body.append(f"{label}:\n{text}")
    return "\n\n".join(body)


def build_system_prompt(circuit: str, wiring: dict) -> str:
    prompts = wiring.get("prompts", {})
    base = prompts.get("base", "")
    role = prompts.get("roles", {}).get(circuit, "")
    return (base + "\n\n" + role).strip()


def call_node(node_cfg: dict, ctx) -> dict:
    """ROD two-call decision for an LLM circuit, with intent-record validation.

    Returns {content, reasoning, parsed, record_ok}. `parsed` is the typed record; it is
    only considered valid when its record_type matches the wiring contract for the circuit.
    Fail hard: the brain raises on transport errors; we do not swallow them here."""
    wiring = ctx.wiring
    circuit = circuit_for(node_cfg)
    system = build_system_prompt(circuit, wiring)
    user = build_user_message(circuit, ctx.state, wiring)
    retries = wiring_limit("llm_parse_retries", 2, wiring)
    content, parsed, reasoning = ctx.brain.think(system, user, retries)

    expected = wiring.get("reasoning", {}).get("expected_record_type", {}).get(circuit)
    record_ok = bool(parsed) and (expected is None or parsed.get("record_type") == expected)

    # reasoning trace (debug/workbench), bounded
    chain = list(ctx.state.get("reasoning_chain", []) or [])
    chain.append({"circuit": circuit, "reasoning": reasoning[:4000], "parsed": parsed, "ts": time.time()})
    depth = int(wiring.get("reasoning", {}).get("chain_depth", 32) or 32)
    ctx.state["reasoning_chain"] = chain[-depth:]
    ctx.state["last_reasoning"] = reasoning[:2000]
    return {"content": content, "reasoning": reasoning, "parsed": parsed, "record_ok": record_ok}


# ─── desktop I/O (reuses the proven actions.py / desktop.py) ─────────────────

_io_ready = False


def _ensure_io(wiring: dict):
    global _io_ready
    if not _io_ready:
        actions.configure_runtime(wiring)
        _io_ready = True


def observe_screen() -> str:
    return actions.observe_screen()


def last_observation_snapshot() -> dict:
    return actions.last_observation_snapshot()


def get_focused_title() -> str:
    return actions.get_focused_title()


def execute_verb(verb: str, target: str = "", value: str = "") -> str:
    return actions.execute_verb(verb, target, value)


# ─── helpers ────────────────────────────────────────────────────────────────

def wiring_limit(name: str, default: int, wiring: dict) -> int:
    try:
        return int(wiring.get("limits", {}).get(name, default))
    except (TypeError, ValueError):
        return default


def evaluate_rules(circuit: str, state: dict, wiring: dict):
    """Optional deterministic rules. Empty by default; intent judgment is the LLM's job."""
    for rule in wiring.get("rules", []) or []:
        if rule.get("circuit") == circuit:
            return rule
    return None


def apply_memory_action(memory: dict, key: str, value: str) -> tuple[bool, dict, str]:
    if not key:
        return False, memory, "FAILED: remember needs a target key"
    memory = dict(memory)
    memory[key] = value
    return True, memory, f"remembered {key}"


def preview_text(text: str, n: int = 200) -> str:
    return (text or "")[:n]


def apply_wiring_patch(wiring: dict, parsed: dict) -> tuple[str, Any]:
    """Apply a {op,path,value} wiring patch in place. op=set only (smallest surface)."""
    data = (parsed or {}).get("data") or {}
    op = data.get("op", "set")
    path = str(data.get("path", "")).strip()
    value = data.get("value")
    if not path:
        raise ValueError("wiring_patch missing path")
    parts = path.split(".")
    cur = wiring
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value
    return op, {"path": path, "value": value}


def validate_wiring(wiring: dict) -> list[str]:
    errs = []
    if "model" not in wiring or "transport" not in wiring.get("model", {}):
        errs.append("model.transport missing")
    if "topology" not in wiring:
        errs.append("topology missing")
    return errs


def save_wiring(wiring: dict):
    (ROOT / "wiring.json").write_text(json.dumps(wiring, ensure_ascii=False, indent=2), encoding="utf-8")
