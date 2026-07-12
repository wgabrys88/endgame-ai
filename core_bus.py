from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any


JsonDict = dict[str, Any]


class BusContractError(RuntimeError):
    """Base class for mechanical organism contract failures."""


class TopologyContractError(BusContractError):
    """Raised when a node emits a signal with no valid topology edge."""


class NodeRecordContractError(BusContractError):
    """Raised when a node returns an invalid bus/output/record shape."""


@dataclass(frozen=True)
class Record:
    """Unified record format for all LLM organs."""

    record_type: str
    data: JsonDict
    reasoning: str = ""

    def to_json(self) -> JsonDict:
        return {"record_type": self.record_type, "data": self.data, "reasoning": self.reasoning}

    @classmethod
    def from_json(cls, obj: JsonDict) -> "Record":
        return cls(record_type=obj.get("record_type", ""), data=obj.get("data", {}), reasoning=obj.get("reasoning", ""))

    @classmethod
    def create(cls, record_type: str, data: JsonDict, reasoning: str = "") -> "Record":
        return cls(record_type=record_type, data=data, reasoning=reasoning)


@dataclass(frozen=True)
class NodeOutput:
    signal: str
    patch: JsonDict = field(default_factory=dict)
    record: Record | None = None
    evidence: JsonDict = field(default_factory=dict)

    def as_tuple(self) -> tuple[str, JsonDict]:
        return self.signal, dict(self.patch)

    def trace(self, *, node: str) -> JsonDict:
        record_type = None
        record_json = None
        if isinstance(self.record, Record):
            record_type = self.record.record_type
            record_json = self.record.to_json()
        elif isinstance(self.record, dict):
            record_type = self.record.get("record_type")
            record_json = dict(self.record)
        omitted = {
            "goal",
            "effective_goal",
            "state",
            "focus",
            "observation",
            "desktop_tree_text",
            "action_index",
            "observation_artifact",
            "repair_validation",
            "repair_baseline",
            "before",
            "after",
        }
        return {
            "kind": "endgame.node_output.v1",
            "node": node,
            "signal": self.signal,
            "record_type": record_type,
            "patch_keys": sorted(self.patch.keys()),
            "evidence_keys": sorted(self.evidence.keys()),
            "record": record_json,
            "patch": {key: value for key, value in self.patch.items() if key not in omitted},
            "evidence": {key: value for key, value in self.evidence.items() if key not in omitted},
            "emitted_at": time.time(),
        }


def emit(signal: str, patch: JsonDict | None = None, *, record: Record | JsonDict | None = None, evidence: JsonDict | None = None) -> NodeOutput:
    if not isinstance(signal, str) or not signal.strip():
        raise ValueError("bus signal must be a non-empty string")
    if patch is not None and not isinstance(patch, dict):
        raise TypeError("bus patch must be a dict")
    if record is not None and not isinstance(record, (Record, dict)):
        raise TypeError("bus record must be a Record or dict when provided")
    if evidence is not None and not isinstance(evidence, dict):
        raise TypeError("bus evidence must be a dict when provided")
    record_obj = Record.from_json(record) if isinstance(record, dict) else record
    return NodeOutput(signal=signal.strip(), patch=dict(patch or {}), record=record_obj, evidence=dict(evidence or {}))


# Rolling narrative bound. effective_goal = immutable root goal + append-only narrative; in the
# analysed run it grew unbounded (tens of KB) and inflated every prompt, contradicting the README's
# "minimal rolling buffer" principle. Keep the root goal (first paragraph) plus the most recent
# NARRATIVE_TAIL_CHARS of appended history so recent context is preserved while growth is bounded.
NARRATIVE_TAIL_CHARS = 12000


def append_narrative(effective_goal: str, line: str, *, root_goal: str = "") -> str:
    combined = f"{effective_goal}{line}"
    if len(combined) <= NARRATIVE_TAIL_CHARS:
        return combined
    head = root_goal if root_goal and combined.startswith(root_goal) else ""
    tail = combined[-NARRATIVE_TAIL_CHARS:]
    marker = "\n\n[...earlier narrative trimmed for token efficiency...]\n"
    return f"{head}{marker}{tail}" if head else f"{marker.lstrip()}{tail}"


