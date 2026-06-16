"""Agents â€” pipeline stages. Each: run(board) â†’ {phase, data, writes, next}."""
from __future__ import annotations
import difflib
import json
import os
from pathlib import Path
import py_compile
import re
import time
from datetime import datetime, timezone
from typing import Any

import config
import log
from llm import LLMResult, call_llm

_ASCII_MAP = str.maketrans({
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u00a0": " ",
})

def validate_python(text: str) -> tuple[bool, str, str]:
    """Syntax check only. Return (ok, cleaned_code, error_message)."""
    cleaned = text.translate(_ASCII_MAP).strip()
    if not cleaned:
        return False, "", "empty code"
    try:
        compile(cleaned, "<step>", "exec")
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "step"
        return False, cleaned, f"SyntaxError: {exc.msg} ({where})"
    return True, cleaned, ""

_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9_]+\.py$")
_REASONING = (
    "Think in reasoning channel. Final content: one raw JSON object, no markdown fences.\n"
)
_CIRCUIT_HINTS: dict[str, str] = {
    "planner": '{"records":[{"schema_version":"contract-bus.v1","record_type":"task|contract","data":{}}]}',
    "verifier": '{"id":"...","task_id":"...","contract_id":"...","contract_version":1,"verdict":"DONE|NOT_DONE|UNKNOWN","confidence":0.0,"because":"...","condition_results":[],"evidence_used":[],"evidence_rejected":[],"actor_claim_trusted_as_primary":false,"next_recommendation":"continue|gather_evidence|replan|ask_user|stop"}',
    "reflector": '{"diagnosis":"...","suggestion":"...","rule":"..."}',
    "mutator": '{"action":"patch_plugin"|"patch_prompt"|"none","filename":"plugins/existing_name.py","content":"full source or prompt text"}',
    "fission_judge": '{"verdict":"credit"|"deny","diagnosis":"...","suggestion":"...","rule":""}',
    "actor": '{"actions":[{"verb":"click|focus|write|press|hotkey|scroll","target":"[id]","value":""}],"conclusion":"EXECUTE"|"DONE"|"CANNOT"}',
}
def _personality(board: dict[str, Any] | None = None) -> str:
    if board:
        return str(board.get("personality", "")).strip()
    return os.environ.get("ENDGAME_PERSONALITY", "").strip()
def _llm_event_data(result: LLMResult, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "output_chars": len(result.text or ""),
        "reasoning_chars": len(result.reasoning or ""),
        "reasoning_tokens": getattr(result, "reasoning_tokens", 0) or 0,
    }
    if extra:
        data.update(extra)
    return data
def _persona_prompt(persona: str) -> str:
    path = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""
def _personality_system(board: dict[str, Any] | None = None) -> str:
    name = _personality(board)
    text = _persona_prompt(name)
    if text:
        return text
    return f"You are {name or 'endgame-ai'}, a reactor rod in the colony organism."
def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""
def _llm_user(circuit: str, body: str) -> str:
    parts: list[str] = [_REASONING]
    hint = _CIRCUIT_HINTS.get(circuit, "")
    if hint:
        parts.append(f"JSON shape (hint, not law): {hint}")
    circuit_text = _load_prompt(circuit)
    if circuit_text:
        parts.append(f"CIRCUIT ({circuit}):\n{circuit_text}")
    parts.append("---TASK_STATE---")
    parts.append(body.strip())
    return "\n".join(parts)
def _strip_code_fence(text: str) -> str:
    cleaned = str(text).strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
def _parse_json(text: str) -> dict[str, Any] | None:
    raw = _strip_code_fence(str(text or "").strip())
    if not raw:
        return None
    for candidate in (raw, raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else ""):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
def _call_circuit(
    board: dict[str, Any],
    circuit: str,
    body: str,
    *,
    role: str = "",
    cache_key: str = "",
) -> LLMResult:
    return call_llm(
        _personality_system(board),
        _llm_user(circuit, body),
        role or circuit,
        cache_key=cache_key or circuit,
    )
def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = ["RECENT HISTORY:"]
    for h in history[-config.MAX_HISTORY:]:
        if isinstance(h, dict):
            lines.append(f"  {json.dumps(h, ensure_ascii=False)[:400]}")
    return "\n".join(lines)
def _desktop_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    return home / "Desktop"
def _filesystem_context() -> str:
    return "\n".join([
        f"WORKSPACE_DIR: {config.BASE_DIR}",
        f"USER_HOME: {Path(os.environ.get('USERPROFILE') or Path.home())}",
        f"DESKTOP_DIR: {_desktop_dir()}",
        "PATH_RULE: Never use placeholder username paths; use the paths above or ENDGAME_* constants and print resolved path evidence.",
    ])
def _desktop_context() -> str:
    try:
        from desktop import observe
        obs = observe()
        parts = [f"DESKTOP_FOCUSED: {obs.focused_title}"]
        if obs.desktop_summary: parts.append(f"DESKTOP_SUMMARY: {obs.desktop_summary[:600]}")
        if obs.context_text: parts.append(obs.context_text[:2000])
        return "\n".join(parts)
    except Exception as exc:
        return f"DESKTOP_ERROR: {exc}"
def _active_claims() -> str:
    try:
        import comms
        claims: dict[str, str] = {}
        for e in comms.read_chat(30):
            kind, payload = str(e.get("kind", "")), e.get("payload") if isinstance(e.get("payload"), dict) else {}
            if kind == comms.KIND_ROUTE and str(e.get("from", "")) == "comms_operator":
                t = str(e.get("to", ""))
                if t: claims[t] = (str(payload.get("goal", "")) or str(e.get("text", "")))[:500]
            elif kind == comms.KIND_EVENT and payload.get("phase") == "plan":
                who = str(e.get("from", ""))
                if who: claims[who] = str(payload.get("done_when", ""))[:500] or claims.get(who, "")
        if not claims: return ""
        return "OTHERS WORKING ON (do not duplicate):\n" + "\n".join(f"  @{w}: {t}" for w, t in claims.items())
    except Exception:
        return ""

CONTRACT_SCHEMA = "contract-bus.v1"
VERIFICATION_PACKET_SCHEMA = "verification-packet.v1"
TASK_STATUSES = frozenset({"proposed", "active", "blocked", "claimed_done", "verified_done", "rejected", "superseded"})
STATUS_TRANSITIONS = frozenset({
    ("proposed", "active"), ("active", "claimed_done"), ("claimed_done", "verified_done"),
    ("active", "verified_done"), ("active", "blocked"), ("active", "rejected"),
    ("claimed_done", "rejected"), ("claimed_done", "active"), ("active", "active"),
    ("blocked", "active"), ("rejected", "active"), ("active", "superseded"),
})
VERDICTS = frozenset({"DONE", "NOT_DONE", "UNKNOWN"})
ROLE_CAPABILITIES: dict[str, dict[str, bool]] = {
    "planner": {"can_plan": True, "can_act": False, "can_observe": True, "can_verify": False,
                "can_publish_claim": True, "can_publish_verdict": False, "can_mutate_ui": False,
                "can_mutate_artifacts": False, "can_execute_commands": False, "can_read_artifacts": True},
    "actor": {"can_plan": False, "can_act": True, "can_observe": True, "can_verify": False,
              "can_publish_claim": True, "can_publish_verdict": False, "can_mutate_ui": True,
              "can_mutate_artifacts": True, "can_execute_commands": True, "can_read_artifacts": True},
    "observer": {"can_plan": False, "can_act": False, "can_observe": True, "can_verify": False,
                 "can_publish_claim": False, "can_publish_verdict": False, "can_mutate_ui": False,
                 "can_mutate_artifacts": False, "can_execute_commands": False, "can_read_artifacts": True},
    "verifier": {"can_plan": False, "can_act": False, "can_observe": True, "can_verify": True,
                 "can_publish_claim": False, "can_publish_verdict": True, "can_mutate_ui": False,
                 "can_mutate_artifacts": False, "can_execute_commands": False, "can_read_artifacts": True},
    "reviewer": {"can_plan": False, "can_act": False, "can_observe": True, "can_verify": True,
                 "can_publish_claim": True, "can_publish_verdict": True, "can_mutate_ui": False,
                 "can_mutate_artifacts": False, "can_execute_commands": False, "can_read_artifacts": True},
    "runtime": {"can_plan": False, "can_act": False, "can_observe": True, "can_verify": False,
                "can_publish_claim": True, "can_publish_verdict": False, "can_mutate_ui": False,
                "can_mutate_artifacts": False, "can_execute_commands": False, "can_read_artifacts": True},
    "tool": {"can_plan": False, "can_act": False, "can_observe": True, "can_verify": False,
             "can_publish_claim": True, "can_publish_verdict": False, "can_mutate_ui": False,
             "can_mutate_artifacts": False, "can_execute_commands": False, "can_read_artifacts": True},
}

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
def _new_id(board: dict[str, Any], prefix: str) -> str:
    seq = int(board.get("_record_seq", 0) or 0) + 1
    board["_record_seq"] = seq
    return f"{prefix}-{int(time.time() * 1000)}-{seq}"
