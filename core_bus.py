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


_INTERP_ORDER = ["execute", "verify", "reflect", "frame"]

INTERP_MIN_CHARS = 300


def render_interpretation_table(goal: str, interps: JsonDict | None) -> str:
    """The goal-interpretation table, rendered for the tail of every user message.

    Row one is the immutable root goal. Each thinking faculty keeps exactly one row —
    its own single-sentence reading of the ultimate goal — which it rewrites in place
    whensoever it acts. The table is bounded (one row per faculty), never accumulates,
    and never truncates. It rides the volatile user tail, so it costs no prefix cache."""
    interps = interps or {}
    lines = [
        "GOAL INTERPRETATION TABLE — the root goal is immutable and standeth first; "
        "each thinking faculty keepeth one row below it, being that faculty's own "
        "single-sentence reading of the ultimate goal, rewritten whensoever it acteth:",
        f"[ROOT GOAL] {goal}",
    ]
    for faculty in _INTERP_ORDER:
        sentence = str(interps.get(faculty) or "").strip()
        lines.append(f"[{faculty}] {sentence}" if sentence else f"[{faculty}] (not yet interpreted)")
    return "\n".join(lines)


def with_interpretation(interps: JsonDict | None, faculty: str, sentence: str) -> JsonDict:
    """Return a copy of the interpretation table with one faculty's row rewritten."""
    merged = dict(interps or {})
    merged[faculty] = str(sentence or "").strip()
    return merged


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


def state_brief(state: JsonDict) -> JsonDict:
    """Compact operational focus of the NOW. The sole within-waking continuity is the
    immutable goal and the goal-interpretation table (carried to the user tail); there
    is no memory, no history, no prior turn — only this present state and the fresh
    observation that reveals the world as it now is."""
    current_deed = state.get("current_deed") or {}
    return {
        "tick": state.get("tick"),
        "current_node": state.get("current_node"),
        "goal_interpretations": dict(state.get("goal_interpretations") or {}),
        "latest_counsel": state.get("latest_counsel") or "",
        "current_deed": {"description": current_deed.get("description", ""), "done_when": current_deed.get("done_when", "")},
        "last_signal": state.get("last_signal"),
        "last_verification": state.get("last_verification", {}),
        "last_reflection": state.get("last_reflection", {}),
        "failure_streak": state.get("failure_streak", {}),
        "has_action_frame": bool(state.get("action_frame")),
    }


def focused_elements(state: JsonDict) -> JsonDict:
    """Expand geometry/identity only for genuinely focused or action-framed ids.

    desktop_tree_text already carries the readable overview — id, role, name,
    [active]/[focused] markers, [action], and ~text hint — for every visible
    element. This map therefore adds ONLY what the tree lacks (enabled, rect,
    automation_id, class_name) and ONLY for the element(s) currently focused or
    named by an action_frame. It never re-emits the whole tree as structured
    metadata, so the payload carries each element once. Element targeting uses
    the full in-memory action_index, not this brief.
    """
    action_index = state.get("action_index") or {}
    if not isinstance(action_index, dict):
        return {}
    tree_text = str(state.get("desktop_tree_text") or "")
    visible_ids = {line.strip().split(" ", 1)[0] for line in tree_text.splitlines() if line.strip()}
    frame_text = json.dumps(state.get("action_frame") or {}, ensure_ascii=False, default=str)
    framed_ids = set(re.findall(r"\b(?:e|W)\d+\b", frame_text))
    detail_fields = ("name", "role", "action", "enabled", "rect", "automation_id", "class_name")
    mapped: JsonDict = {}
    for node_id, node in action_index.items():
        if not isinstance(node, dict) or str(node_id) not in visible_ids:
            continue
        if node.get("focused") or str(node_id) in framed_ids:
            mapped[str(node_id)] = {key: node[key] for key in detail_fields if key in node}
    return mapped


def observation_brief(state: JsonDict) -> JsonDict:
    artifact = state.get("observation_artifact") or {}
    return {
        "provenance": (
            "independent world state: the settled desktop as an outside eye beheld it, "
            "produced by the OS and applications, not authored by the actor."
        ),
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "focused_elements": focused_elements(state),
        "observed_at": state.get("observed_at"),
        "settle_seconds": artifact.get("settle_seconds") if isinstance(artifact, dict) else None,
        "screen": artifact.get("screen", {}) if isinstance(artifact, dict) else {},
    }


def _last_denial(state: JsonDict) -> str:
    lv = state.get("last_verification") or {}
    if isinstance(lv, dict) and lv.get("success") is False:
        return str(lv.get("reasoning", "")).strip()
    return ""


def _action_event_count(turn: JsonDict) -> int:
    total = 0
    if isinstance(turn, dict):
        for faculty in turn.values():
            events = faculty.get("action_events") if isinstance(faculty, dict) else None
            if isinstance(events, list):
                total += len(events)
    return total


def execution_evidence(state: JsonDict) -> JsonDict:
    denial = _last_denial(state)
    turn = state.get("turn_executions") or {}
    evidence: JsonDict = {"faculties": turn if isinstance(turn, dict) else {}}
    evidence["provenance"] = (
        "actor-authored record: the [action_events] the runner's own primitives recorded of themselves. "
        "This is the actor's testimony about what it did, not proof of world-effect. "
        "Independent world state is carried separately in the observation field."
    )
    evidence["action_event_count"] = _action_event_count(turn)
    if denial:
        evidence["unsatisfied_requirement"] = denial
    return evidence


def failure_signature(state: JsonDict) -> str:
    deed = state.get("current_deed") or {}
    parts = {
        "deed": deed.get("description", ""),
        "done_when": deed.get("done_when", ""),
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