def coerce_node_output(node: str, result: Any) -> NodeOutput:
    if isinstance(result, NodeOutput):
        return result
    if isinstance(result, tuple) and len(result) == 2:
        signal, patch = result
        if not isinstance(signal, str) or not signal:
            raise NodeRecordContractError(f"node '{node}' contract violation: signal must be a non-empty string")
        if not isinstance(patch, dict):
            raise NodeRecordContractError(f"node '{node}' contract violation: patch must be dict")
        return emit(signal, patch)
    raise NodeRecordContractError(f"node '{node}' contract violation: expected NodeOutput or (signal, patch)")


def allowed_signals(wiring: JsonDict, node: str) -> set[str]:
    edges = wiring.get("topology", {}).get("edges", {})
    node_edges = edges.get(node, {})
    if not isinstance(node_edges, dict):
        return set()
    return {str(signal) for signal in node_edges}


def validate_signal(wiring: JsonDict, node: str, signal: str) -> None:
    signals = allowed_signals(wiring, node)
    if signals and signal not in signals:
        allowed = ", ".join(sorted(signals))
        raise TopologyContractError(f"node '{node}' emitted signal '{signal}' outside topology contract; allowed: {allowed}")


def emergent_signals(wiring: JsonDict, node: str | None) -> list[str]:
    """The signals a node may emit are emergent from wiring: they are exactly its
    outgoing topology edges, minus the universal 'error' fallback. This replaces the
    hand-maintained record_contracts.enums.next_signal — the contract of what a node
    outputs comes from what it is wired to, not a separate registry."""
    if not node:
        return []
    return sorted(s for s in allowed_signals(wiring, node) if s != "error")


def _plan_intent(state: JsonDict) -> list[JsonDict]:
    plan = state.get("plan")
    intent = plan.get("intent", []) if isinstance(plan, dict) else []
    return intent if isinstance(intent, list) else []


def repair_validation_brief(state: JsonDict) -> JsonDict:
    repair = state.get("repair_validation") or {}
    if not isinstance(repair, dict) or not repair:
        return {}
    probe = repair.get("probe") or {}
    commit = repair.get("commit") or {}
    return {
        "repair_id": repair.get("repair_id"),
        "status": repair.get("status"),
        "resolved": repair.get("resolved"),
        "summary": repair.get("summary"),
        "expected_validation": repair.get("expected_validation"),
        "candidate_commit": commit.get("commit") if isinstance(commit, dict) else None,
        "activation": repair.get("activation", {}),
        "probe": {
            "failure_signature": probe.get("failure_signature"),
            "description": probe.get("description"),
            "done_when": probe.get("done_when"),
        } if isinstance(probe, dict) and probe else {},
        "comparison": repair.get("comparison"),
        "conclusion": repair.get("conclusion"),
    }


def state_brief(state: JsonDict) -> JsonDict:
    """Compact operational focus. The full append-only narrative remains in state, never in every prompt."""
    current_step = state.get("current_step") or {}
    intent = _plan_intent(state)
    now = time.time()
    started_at = state.get("started_at")
    deadline_at = state.get("deadline_at")
    step_index = int(state.get("step", 0) or 0)
    return {
        "tick": state.get("tick"),
        "current_node": state.get("current_node"),
        "step_index": step_index,
        "current_step": {"description": current_step.get("description", ""), "done_when": current_step.get("done_when", "")},
        "remaining_plan_steps": max(0, len(intent) - step_index),
        "completed_step_count": len(state.get("completed_steps") or []),
        "last_signal": state.get("last_signal"),
        "last_error": state.get("last_error"),
        "last_verification": state.get("last_verification", {}),
        "last_reflection": state.get("last_reflection", {}),
        "last_failure": state.get("last_failure", {}),
        "failure_streak": state.get("failure_streak", {}),
        "repair_validation": repair_validation_brief(state),
        "has_action_frame": bool(state.get("action_frame")),
        "timing": {
            "started_at": started_at,
            "deadline_at": deadline_at,
            "duration_seconds": state.get("duration_seconds"),
            "elapsed_seconds": round(now - float(started_at), 3) if started_at is not None else None,
            "remaining_seconds": round(float(deadline_at) - now, 3) if deadline_at is not None else None,
        },
    }