def _cycle_id(board: dict[str, Any]) -> str:
    cycles = int(board.get("_pressure", {}).get("cycles", 0) or 0)
    return f"cycle-{cycles}"
def _root_task_id(board: dict[str, Any]) -> str:
    root = str(board.get("root_task_id", "")).strip()
    if not root:
        root = _new_id(board, "task-root")
        board["root_task_id"] = root
    return root
def _effective_role(board: dict[str, Any], role: str) -> str:
    return "reviewer" if _personality(board) == "reviewer" and role in {"actor", "verifier", "observer"} else role
def _capability(role: str) -> dict[str, bool]:
    return dict(ROLE_CAPABILITIES.get(role, ROLE_CAPABILITIES["runtime"]))
def _confidence(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
def _make_record(
    board: dict[str, Any],
    record_type: str,
    role: str,
    data: dict[str, Any],
    *,
    task_id: str | None = None,
    parent_task_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA,
        "record_id": _new_id(board, record_type),
        "record_type": record_type,
        "created_at": _now_iso(),
        "cycle_id": _cycle_id(board),
        "root_task_id": _root_task_id(board),
        "parent_task_id": parent_task_id,
        "task_id": task_id,
        "role": role,
        "agent_id": _personality(board) or None,
        "data": data,
    }
def _publish_record(board: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    records = board.setdefault("bus_records", [])
    records.append(record)
    if len(records) > 240:
        del records[:-240]
    try:
        import comms
        comms.post_record(record)
    except Exception:
        pass
    return record
def _runtime_event(
    board: dict[str, Any],
    event_type: str,
    summary: str,
    *,
    task_id: str | None = None,
    related_record_ids: list[str] | None = None,
    severity: str = "info",
) -> dict[str, Any]:
    data = {
        "id": _new_id(board, "runtime-event"),
        "event_type": event_type,
        "task_id": task_id,
        "related_record_ids": related_record_ids or [],
        "summary": summary[:500],
        "severity": severity,
    }
    return _publish_record(board, _make_record(board, "runtime_event", "runtime", data, task_id=task_id))
def _permission_denied(board: dict[str, Any], role: str, operation: str, task_id: str | None, summary: str) -> dict[str, Any]:
    return _runtime_event(board, "permission_denied", f"{role} cannot {operation}: {summary}", task_id=task_id, severity="warning")
def _require_capability(board: dict[str, Any], role: str, flag: str, operation: str, task_id: str | None, summary: str) -> bool:
    if _capability(role).get(flag, False):
        return True
    _permission_denied(board, role, operation, task_id, summary)
    return False
def _proof_requirement(classes: list[str] | None = None) -> dict[str, Any]:
    return {
        "required_evidence_classes": classes or [
            "direct_observation", "external_readback", "tool_result",
            "state_snapshot", "artifact_inspection", "execution_trace",
            "prior_verified_contract",
        ],
        "min_independent_sources": 1,
        "actor_claim_allowed_as_primary": False,
        "allow_inference": True,
        "max_age_cycles": 3,
    }
def _default_contract(task: dict[str, Any]) -> dict[str, Any]:
    done_when = str(task.get("description", "")).strip()
    return {
        "id": str(task.get("contract_id") or f"contract-{task['id']}-v1"),
        "task_id": task["id"],
        "version": 1,
        "done_when": done_when,
        "success_conditions": [{
            "id": "sc-1",
            "description": done_when,
            "required": True,
            "proof_requirement": _proof_requirement(),
        }],
        "failure_conditions": [{"id": "fc-contradiction", "description": "Evidence contradicts completion."}],
        "forbidden_primary_evidence_classes": ["actor_self_report", "keyword_match_only", "planner_intent_only"],
        "uncertainty_policy": {
            "missing_required_evidence": "UNKNOWN",
            "contradictory_evidence": "NOT_DONE",
            "stale_evidence": "UNKNOWN",
        },
    }
def _tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in board.get("tasks", []) if isinstance(t, dict)]
def _contracts(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in board.get("contracts", []) if isinstance(c, dict)]
def _task_by_id(board: dict[str, Any], task_id: str | None) -> dict[str, Any] | None:
    return next((t for t in _tasks(board) if t.get("id") == task_id), None)
def _contract_for_task(board: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    cid = str(task.get("contract_id", ""))
    contract = next((c for c in _contracts(board) if c.get("id") == cid or c.get("task_id") == task.get("id")), None)
    if contract:
        return contract
    contract = _default_contract(task)
    board.setdefault("contracts", []).append(contract)
    _publish_record(board, _make_record(board, "contract", "planner", contract, task_id=task["id"], parent_task_id=task.get("parent_id")))
    return contract
def _sync_plan(board: dict[str, Any]) -> None:
    root = board.get("root_task_id")
    board["plan"] = [t for t in _tasks(board) if t.get("id") != root]
def _ensure_root_records(board: dict[str, Any]) -> None:
    root_id = _root_task_id(board)
    if _task_by_id(board, root_id):
        return
    root = {
        "id": root_id,
        "parent_id": None,
        "root_id": root_id,
        "description": str(board.get("goal", "") or "root mission"),
        "intent": "mission_context",
        "status": "active",
        "depends_on": [],
        "contract_id": f"contract-{root_id}-v1",
        "version": 1,
    }
    contract = _default_contract(root)
    board["tasks"] = [root] + _tasks(board)
    board["contracts"] = [contract] + _contracts(board)
    _publish_record(board, _make_record(board, "task", "runtime", root, task_id=root_id))
    _publish_record(board, _make_record(board, "contract", "runtime", contract, task_id=root_id))
    if not board.get("_capabilities_published"):
        for role, caps in ROLE_CAPABILITIES.items():
            _publish_record(board, _make_record(board, "capability", "runtime", {"role": role, **caps}, task_id=root_id))
        board["_capabilities_published"] = True
def _set_task_status(board: dict[str, Any], task: dict[str, Any], status: str, role: str, related: list[str] | None = None) -> None:
    old = str(task.get("status", "proposed"))
    if status not in TASK_STATUSES:
        status = "blocked"
    if old != status and (old, status) not in STATUS_TRANSITIONS:
        _runtime_event(board, "task_status_changed", f"blocked invalid transition {task['id']} {old}->{status}", task_id=task["id"], severity="warning")
        status = "blocked"
    task["status"] = status
    if status == "active":
        board["active_task_id"] = task["id"]
        board["done_when"] = str(_contract_for_task(board, task).get("done_when", task.get("description", "")))
    elif board.get("active_task_id") == task.get("id") and status in {"verified_done", "rejected", "blocked", "superseded"}:
        board["active_task_id"] = ""
    _sync_plan(board)
    _runtime_event(board, "task_status_changed", f"{task['id']} {old}->{status} by {role}", task_id=task["id"], related_record_ids=related)
def _active_task(board: dict[str, Any]) -> dict[str, Any] | None:
    task = _task_by_id(board, str(board.get("active_task_id", "")))
    if task and task.get("status") in {"active", "claimed_done"}:
        return task
    return next((t for t in _tasks(board) if t.get("status") in {"active", "claimed_done"} and t.get("id") != board.get("root_task_id")), None)
def _activate_next_task(board: dict[str, Any]) -> dict[str, Any] | None:
    if _active_task(board):
        return _active_task(board)
    done = {t.get("id") for t in _tasks(board) if t.get("status") == "verified_done"}
    for task in _tasks(board):
        if task.get("id") == board.get("root_task_id") or task.get("status") != "proposed":
            continue
        deps = [str(d) for d in task.get("depends_on", []) if str(d)]
        if all(dep in done for dep in deps):
            _set_task_status(board, task, "active", "runtime")
            return task
    return None
def _normalize_task_data(board: dict[str, Any], raw: dict[str, Any], index: int) -> dict[str, Any]:
    data = raw.get("data") if str(raw.get("record_type", "")) == "task" and isinstance(raw.get("data"), dict) else raw
    root = _root_task_id(board)
    task_id = str(data.get("id") or _new_id(board, f"task-{index}"))
    status = str(data.get("status", "proposed"))
    return {
        "id": task_id,
        "parent_id": data.get("parent_id") if data.get("parent_id") is not None else root,
        "root_id": str(data.get("root_id") or root),
        "description": str(data.get("description", "")).strip(),
        "intent": str(data.get("intent", "")).strip() or "execute_subtask",
        "status": status if status in TASK_STATUSES else "proposed",
        "depends_on": [str(v) for v in data.get("depends_on", [])] if isinstance(data.get("depends_on"), list) else [],
        "contract_id": str(data.get("contract_id") or f"contract-{task_id}-v1"),
        "version": int(data.get("version", 1) or 1),
    }
def _normalize_contract_data(raw: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data") if str(raw.get("record_type", "")) == "contract" and isinstance(raw.get("data"), dict) else raw
    contract = _default_contract(task)
    contract.update({k: v for k, v in data.items() if k in contract})
    contract["id"] = str(data.get("id") or task["contract_id"])
    contract["task_id"] = task["id"]
    contract["version"] = int(data.get("version", 1) or 1)
    if not isinstance(contract.get("success_conditions"), list) or not contract["success_conditions"]:
        contract["success_conditions"] = _default_contract(task)["success_conditions"]
    return contract
def _planner_record_sources(parsed: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = parsed.get("records") if isinstance(parsed.get("records"), list) else []
    tasks: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        rtype = str(item.get("record_type", ""))
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        if rtype == "task" or ("description" in data and "contract_id" in data):
            tasks.append(item)
        elif rtype == "contract" or ("done_when" in data and "success_conditions" in data):
            contracts.append(item)
    for key in ("task", "tasks"):
        value = parsed.get(key)
        items = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
        tasks.extend(items)
    for key in ("contract", "contracts"):
        value = parsed.get(key)
        items = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
        contracts.extend(items)
    return tasks, contracts
def _install_planner_records(board: dict[str, Any], parsed: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    _ensure_root_records(board)
    raw_tasks, raw_contracts = _planner_record_sources(parsed)
    tasks = [_normalize_task_data(board, raw, i + 1) for i, raw in enumerate(raw_tasks)]
    tasks = [task for task in tasks if task["description"]]
    if not tasks:
        return False, "planner produced no task records", {}
    contract_by_task: dict[str, dict[str, Any]] = {}
    for raw in raw_contracts:
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        tid = str(data.get("task_id", ""))
        task = next((t for t in tasks if t["id"] == tid or t["contract_id"] == str(data.get("id", ""))), None)
        if task:
            contract_by_task[task["id"]] = _normalize_contract_data(raw, task)
    root = _task_by_id(board, _root_task_id(board))
    root_contract = _contract_for_task(board, root) if root else None
    board["tasks"] = ([root] if root else []) + tasks
    contracts = ([root_contract] if root_contract else [])
    for task in tasks:
        contract = contract_by_task.get(task["id"]) or _default_contract(task)
        task["contract_id"] = contract["id"]
        contracts.append(contract)
    board["contracts"] = contracts
    record_ids: list[str] = []
    for task in tasks:
        record_ids.append(_publish_record(
            board, _make_record(board, "task", "planner", task, task_id=task["id"], parent_task_id=task.get("parent_id"))
        )["record_id"])
        contract = _contract_for_task(board, task)
        record_ids.append(_publish_record(
            board, _make_record(board, "contract", "planner", contract, task_id=task["id"], parent_task_id=task.get("parent_id"))
        )["record_id"])
    active = _activate_next_task(board)
    data = {"tasks": len(tasks), "contracts": len(contracts) - (1 if root_contract else 0), "active_task_id": active.get("id") if active else ""}
    return True, "", {"record_ids": record_ids, **data}

def _planner_state(board: dict[str, Any]) -> str:
    persona = _personality(board)
    stag = float(board.get("stagnation", board.get("_pressure", {}).get("stagnation", 0)) or 0)
    goal_text = str(board.get("goal", ""))
    parts = [
        f"ROD: {persona or 'default'}",
        f"ROOT_TASK_ID: {_root_task_id(board)}",
        f"ACTIVE_TASK: {goal_text[:config.PROMPT_GOAL_TEXT_MAX] or '(idle)'}",
    ]
    try:
        lt = __import__("comms").colony_goal_text()[:config.PROMPT_GOAL_TEXT_MAX]
        if lt: parts.append(f"LONG_TERM_GOAL: {lt}")
    except Exception: pass
    parts.append(f"PRESSURE: stag={stag:.3f} pwr={float(board.get('power', 1.0 - stag) or 0):.3f}")
    parts.append(_filesystem_context())
    claims = _active_claims()
    if claims and persona != "comms_operator": parts.append(claims)
    desktop_ctx = _desktop_context()
    if desktop_ctx: parts.append(desktop_ctx)
    history_ctx = _format_history(board.get("history", []))
    if history_ctx: parts.append(history_ctx)
    records = board.get("bus_records", [])
    if records:
        compact = [
            {"record_type": r.get("record_type"), "task_id": r.get("task_id"), "data": r.get("data")}
            for r in records[-8:] if isinstance(r, dict)
        ]
        parts.append("RECENT CONTRACT BUS RECORDS:\n" + json.dumps(compact, ensure_ascii=False)[:2400])
    try: parts.append(__import__("comms").format_bus_context(10 if persona == "comms_operator" else 6, for_agent=persona))
    except Exception: pass
    parts.append("Planner must return contract-bus task and contract records JSON:")
    return "\n".join(parts)
def _build_args(verb: str, target: str, value: str) -> dict[str, Any]:
    from actions import DEFAULT_SCROLL_AMOUNT
    target = target.strip("[]")
    if verb == "click":
        return {"selector": target}
    if verb == "write":
        return {"selector": target, "text": value}
    if verb == "press":
        return {"key": target or value}
    if verb == "hotkey":
        raw = value or target
        keys = ["+"] if raw.strip() == "+" else [k.strip() for k in raw.replace("+", ",").split(",") if k.strip()]
        return {"keys": keys}
    if verb == "scroll":
        try:
            return {"selector": target, "amount": int(value) if value else DEFAULT_SCROLL_AMOUNT}
        except ValueError:
            return {"selector": target, "amount": DEFAULT_SCROLL_AMOUNT}
    if verb == "focus":
        return {"window_title": target or value}
    return {}
def _step_policy(step: str) -> tuple[str, str, bool, str]:
    low = step.strip().lower()
    if low.startswith("read_file "):
        return "read", "artifact", False, "can_read_artifacts"
    if low.startswith("write_file "):
        return "write", "artifact", True, "can_mutate_artifacts"
    if low.startswith("wait "):
        return "wait", "unknown", False, "can_observe"
    return "execute", "command", True, "can_execute_commands"
def _verb_policy(verb: str) -> tuple[str, str, bool, str]:
    if verb == "wait":
        return "wait", "unknown", False, "can_observe"
    return (
        {"write": "write", "click": "click", "focus": "other", "press": "other", "hotkey": "other", "scroll": "other"}.get(verb, "other"),
        "ui_surface",
        True,
        "can_mutate_ui",
    )
def _source_for_action(operation: str, target_kind: str, result_verb: str, success: bool) -> tuple[str, str, str]:
    if result_verb == "read_file":
        return "external_readback", "read", "primary"
    if operation == "execute":
        return "tool_result", "execute", "primary" if success else "supporting"
    if target_kind == "ui_surface":
        return "execution_trace", operation, "weak"
    return "execution_trace", operation, "supporting"
def _target_data(kind: str, identifier: str = "", label: str = "") -> dict[str, Any]:
    return {"kind": kind or "unknown", "identifier": identifier or None, "human_label": label or None}
def _publish_action_result(
    board: dict[str, Any],
    task: dict[str, Any],
    role: str,
    *,
    operation: str,
    target_kind: str,
    input_summary: str,
    result: Any,
    mutates_state: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    task_id = task["id"]
    success = bool(getattr(result, "success", False))
    obs = str(getattr(result, "observation", ""))[:config.EVIDENCE_TEXT_MAX]
    source_class, evidence_operation, strength = _source_for_action(operation, target_kind, str(getattr(result, "verb", "")), success)
    evidence: dict[str, Any] | None = None
    evidence_record_id = ""
    if obs:
        evidence = {
            "id": _new_id(board, "evidence"),
            "task_id": task_id,
            "produced_by_role": "tool" if source_class in {"tool_result", "external_readback"} else role,
            "source_class": source_class,
            "source_name": str(getattr(result, "verb", "tool")),
            "operation": evidence_operation,
            "target": _target_data(target_kind, input_summary[:200], input_summary[:200]),
            "observed": {"summary": obs, "text": obs, "structured": getattr(result, "data", {}) or {}, "artifact_refs": []},
            "claim": {"statement": "", "supports_condition_ids": [], "contradicts_condition_ids": [], "confidence": 0.0},
            "trust": {
                "independence": "independent" if source_class in {"tool_result", "external_readback"} else "derived",
                "mutability": "mutating" if mutates_state else "read_only",
                "strength": strength,
                "freshness_cycle": int(board.get("_pressure", {}).get("cycles", 0) or 0),
            },
        }
        evidence_record_id = _publish_record(board, _make_record(board, "evidence", evidence["produced_by_role"], evidence, task_id=task_id, parent_task_id=task.get("parent_id")))["record_id"]
    action = {
        "id": _new_id(board, "action"),
        "task_id": task_id,
        "actor_role": role if role in {"actor", "runtime", "tool"} else "actor",
        "operation": operation if operation in {"click", "type", "hotkey", "write", "execute", "open", "wait", "other"} else "other",
        "target": _target_data(target_kind, input_summary[:200], input_summary[:200]),
        "input_summary": input_summary[:500],
        "result_summary": obs,
        "success_reported_by_tool": success,
        "created_evidence_ids": [evidence["id"]] if evidence else [],
        "mutates_state": mutates_state,
    }
    action_record = _publish_record(board, _make_record(board, "action", role, action, task_id=task_id, parent_task_id=task.get("parent_id")))
    if evidence_record_id:
        _runtime_event(board, "evidence_created", f"evidence {evidence['id']} from {source_class}", task_id=task_id, related_record_ids=[evidence_record_id])
    return action_record, evidence
def _publish_claim(board: dict[str, Any], task: dict[str, Any], role: str, statement: str, evidence_ids: list[str] | None = None, confidence: float = 0.0) -> dict[str, Any]:
    claim = {
        "id": _new_id(board, "claim"),
        "task_id": task["id"],
        "made_by_role": role if role in {"planner", "actor", "observer", "verifier", "reviewer", "runtime", "tool"} else "runtime",
        "statement": statement[:800],
        "about_condition_ids": [str(c.get("id", "")) for c in _contract_for_task(board, task).get("success_conditions", []) if isinstance(c, dict)],
        "confidence": _confidence(confidence),
        "evidence_ids": evidence_ids or [],
    }
    record = _publish_record(board, _make_record(board, "claim", role, claim, task_id=task["id"], parent_task_id=task.get("parent_id")))
    _runtime_event(board, "claim_created", claim["statement"], task_id=task["id"], related_record_ids=[record["record_id"]])
    return record
def _claim_task_done(board: dict[str, Any], task: dict[str, Any], role: str, statement: str, evidence_ids: list[str] | None = None) -> None:
    record = _publish_claim(board, task, role, statement, evidence_ids=evidence_ids, confidence=0.35)
    _set_task_status(board, task, "claimed_done", role, [record["record_id"]])
def _block_task(board: dict[str, Any], task: dict[str, Any], reason: str) -> None:
    history = board.setdefault("history", [])
    history.append({"blocked": task.get("description", ""), "reason": reason[:config.EVIDENCE_TEXT_MAX]})
    _set_task_status(board, task, "blocked", "runtime")
def _render_actor_context(board: dict[str, Any], instruction: str) -> str:
    parts: list[str] = [f"GOAL: {board.get('goal', '')}"]
    screen = str(board.get("screen", "")).strip()
    if screen:
        parts.append(f"SCREEN:\n{screen}")
    plan = board.get("plan", [])
    if plan:
        lines = ["PLAN:"]
        for step in plan:
            if isinstance(step, dict):
                lines.append(f"  - {step.get('status', '?')} {step.get('id', '')}: {step.get('description', '')}")
        parts.append("\n".join(lines))
    task = _active_task(board)
    if task:
        parts.append("ACTIVE_CONTRACT:\n" + json.dumps(_contract_for_task(board, task), ensure_ascii=False)[:2000])
    parts.append(f"INSTRUCTION: {instruction}")
    return "\n\n".join(parts)
def _restore_after_human_task(board: dict[str, Any]) -> None:
    board["priority"] = config.PRI_MAINTENANCE
    board["goal"] = ""
    board["plan"] = []
    board["_human_denials"] = 0
class ObserverAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        from desktop import observe
        role = _effective_role(board, "observer")
        if not _require_capability(board, role, "can_observe", "observe", board.get("active_task_id"), "desktop observation"):
            return {"phase": "observe", "data": {"error": "permission_denied"}}
        try:
            obs = observe()
        except Exception as exc:
            return {"phase": "observe", "data": {"error": str(exc)[:200]}}
        task_id = str(board.get("active_task_id", "")) or None
        evidence = {
            "id": _new_id(board, "evidence"),
            "task_id": task_id,
            "produced_by_role": role,
            "source_class": "direct_observation",
            "source_name": "desktop.observe",
            "operation": "observe",
            "target": {"kind": "ui_surface", "identifier": obs.focused_title or None, "human_label": obs.focused_title or None},
            "observed": {
                "summary": obs.desktop_summary[:500],
                "text": obs.context_text[:config.EVIDENCE_TEXT_MAX] or None,
                "structured": {"focused": obs.focused_title, "chars": len(obs.context_text), "windows": obs.windows[:10]},
                "artifact_refs": [],
            },
            "claim": {"statement": "", "supports_condition_ids": [], "contradicts_condition_ids": [], "confidence": 0.0},
            "trust": {"independence": "independent", "mutability": "read_only", "strength": "primary", "freshness_cycle": int(board.get("_pressure", {}).get("cycles", 0) or 0)},
        }
        record = _publish_record(board, _make_record(board, "evidence", role, evidence, task_id=task_id))
        return {
            "phase": "observe",
            "data": {"focused": obs.focused_title, "chars": len(obs.context_text), "record_id": record["record_id"], "evidence_id": evidence["id"]},
            "writes": {
                "screen": obs.context_text,
                "screen_elements": obs.book,
                "focused_window": obs.focused_title,
                "desktop_summary": obs.desktop_summary,
            },
        }
class SchedulerAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        # comms_operator only plans on human interrupt
        if _personality(board) == "comms_operator":
            if board.get("priority", config.PRI_MAINTENANCE) < config.PRI_HUMAN and not board.get("plan"):
                return None
        _ensure_root_records(board)
        active = _active_task(board)
        if active:
            return {"next": "verifier" if active.get("status") == "claimed_done" else "actor",
                    "data": {"reason": active.get("status"), "task_id": active.get("id")}}
        if _activate_next_task(board):
            return {"next": "actor", "data": {"reason": "task_activated", "task_id": board.get("active_task_id", "")}}
        if not [t for t in _tasks(board) if t.get("id") != board.get("root_task_id")]:
            # Workers always self-direct: use goal or personality mission
            if not board.get("goal"):
                persona = _personality(board) or "worker"
                board["goal"] = f"Self-directed {persona} maintenance: audit, improve, report"
            return {"next": "planner", "data": {"reason": "need_plan"}}
        if any(t.get("status") == "blocked" for t in _tasks(board)):
            return {"next": "reflector", "data": {"reason": "task_blocked"}}
        return {"next": "planner", "data": {"reason": "no_active_task"}}
class PlannerAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        goal = board.get("goal", "")
        if not goal:
            return None
        if not _require_capability(board, "planner", "can_plan", "plan", None, "create task and contract records"):
            return {"phase": "planner.error", "data": {"error": "permission_denied"}}
        log.emit("planner.pending", {"goal": goal[:config.GOAL_TEXT_MAX]})
        llm_out = _call_circuit(board, "planner", _planner_state(board), role="planner")
        parsed = _parse_json(llm_out.text)
        if not parsed:
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {
                "error": "invalid JSON",
                "raw": str(llm_out.text)[:config.PLANNER_ERROR_RAW_MAX],
            })}
        ok, error, install_data = _install_planner_records(board, parsed)
        if not ok:
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {"error": error})}
        writes: dict[str, Any] = {
            "tasks": board.get("tasks", []),
            "contracts": board.get("contracts", []),
            "plan": board.get("plan", []),
            "active_task_id": board.get("active_task_id", ""),
            "done_when": board.get("done_when", ""),
        }
        if _personality(board) == "comms_operator":
            writes["_last_route"] = time.time()
        return {
            "phase": "plan", "next": "actor",
            "data": _llm_event_data(llm_out, install_data),
            "writes": writes,
        }
class ActorAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        from actions import execute_step, execute_verb, is_python_step, VERBS

        task = _active_task(board)
        if not task or task.get("status") != "active":
            return None
        role = _effective_role(board, "actor")
        text = str(task.get("description", "")).strip()
        if not text:
            _block_task(board, task, "no active task description")
            return {"phase": "actor.error", "data": {"error": "no active task description"}, "next": "reflector"}
        history: list[dict[str, Any]] = list(board.get("history", []))

        if is_python_step(text):
            operation, target_kind, mutates_state, flag = _step_policy(text)
            if not _require_capability(board, role, flag, operation, task["id"], text[:200]):
                return {"phase": "actor", "data": {"ok": False, "permission_denied": True, "task_id": task["id"]}, "next": "verifier"}
            result = execute_step(text)
            action_record, evidence = _publish_action_result(
                board, task, role, operation=operation, target_kind=target_kind,
                input_summary=text, result=result, mutates_state=mutates_state,
            )
            evidence_ids = [evidence["id"]] if evidence else []
            history.append({"verb": result.verb, "ok": result.success, "obs": result.observation, "task_id": task["id"]})
            if result.success:
                _claim_task_done(board, task, role, f"Actor reports task completed after {result.verb}.", evidence_ids)
                return {
                    "phase": "actor",
                    "data": {"ok": True, "verb": result.verb, "obs": result.observation[:200], "task_status": "claimed_done", "record_id": action_record["record_id"]},
                    "next": "verifier",
                    "writes": {"plan": board.get("plan", []), "tasks": board.get("tasks", []), "history": history[-config.MAX_HISTORY:]},
                }
            _block_task(board, task, result.observation)
            return {
                "phase": "actor",
                "data": {"ok": False, "verb": result.verb, "obs": result.observation[:200]},
                "next": "reflector",
                "writes": {"plan": board.get("plan", []), "tasks": board.get("tasks", []), "history": history[-config.MAX_HISTORY:]},
            }

        llm_out = _call_circuit(board, "actor", _render_actor_context(board, text), role="actor")
        parsed = _parse_json(llm_out.text)
        if not parsed:
            return {"phase": "actor.error", "data": _llm_event_data(llm_out, {"error": "invalid JSON"})}
        conclusion = str(parsed.get("conclusion", "EXECUTE"))
        actions: list[dict[str, Any]] = parsed.get("actions", []) if isinstance(parsed.get("actions"), list) else []
        actions = [a for a in actions if str(a.get("verb", "")) in VERBS]

        if conclusion == "DONE":
            _claim_task_done(board, task, role, "Actor self-reports task completion.", [])
            return {
                "phase": "actor",
                "data": _llm_event_data(llm_out, {"conclusion": "DONE", "task_status": "claimed_done"}),
                "next": "verifier",
                "writes": {"plan": board.get("plan", []), "tasks": board.get("tasks", [])},
            }
        if conclusion == "CANNOT" or (conclusion == "EXECUTE" and not actions):
            _block_task(board, task, conclusion)
            return {"phase": "actor", "data": _llm_event_data(llm_out, {"conclusion": conclusion, "ok": False}), "next": "reflector"}

        elements: dict[str, Any] = board.get("screen_elements", {})
        evidence_ids: list[str] = []
        action_ids: list[str] = []
        for action in actions:
            verb = str(action.get("verb", ""))
            operation, target_kind, mutates_state, flag = _verb_policy(verb)
            summary = f"{verb} target={action.get('target', '')} value={action.get('value', '')}"
            if not _require_capability(board, role, flag, operation, task["id"], summary):
                return {"phase": "actor", "data": _llm_event_data(llm_out, {"ok": False, "permission_denied": True}), "next": "verifier"}
            result = execute_verb(
                verb,
                _build_args(verb, str(action.get("target", "")), str(action.get("value", ""))),
                elements,
                None,
            )
            action_record, evidence = _publish_action_result(
                board, task, role, operation=operation, target_kind=target_kind,
                input_summary=summary, result=result, mutates_state=mutates_state,
            )
            action_ids.append(action_record["record_id"])
            if evidence:
                evidence_ids.append(evidence["id"])
            history.append({"verb": verb, "ok": result.success, "obs": result.observation, "task_id": task["id"]})
            if not result.success:
                _block_task(board, task, result.observation)
                return {
                    "phase": "actor",
                    "data": _llm_event_data(llm_out, {"conclusion": conclusion, "ok": False, "record_ids": action_ids}),
                    "next": "reflector",
                    "writes": {"plan": board.get("plan", []), "tasks": board.get("tasks", []), "history": history[-config.MAX_HISTORY:]},
                }
        _claim_task_done(board, task, role, f"Actor reports GUI actions completed for task.", evidence_ids)
        return {
            "phase": "actor",
            "data": _llm_event_data(llm_out, {"conclusion": conclusion, "ok": True, "record_ids": action_ids, "task_status": "claimed_done"}),
            "next": "verifier",
            "writes": {"plan": board.get("plan", []), "tasks": board.get("tasks", []), "history": history[-config.MAX_HISTORY:]},
        }
def _records_for_task(board: dict[str, Any], task_id: str) -> dict[str, list[dict[str, Any]]]:
    grouped = {"actions": [], "evidence": [], "claims": [], "prior_verdicts": [], "runtime_events": []}
    for record in board.get("bus_records", []):
        if not isinstance(record, dict):
            continue
        rtype = str(record.get("record_type", ""))
        rid = record.get("task_id")
        if rid not in (task_id, None, "") and record.get("root_task_id") != board.get("root_task_id"):
            continue
        if rtype == "action":
            grouped["actions"].append(record)
        elif rtype == "evidence":
            grouped["evidence"].append(record)
        elif rtype == "claim":
            grouped["claims"].append(record)
        elif rtype == "verdict":
            grouped["prior_verdicts"].append(record)
        elif rtype == "runtime_event":
            grouped["runtime_events"].append(record)
    return grouped
def _verification_packet(board: dict[str, Any], role: str, task: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    root = _task_by_id(board, _root_task_id(board)) or {}
    return {
        "schema_version": VERIFICATION_PACKET_SCHEMA,
        "root_task": root,
        "active_task": task,
        "active_contract": contract,
        "records": _records_for_task(board, task["id"]),
        "verifier_capability": {"role": role, **_capability(role)},
    }
def _normalize_condition_results(parsed: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    raw = parsed.get("condition_results")
    if isinstance(raw, list) and raw:
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "unknown")).lower()
            out.append({
                "condition_id": str(item.get("condition_id", "")),
                "status": status if status in {"satisfied", "unsatisfied", "unknown"} else "unknown",
                "evidence_used": [str(v) for v in item.get("evidence_used", [])] if isinstance(item.get("evidence_used"), list) else [],
                "missing_evidence": [str(v) for v in item.get("missing_evidence", [])] if isinstance(item.get("missing_evidence"), list) else [],
                "reason": str(item.get("reason", ""))[:500],
            })
        if out:
            return out
    return [{
        "condition_id": str(cond.get("id", "")),
        "status": "unknown",
        "evidence_used": [],
        "missing_evidence": ["verifier did not return a condition result"],
        "reason": "Missing verifier condition result.",
    } for cond in contract.get("success_conditions", []) if isinstance(cond, dict)]
def _normalize_verdict_data(board: dict[str, Any], parsed: dict[str, Any] | None, task: dict[str, Any], contract: dict[str, Any], raw_text: str) -> dict[str, Any]:
    parsed = parsed or {}
    verdict = str(parsed.get("verdict", "UNKNOWN")).upper()
    if verdict not in VERDICTS:
        verdict = "UNKNOWN"
    rejected_raw = parsed.get("evidence_rejected", [])
    rejected = []
    if isinstance(rejected_raw, list):
        for item in rejected_raw:
            if isinstance(item, dict):
                rejected.append({"evidence_id": str(item.get("evidence_id", "")), "reason": str(item.get("reason", ""))[:500]})
    return {
        "id": _new_id(board, "verdict"),
        "task_id": task["id"],
        "contract_id": contract["id"],
        "contract_version": int(contract.get("version", 1) or 1),
        "verdict": verdict,
        "confidence": _confidence(parsed.get("confidence", 0.0)),
        "because": str(parsed.get("because", "") or raw_text or "verifier returned no explanation")[:config.EVIDENCE_TEXT_MAX],
        "condition_results": _normalize_condition_results(parsed, contract),
        "evidence_used": [str(v) for v in parsed.get("evidence_used", [])] if isinstance(parsed.get("evidence_used"), list) else [],
        "evidence_rejected": rejected,
        "actor_claim_trusted_as_primary": False,
        "next_recommendation": str(parsed.get("next_recommendation", "gather_evidence")) if str(parsed.get("next_recommendation", "gather_evidence")) in {"continue", "gather_evidence", "replan", "ask_user", "stop"} else "gather_evidence",
    }
def _apply_verdict(board: dict[str, Any], task: dict[str, Any], verdict_record: dict[str, Any], llm_out: LLMResult) -> dict[str, Any]:
    verdict = verdict_record["data"]["verdict"]
    because = str(verdict_record["data"].get("because", ""))[:config.EVIDENCE_TEXT_MAX]
    if verdict == "DONE":
        _set_task_status(board, task, "verified_done", "verifier", [verdict_record["record_id"]])
        board.setdefault("completed", []).append(str(task.get("description", "")))
        board["_last_verified_goal"] = str(board.get("goal", ""))[:config.PROMPT_GOAL_TEXT_MAX]
        board["_last_verified_priority"] = board.get("priority", config.PRI_MAINTENANCE)
        board["_last_verifier_evidence"] = because
        if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN and not any(t.get("status") in {"proposed", "active", "claimed_done"} for t in _tasks(board) if t.get("id") != board.get("root_task_id")):
            _restore_after_human_task(board)
        return {"phase": "verify", "data": _llm_event_data(llm_out, {"verdict": "DONE", "because": because, "record_id": verdict_record["record_id"]}), "next": "fission_judge"}
    if verdict == "NOT_DONE":
        _set_task_status(board, task, "rejected", "verifier", [verdict_record["record_id"]])
        board.setdefault("history", []).append({"denied": task.get("description", ""), "reason": because})
        _post_failure_candidate(board, str(task.get("description", "")), because)
        return {"phase": "verify", "data": _llm_event_data(llm_out, {"verdict": "NOT_DONE", "because": because, "record_id": verdict_record["record_id"]}), "next": "reflector"}
    _set_task_status(board, task, "active", "verifier", [verdict_record["record_id"]])
    return {"phase": "verify", "data": _llm_event_data(llm_out, {"verdict": "UNKNOWN", "because": because, "record_id": verdict_record["record_id"]}), "next": "actor"}
class VerifierAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        task = _active_task(board)
        if not task:
            return None
        role = _effective_role(board, "verifier")
        if not _require_capability(board, role, "can_verify", "verify", task["id"], "contract-bus packet"):
            return {"phase": "verifier.error", "data": {"error": "permission_denied"}}
        if not _require_capability(board, role, "can_publish_verdict", "publish_verdict", task["id"], "verifier verdict"):
            return {"phase": "verifier.error", "data": {"error": "permission_denied"}}
        contract = _contract_for_task(board, task)
        packet = _verification_packet(board, role, task, contract)
        llm_out = _call_circuit(
            board,
            "verifier",
            json.dumps(packet, ensure_ascii=False, separators=(",", ":")),
            role="verifier",
        )
        parsed = _parse_json(llm_out.text)
        verdict = _normalize_verdict_data(board, parsed, task, contract, str(llm_out.text)[:config.EVIDENCE_TEXT_MAX])
        record = _publish_record(board, _make_record(board, "verdict", role, verdict, task_id=task["id"], parent_task_id=task.get("parent_id")))
        _runtime_event(board, "verdict_created", f"{verdict['verdict']} for {task['id']}", task_id=task["id"], related_record_ids=[record["record_id"]])
        return _apply_verdict(board, task, record, llm_out)
class FissionJudgeAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        completed = board.get("completed", [])
        if not completed:
            return None
        latest = str(completed[-1])
        review = _fission_review(board, latest)
        if review.get("verdict") != "credit":
            reason = str(review.get("diagnosis", "fission judge denied credit"))[:300]
            if not board.get("goal") and board.get("_last_verified_goal"):
                board["goal"] = str(board.get("_last_verified_goal", ""))
                board["priority"] = int(board.get("_last_verified_priority", config.PRI_NORMAL) or config.PRI_NORMAL)
            history = board.setdefault("history", [])
            history.append({"denied": latest, "reason": reason, "stage": "fission_judge"})
            _post_failure_candidate(board, latest, reason, behavior="fission_denial", reason="fission denied")
            llm_meta = review.pop("_llm", None) if isinstance(review.get("_llm"), dict) else None
            deny_data = {
                "completed": latest,
                "verdict": "deny",
                "diagnosis": reason,
                "suggestion": str(review.get("suggestion", "")),
                "rule": str(review.get("rule", "")),
            }
            if llm_meta:
                deny_data.update(llm_meta)
            return {"phase": "fission.deny", "data": deny_data, "writes": {"history": history}, "next": "reflector"}
        fissions = board.get("fissions", 0) + 1
        board["fissions"] = fissions
        board.setdefault("fission_credited", []).append(latest)
        fitness = _fitness(board, fissions)
        _post_evolution_candidate(board, fissions, latest, fitness, review)
        llm_meta = review.pop("_llm", None) if isinstance(review.get("_llm"), dict) else None
        fission_data = {
            "fissions": fissions,
            "completed": latest,
            "fitness": fitness,
            "diagnosis": str(review.get("diagnosis", "")),
        }
        if llm_meta:
            fission_data.update(llm_meta)
        return {"phase": "fission", "data": fission_data}
class ReflectorAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        history = board.get("history", [])
        last_denial = next((h for h in reversed(history) if isinstance(h, dict) and h.get("denied")), {})
        pressure = board.get("_pressure", {})
        llm_out = _call_circuit(
            board,
            "reflector",
            (
                f"GOAL: {str(board.get('goal', ''))[:config.PROMPT_GOAL_TEXT_MAX]}\n"
                f"PRESSURE: failures={int(pressure.get('failures', 0) or 0)} "
                f"stag={float(pressure.get('stagnation', 0) or 0):.3f}\n"
                f"DENIED: {str(last_denial.get('denied', ''))[:config.EVIDENCE_TEXT_MAX]}\n"
                f"EVIDENCE: {str(last_denial.get('reason', ''))[:config.EVIDENCE_TEXT_MAX]}\n"
                "Reflect JSON:"
            ),
            role="reflector",
        )
        parsed = _parse_json(llm_out.text) or {}
        reflection = {
            "diagnosis": str(parsed.get("diagnosis", last_denial.get("reason", "verify denied")))[:config.EVIDENCE_TEXT_MAX],
            "suggestion": str(parsed.get("suggestion", "simplify next plan"))[:config.EVIDENCE_TEXT_MAX],
            "rule": str(parsed.get("rule", ""))[:200],
        }
        writes = {"plan": [], "history": history[-config.MAX_HISTORY:] + [{"reflection": reflection}], "reflection": reflection}
        return {"phase": "reflect", "data": _llm_event_data(llm_out, reflection), "writes": writes, "next": "mutator"}
class MutatorAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        pressure = board.get("_pressure", {})
        failures = int(pressure.get("failures", 0) or 0)
        denials = int(board.get("_human_denials", 0) or 0)
        reflection = board.get("reflection")
        if max(failures, denials) < config.MUTATE_AFTER_FAILURES or not isinstance(reflection, dict):
            return {
                "phase": "mutate",
                "data": {"action": "none", "reason": "waiting for failure pressure", "failures": failures},
                "next": "planner",
            }
        plugin_names = _existing_plugin_names()
        elite_dna = _get_elite_dna_context(_personality(board))
        llm_out = _call_circuit(
            board,
            "mutator",
            (
                f"GOAL: {str(board.get('goal', ''))[:config.PROMPT_GOAL_TEXT_MAX]}\n"
                f"REFLECTION: {json.dumps(reflection, ensure_ascii=False)[:config.EVIDENCE_TEXT_MAX]}\n"
                f"PLUGINS: {', '.join(plugin_names) or 'none'}\n"
                f"{elite_dna}"
                f"{_format_history(board.get('history', []))}\n"
                "Mutation JSON:"
            ),
            role="mutator",
        )
        parsed = _parse_json(llm_out.text) or {}
        action = str(parsed.get("action", "none"))
        if action == "patch_prompt":
            if not config.ALLOW_PERSONALITY_PATCH_PROMPT:
                return {
                    "phase": "mutate",
                    "data": _llm_event_data(llm_out, {
                        "action": "none",
                        "reason": "patch_prompt disabled during Phase 0 measurement",
                    }),
                    "next": "planner",
                }
            ok, obs = _apply_prompt_mutation(board, str(parsed.get("content", "")))
            data: dict[str, Any] = {"action": "patch_prompt", "ok": ok, "obs": obs}
            event_data = _llm_event_data(llm_out, data)
            if ok:
                _post_mutation_candidate(board, f"prompts/personalities/{_personality(board)}.txt", obs, obs)
            return {"phase": "mutate", "data": event_data, "next": "planner"}
        if action != "patch_plugin":
            return {
                "phase": "mutate",
                "data": _llm_event_data(llm_out, {"action": "none", "reason": str(parsed.get("content", "no mutation"))[:200]}),
                "next": "planner",
            }
        filename = str(parsed.get("filename", ""))
        ok, obs, diff = _apply_plugin_mutation(filename, str(parsed.get("content", "")))
        data = {"action": "patch_plugin", "filename": filename[:80], "ok": ok, "obs": obs}
        if diff:
            data["diff"] = diff[:500]
        event_data = _llm_event_data(llm_out, data)
        if ok:
            _post_mutation_candidate(board, filename, diff, obs)
            return {"phase": "mutate", "data": event_data, "writes": {"mutation": data}, "next": "planner"}
        return {"phase": "mutate", "data": event_data, "next": "planner"}
def _parse_fission_judge_payload(llm_out: LLMResult) -> dict[str, str] | None:
    parsed = _parse_json(llm_out.text)
    if not parsed:
        return None
    verdict = str(parsed.get("verdict", "deny"))
    if verdict not in {"credit", "deny"}:
        verdict = "deny"
    diagnosis = str(parsed.get("diagnosis", "")).strip() or str(llm_out.text)[:300]
    suggestion = str(parsed.get("suggestion", "")).strip() or "continue toward goal"
    return {
        "verdict": verdict,
        "diagnosis": diagnosis,
        "suggestion": suggestion,
        "rule": str(parsed.get("rule", "")).strip(),
    }
def _fission_review(board: dict[str, Any], completed: str) -> dict[str, str]:
    credited = [str(item) for item in board.get("fission_credited", [])]
    if str(completed) in credited:
        return {
            "verdict": "deny",
            "diagnosis": "duplicate credited milestone",
            "suggestion": "plan a new verifiable step",
            "rule": "",
        }
    pressure = board.get("_pressure", {})
    llm_out = _call_circuit(
        board,
        "fission_judge",
        (
            f"GOAL: {str(board.get('_last_verified_goal') or board.get('goal', ''))[:config.PROMPT_GOAL_TEXT_MAX]}\n"
            f"COMPLETED: {completed[:config.EVIDENCE_TEXT_MAX]}\n"
            f"EVIDENCE: {str(board.get('_last_verifier_evidence', ''))[:config.EVIDENCE_TEXT_MAX]}\n"
            f"PRESSURE: stag={float(pressure.get('stagnation', 0) or 0):.3f} "
            f"fissions={int(board.get('fissions', 0) or 0)}\n"
            f"{_format_history(board.get('history', [])[-3:])}\n"
            "Fission judge JSON:"
        ),
        role="fission_judge",
        cache_key="fission_judge",
    )
    review = _parse_fission_judge_payload(llm_out)
    if review:
        review["_llm"] = _llm_event_data(llm_out)
        return review
    return {
        "verdict": "deny",
        "diagnosis": str(llm_out.text)[:300] or "invalid judge JSON",
        "suggestion": "retry with clearer milestone",
        "rule": "",
        "_llm": _llm_event_data(llm_out, {"judge_error": "invalid_json"}),
    }

def _fitness(board: dict[str, Any], fissions: int) -> float:
    """MAP-Elites fitness: power + fission bonus - stagnation penalty."""
    stag = float(board.get("_pressure", {}).get("stagnation", 0) or 0)
    power = float(board.get("power", 1.0 - stag) or 0)
    return round(max(0.0, min(1.0, 0.55 + power * 0.35 + min(0.2, fissions * 0.02) - stag * 0.25)), 4)
def _niche(board: dict[str, Any], behavior: str) -> str:
    stag = float(board.get("_pressure", {}).get("stagnation", 0) or 0)
    band = "high" if stag >= config.STAG_ESCALATE else "mid" if stag >= 0.3 else "low"
    safe = re.sub(r"[^a-z0-9_]+", "_", behavior.lower()).strip("_") or "general"
    return f"{safe}:{band}"
def _post_evolution_candidate(board: dict[str, Any], fissions: int, completed: str, fitness: float, review: dict[str, str] | None = None) -> None:
    try:
        import comms
        comms.post_evolve(comms.agent_id(), comms.agent_id(), "retain", fitness=fitness,
                          completed=completed, reason="fission credit",
                          data={"niche": _niche(board, "general_task"), "fissions": fissions})
    except Exception:
        pass
def _post_failure_candidate(board: dict[str, Any], done_when: str, evidence: str, **_kw: Any) -> None:
    try:
        import comms
        stag = float(board.get("_pressure", {}).get("stagnation", 0) or 0)
        fit = round(max(0.0, 0.35 - stag * 0.25), 4)
        comms.post_evolve(comms.agent_id(), comms.agent_id(), "evict", fitness=fit,
                          completed=str(done_when), reason="verify denied",
                          data={"niche": _niche(board, "denial"), "evidence": str(evidence)[:200]})
    except Exception:
        pass
def _get_elite_dna_context(persona: str) -> str:
    """Pull best prompt DNA from breed archive for crossover context."""
    try:
        import json as _json
        archive_path = config.PROMPTS_DIR.parent / "runtime" / "breed_archive.json"
        if not archive_path.exists():
            return ""
        data = _json.loads(archive_path.read_text(encoding="utf-8"))
        archive = data.get("archive", {}) if isinstance(data, dict) else {}
        best_dna, best_fit = "", 0.0
        for elite in archive.values():
            if not isinstance(elite, dict):
                continue
            fit = float(elite.get("fitness", 0) or 0)
            dna = str(elite.get("prompt_dna", "")).strip()
            if dna and fit > best_fit and elite.get("target") != persona:
                best_dna, best_fit = dna, fit
        if best_dna:
            return f"ELITE_DNA (fitness={best_fit:.2f}, use for crossover):\n{best_dna[:800]}\n"
    except Exception:
        pass
    return ""


def _apply_prompt_mutation(board: dict[str, Any], new_prompt: str) -> tuple[bool, str]:
    """Mutate the current persona's prompt file with new DNA."""
    persona = _personality(board)
    if not persona:
        return False, "no persona"
    cleaned = new_prompt.strip()
    if len(cleaned) < 20:
        return False, "prompt too short"
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000]
    pfile = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
    try:
        before = pfile.read_text(encoding="utf-8").strip() if pfile.exists() else ""
    except OSError:
        return False, "read failed"
    if before == cleaned:
        return False, "unchanged"
    pfile.write_text(cleaned, encoding="utf-8")
    return True, f"patched {persona}.txt ({len(cleaned)} chars)"


def _existing_plugin_names() -> list[str]:
    try:
        deny = set(config.PHASE0_PLUGIN_MUTATION_DENYLIST)
        return [p.name for p in sorted(config.PLUGINS_DIR.glob("*.py")) if p.is_file() and p.name not in deny]
    except OSError:
        return []


def _resolve_existing_plugin(filename: str) -> Path | None:
    raw = str(filename).strip().replace("\\", "/")
    if raw.startswith("plugins/"):
        raw = raw[len("plugins/"):]
    if "/" in raw or not _PLUGIN_NAME_RE.fullmatch(raw):
        return None
    if raw in config.PHASE0_PLUGIN_MUTATION_DENYLIST:
        return None
    path = (config.PLUGINS_DIR / raw).resolve()
    try:
        path.relative_to(config.PLUGINS_DIR.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None
def _apply_plugin_mutation(filename: str, content: str) -> tuple[bool, str, str]:
    path = _resolve_existing_plugin(filename)
    if path is None:
        return False, "mutable existing plugins/[name].py required", ""
    ok, cleaned, err = validate_python(_strip_code_fence(content))
    if not ok:
        return False, err, ""
    cleaned = cleaned.rstrip() + "\n"
    if "def run(" not in cleaned:
        return False, "plugin must define def run(board)", ""
    try:
        before = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}", ""
    if before == cleaned:
        return False, "plugin unchanged", ""
    diff = "\n".join(list(difflib.unified_diff(
        before.splitlines(), cleaned.splitlines(),
        fromfile=f"a/{path.name}", tofile=f"b/{path.name}", lineterm="", n=2))[:40])
    try:
        path.write_text(cleaned, encoding="utf-8")
        py_compile.compile(str(path), doraise=True)
        # Trial exec in isolated namespace to catch import/name errors
        exec(compile(cleaned, str(path), "exec"), {"__builtins__": __builtins__})
    except Exception as exc:
        try:
            path.write_text(before, encoding="utf-8")
        except OSError:
            pass
        return False, f"apply failed: {exc}", ""
    return True, f"patched plugins/{path.name}", diff
def _post_mutation_candidate(board: dict[str, Any], filename: str, diff: str, obs: str) -> None:
    try:
        import comms
        fit = round(max(0.0, min(0.6, 0.52 - float(board.get("_pressure", {}).get("stagnation", 0) or 0) * 0.12)), 4)
        comms.post_evolve(comms.agent_id(), comms.agent_id(), "patch_plugin",
                          fitness=fit, completed=str(filename)[:80], reason="mutator patch",
                          diff=diff, data={"niche": _niche(board, "plugin_patch")})
    except Exception:
        pass
