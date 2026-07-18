from dataclasses import dataclass, field
import json
import re
import time
from typing import Any


JsonDict = dict[str, Any]


def deep_merge(base: JsonDict, override: JsonDict) -> JsonDict:
    """Return a new dict: override laid over base, nested dicts merged recursively.
    A non-dict override value replaces the base value wholesale."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def drop_nulls(obj: Any) -> Any:
    """Recursively drop keys whose value is None (an unsent API field),
    and drop any nested object left empty by that pruning. Lists are pruned in place."""
    if isinstance(obj, dict):
        pruned: JsonDict = {}
        for key, value in obj.items():
            if value is None:
                continue
            cleaned = drop_nulls(value)
            if isinstance(cleaned, dict) and not cleaned:
                continue
            pruned[key] = cleaned
        return pruned
    if isinstance(obj, list):
        return [drop_nulls(item) for item in obj]
    return obj


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


@dataclass(frozen=True)
class NodeOutput:
    signal: str
    patch: JsonDict = field(default_factory=dict)
    record: Record | None = None
    evidence: JsonDict = field(default_factory=dict)

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


_INTERP_ORDER = ["execute", "verify", "recover"]


def render_interpretation_table(goal: str, interps: JsonDict | None) -> str:
    """The living word — the goal-interpretation rows — rendered for the tail of every user message.

    Each thinking faculty keeps exactly one row: what it has LEARNED (not a restating of
    the goal), rewritten in place whensoever it acts. The immutable root goal follows as a
    fixed lodestar footer. The table is bounded (one row per faculty), never accumulates,
    and never truncates. It rides the volatile user tail, so it costs no prefix cache."""
    interps = interps or {}
    lines = [
        "THE LIVING WORD — this is thy sole thread across wakings, and thou plannest FROM it, not from the root goal. Each faculty keepeth one row: not a restating of the goal (the goal changeth never and needeth no echo), but what it hath LEARNED—what the world revealed, what deed was tried and how it fared, what obstacle now standeth, what the next true deed must therefore be. Try every row against the fresh observation and correct what it gainsayeth ere thou actest. A row that merely repeateth the goal is wasted and blind; write what advanceth the work:",
    ]
    for faculty in _INTERP_ORDER:
        sentence = str(interps.get(faculty) or "").strip()
        lines.append(f"[{faculty}] {sentence}" if sentence else f"[{faculty}] (not yet interpreted)")
    lines.append(f"[the root goal, a fixed lodestar to consult but never to plan from] {goal}")
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
    """Return the live outgoing signal vocabulary, excluding reserved 'error'."""
    if not node:
        return []
    return sorted(s for s in allowed_signals(wiring, node) if s != "error")


def state_brief(state: JsonDict) -> JsonDict:
    """Present deed facts; the living word is extracted from here into the user tail."""
    current_deed = state.get("current_deed") or {}
    return {
        "goal_interpretations": dict(state.get("goal_interpretations") or {}),
        "latest_counsel": state.get("latest_counsel") or "",
        "current_deed": {"description": current_deed.get("description", "")},
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
        "screen": artifact.get("screen", {}) if isinstance(artifact, dict) else {},
    }


def execution_evidence(state: JsonDict) -> JsonDict:
    turn = state.get("turn_executions") or {}
    return {
        "faculties": turn if isinstance(turn, dict) else {},
        "provenance": (
            "actor-authored record: what code the executor authored and enacted, by its own account. "
            "This is the actor's testimony about what it did, not proof of world-effect. "
            "Independent world state is carried separately in the observation field."
        ),
    }


def bump_failure_streak(state: JsonDict) -> JsonDict:
    """Count denials since the last witnessed deed, monotonically. The tally is NOT
    keyed to the deed's wording: a reworded description of the same obstacle cannot reset
    it. Only a verifier confirmation clears it (see node_verify). The higher it climbs, the
    wider recovery must forsake its tried approaches."""
    previous = state.get("failure_streak") or {}
    count = int(previous.get("count", 0) or 0) + 1
    return {"failure_streak": {"count": count, "updated_at": time.time()}}
