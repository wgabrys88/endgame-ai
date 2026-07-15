from dataclasses import dataclass, field
import hashlib
import json
import re
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
        record_summary = None
        if isinstance(self.record, Record):
            record_type = self.record.record_type
            record_summary = {"record_type": record_type, "data_keys": sorted(self.record.data)}
        elif isinstance(self.record, dict):
            record_type = self.record.get("record_type")
            data = self.record.get("data")
            record_summary = {"record_type": record_type, "data_keys": sorted(data) if isinstance(data, dict) else []}
        return {
            "kind": "endgame.node_output.v1",
            "node": node,
            "signal": self.signal,
            "record_type": record_type,
            "patch_keys": sorted(self.patch.keys()),
            "evidence_keys": sorted(self.evidence.keys()),
            "record": record_summary,
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
    if signal not in signals:
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


def state_brief(state: JsonDict) -> JsonDict:
    """Compact operational focus plus the bounded continuity narrative."""
    current_step = state.get("current_step") or {}
    intent = _plan_intent(state)
    step_index = int(state.get("step", 0) or 0)
    narrative = str(state.get("effective_goal") or "")
    root_goal = str(state.get("goal") or "")
    if root_goal and narrative.startswith(root_goal):
        narrative = narrative[len(root_goal):].lstrip()
    return {
        "tick": state.get("tick"),
        "depth": state.get("_depth", 0),
        "current_node": state.get("current_node"),
        "frontier": list(state.get("frontier") or []),
        "narrative": narrative,
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
        "has_action_frame": bool(state.get("action_frame")),
    }


def focused_elements(state: JsonDict) -> JsonDict:
    """Expand geometry/identity only for genuinely focused or action-framed ids.

    desktop_tree_text already carries the readable overview — id, role, name,
    [active]/[focused] markers, [action], and ~text hint — for every visible
    element. This map therefore adds ONLY what the tree lacks (enabled, rect,
    automation_id, class_name, hwnd, depth) and ONLY for the element(s) currently
    focused or named by an action_frame. It never re-emits the whole tree as
    structured metadata, so the payload carries each element once. Element
    targeting uses the full in-memory action_index, not this brief.
    """
    action_index = state.get("action_index") or {}
    if not isinstance(action_index, dict):
        return {}
    tree_text = str(state.get("desktop_tree_text") or "")
    visible_ids = {line.strip().split(" ", 1)[0] for line in tree_text.splitlines() if line.strip()}
    frame_text = json.dumps(state.get("action_frame") or {}, ensure_ascii=False, default=str)
    framed_ids = set(re.findall(r"\b(?:e|W)\d+\b", frame_text))
    detail_fields = ("name", "role", "action", "enabled", "rect", "automation_id", "class_name", "hwnd", "depth")
    mapped: JsonDict = {}
    for node_id, node in action_index.items():
        if not isinstance(node, dict) or str(node_id) not in visible_ids:
            continue
        if node.get("focused") or str(node_id) in framed_ids:
            mapped[str(node_id)] = {key: node[key] for key in detail_fields if key in node}
    return mapped


def observation_brief(state: JsonDict) -> JsonDict:
    artifact = state.get("observation_artifact") or {}
    tree = artifact.get("desktop_tree") if isinstance(artifact, dict) else {}
    return {
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "focused_elements": focused_elements(state),
        "observed_at": state.get("observed_at"),
        "settle_seconds": artifact.get("settle_seconds") if isinstance(artifact, dict) else None,
        "screen": artifact.get("screen", {}) if isinstance(artifact, dict) else {},
        "scan_stats": artifact.get("scan_stats", {}) if isinstance(artifact, dict) else {},
        "rendered_node_count": state.get("rendered_node_count") or (tree or {}).get("rendered_node_count"),
        "max_llm_nodes": state.get("max_llm_nodes") or (tree or {}).get("max_llm_nodes"),
        "llm_node_limit_hit": state.get("llm_node_limit_hit") or (tree or {}).get("llm_node_limit_hit"),
        "elements_truncated": (tree or {}).get("elements_truncated", False),
        "elements_dropped_per_window": (tree or {}).get("elements_dropped_per_window", {}),
        "elements_dropped_global": (tree or {}).get("elements_dropped_global", 0),
    }


def _last_denial(state: JsonDict) -> str:
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