def focused_elements(state: JsonDict) -> JsonDict:
    """Expand only UI ids already named by the active focus; never dump the whole action index."""
    action_index = state.get("action_index") or {}
    if not isinstance(action_index, dict):
        return {}
    focus_sources = {
        "current_step": state.get("current_step") or {},
        "action_frame": state.get("action_frame") or {},
        "last_action": state.get("last_action") or {},
        "last_reflection": state.get("last_reflection") or {},
        "focus_ids": state.get("focus_ids") or [],
    }
    focus_text = json.dumps(focus_sources, ensure_ascii=False, default=str)
    fields = ("id", "name", "role", "action", "rect", "enabled", "automation_id", "class_name", "hwnd", "depth")
    # The action_index key is the identity-stable id (e_<runtime_id>) that the model cites, so a
    # single membership test suffices — no positional short_id, no fallback matching.
    return {
        node_id: {key: node[key] for key in fields if key in node}
        for node_id, node in action_index.items()
        if isinstance(node, dict) and str(node_id) in focus_text
    }


def observation_brief(state: JsonDict) -> JsonDict:
    artifact = state.get("observation_artifact") or {}
    tree = artifact.get("desktop_tree") if isinstance(artifact, dict) else {}
    return {
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "focused_elements": focused_elements(state),
        "observed_at": state.get("observed_at"),
        "screen": artifact.get("screen", {}) if isinstance(artifact, dict) else {},
        "scan_stats": artifact.get("scan_stats", {}) if isinstance(artifact, dict) else {},
        "rendered_node_count": state.get("rendered_node_count") or (tree or {}).get("rendered_node_count"),
        "max_llm_nodes": state.get("max_llm_nodes") or (tree or {}).get("max_llm_nodes"),
        "llm_node_limit_hit": state.get("llm_node_limit_hit") or (tree or {}).get("llm_node_limit_hit"),
        "elements_truncated": (tree or {}).get("elements_truncated", False),
        "elements_dropped_per_window": (tree or {}).get("elements_dropped_per_window", {}),
    }


def _last_denial(state: JsonDict) -> str:
    # Surface the most recent verify denial reason as an explicit, top-level constraint so the
    # next execute/frame attempt converges instead of re-guessing. Empirically the wheel burned
    # ~7 laps per step because the denial reason (e.g. "use read_file, not a directory listing")
    # was only reachable buried inside focus.state_brief.last_verification.
    lv = state.get("last_verification") or {}
    if isinstance(lv, dict) and lv.get("success") is False:
        return str(lv.get("reasoning", "")).strip()
    return ""


def execution_evidence(state: JsonDict) -> JsonDict:
    denial = _last_denial(state)
    turn = state.get("turn_executions") or {}
    if isinstance(turn, dict) and turn:
        evidence: JsonDict = {"faculties": turn}
    else:
        evidence = {
            "last_action": state.get("last_action") or {},
            "last_result": state.get("last_result") or {},
            "last_error": state.get("last_error"),
            "last_failure": state.get("last_failure") or {},
        }
    if denial:
        evidence["unsatisfied_requirement"] = denial
    return evidence


def failure_signature(state: JsonDict) -> str:
    step = state.get("current_step") or {}
    parts = {
        "step": step.get("description", ""),
        "done_when": step.get("done_when", ""),
        "failure": state.get("last_failure") or {},
        "verification": state.get("last_verification") or {},
        "executions": state.get("turn_executions") or {},
    }
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def update_failure_streak(state: JsonDict) -> JsonDict:
    signature = failure_signature(state)
    previous = state.get("failure_streak") or {}
    count = int(previous.get("count", 0) or 0) + 1 if previous.get("signature") == signature else 1
    return {"failure_streak": {"signature": signature, "count": count, "updated_at": time.time()}}
