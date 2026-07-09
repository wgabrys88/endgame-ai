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
    """Unified record format for ALL organs - single source of truth."""
    record_type: str
    data: JsonDict
    reasoning: str = ""

    def to_json(self) -> JsonDict:
        return {
            "record_type": self.record_type,
            "data": self.data,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_json(cls, obj: JsonDict) -> "Record":
        return cls(
            record_type=obj.get("record_type", ""),
            data=obj.get("data", {}),
            reasoning=obj.get("reasoning", ""),
        )

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
        return {
            "kind": "endgame.node_output.v1",
            "node": node,
            "signal": self.signal,
            "record_type": record_type,
            "patch_keys": sorted(self.patch.keys()),
            "evidence_keys": sorted(self.evidence.keys()),
            "record": record_json,
            "patch": self.patch,
            "evidence": self.evidence,
            "emitted_at": time.time(),
            "effective_goal": self.patch.get("effective_goal") or self.evidence.get("effective_goal"),
        }


def emit(
    signal: str,
    patch: JsonDict | None = None,
    *,
    record: Record | JsonDict | None = None,
    evidence: JsonDict | None = None,
) -> NodeOutput:

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
    return {str(signal) for signal in node_edges.keys()}


def validate_signal(wiring: JsonDict, node: str, signal: str) -> None:
    signals = allowed_signals(wiring, node)
    if signals and signal not in signals:
        allowed = ", ".join(sorted(signals))
        raise TopologyContractError(f"node '{node}' emitted signal '{signal}' outside topology contract; allowed: {allowed}")


def state_brief(state: JsonDict) -> JsonDict:

    current_step = state.get("current_step") or {}
    brief = {
        "tick": state.get("tick"),
        "current_node": state.get("current_node"),
        "step_index": state.get("step", 0),
        "current_step": {
            "description": current_step.get("description", ""),
            "done_when": current_step.get("done_when", ""),
        },
        "last_signal": state.get("last_signal"),
        "last_error": state.get("last_error"),
        "last_verification": state.get("last_verification", {}),
        "last_reflection": state.get("last_reflection", {}),
        "last_failure": state.get("last_failure", {}),
        "failure_streak": state.get("failure_streak", {}),
        "has_action_frame": bool(state.get("action_frame")),
        "root_goal": state.get("goal", ""),
        "effective_goal": state.get("effective_goal", state.get("goal", "")),
    }
    return brief


def observation_brief(state: JsonDict) -> JsonDict:
    artifact = state.get("observation_artifact") or {}
    tree = artifact.get("desktop_tree") if isinstance(artifact, dict) else {}
    return {
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "observed_at": state.get("observed_at"),
        "scan_config": artifact.get("scan_config", {}) if isinstance(artifact, dict) else {},
        "scan_stats": artifact.get("scan_stats", {}) if isinstance(artifact, dict) else {},
        "rendered_node_count": state.get("rendered_node_count") or (tree or {}).get("rendered_node_count"),
        "max_llm_nodes": state.get("max_llm_nodes") or (tree or {}).get("max_llm_nodes"),
        "llm_node_limit_hit": state.get("llm_node_limit_hit") or (tree or {}).get("llm_node_limit_hit"),
    }


def failure_signature(state: JsonDict) -> str:
    step = state.get("current_step") or {}
    parts = {
        "step": step.get("description", ""),
        "done_when": step.get("done_when", ""),
        "failure": state.get("last_failure") or {},
        "verification": state.get("last_verification") or {},
        "action_conclusion": (state.get("last_action") or {}).get("conclusion", ""),
    }
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def update_failure_streak(state: JsonDict) -> JsonDict:

    signature = failure_signature(state)
    previous = state.get("failure_streak") or {}
    count = int(previous.get("count", 0) or 0) + 1 if previous.get("signature") == signature else 1
    return {
        "failure_streak": {
            "signature": signature,
            "count": count,
            "updated_at": time.time(),
        }
    }
