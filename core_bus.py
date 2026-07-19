from dataclasses import dataclass
import json
import re
import time
from typing import Any


JsonDict = dict[str, Any]


def deep_merge(base: JsonDict, override: JsonDict) -> JsonDict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def drop_nulls(obj: Any) -> Any:
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


class BusContractError(RuntimeError): pass


class TopologyContractError(BusContractError): pass


class NodeRecordContractError(BusContractError): pass


@dataclass(frozen=True)
class Record:
    record_type: str
    data: JsonDict
    reasoning: str = ""

    def to_json(self) -> JsonDict:
        return {"record_type": self.record_type, "data": self.data, "reasoning": self.reasoning}

    @classmethod
    def from_json(cls, obj: JsonDict) -> "Record":
        return cls(record_type=obj.get("record_type", ""), data=obj.get("data", {}), reasoning=obj.get("reasoning", ""))


def emit(signal: str, patch: JsonDict | None = None) -> tuple[str, JsonDict]:
    if not isinstance(signal, str) or not signal.strip():
        raise ValueError("bus signal must be a non-empty string")
    if patch is not None and not isinstance(patch, dict):
        raise TypeError("bus patch must be a dict")
    return signal.strip(), dict(patch or {})


_INTERP_ORDER = ["execute", "verify", "recover"]


def render_interpretation_table(goal: str, interps: JsonDict | None, templates: JsonDict) -> str:
    interps = interps or {}
    lines = [templates["living_word_header"]]
    for faculty in _INTERP_ORDER:
        sentence = str(interps.get(faculty) or "").strip()
        lines.append(f"[{faculty}] {sentence}" if sentence else templates["living_word_empty_row"].format(faculty=faculty))
    lines.append(templates["living_word_goal_row"].format(goal=goal))
    return "\n".join(lines)


def render_proven_ledger(ledger: list | None, templates: JsonDict) -> str:
    entries = [str(e).strip() for e in (ledger or []) if str(e).strip()]
    if not entries:
        return templates["proven_ledger_empty"]
    body = "\n".join(f"  - {e}" for e in entries)
    return templates["proven_ledger_header"] + "\n" + body


def with_interpretation(interps: JsonDict | None, faculty: str, sentence: str) -> JsonDict:
    merged = dict(interps or {})
    merged[faculty] = str(sentence or "").strip()
    return merged


def render_environment_probe(probe: JsonDict | None, templates: JsonDict) -> str:
    probe = probe or {}
    if not probe:
        return ""
    lines = [templates["standing_host_header"]]
    for key, value in probe.items():
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"[{key}] {value}")
    return "\n".join(lines)


def coerce_node_output(node: str, result: Any) -> tuple[str, JsonDict]:
    if not (isinstance(result, tuple) and len(result) == 2):
        raise NodeRecordContractError(f"node '{node}' contract violation: expected (signal, patch)")
    signal, patch = result
    if not isinstance(signal, str) or not signal:
        raise NodeRecordContractError(f"node '{node}' contract violation: signal must be a non-empty string")
    if not isinstance(patch, dict):
        raise NodeRecordContractError(f"node '{node}' contract violation: patch must be dict")
    return signal, patch


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


def state_brief(state: JsonDict) -> JsonDict:
    current_deed = state.get("current_deed") or {}
    return {
        "goal_interpretations": dict(state.get("goal_interpretations") or {}),
        "proven_ledger": list(state.get("proven_ledger") or []),
        "latest_counsel": state.get("latest_counsel") or "",
        "current_deed": {"description": current_deed.get("description", "")},
        "failure_streak": state.get("failure_streak", {}),
        "has_action_frame": bool(state.get("action_frame")),
    }


def framed_elements(state: JsonDict) -> JsonDict:
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
        if str(node_id) in framed_ids:
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
        "framed_elements": framed_elements(state),
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
    previous = state.get("failure_streak") or {}
    count = int(previous.get("count", 0) or 0) + 1
    return {"failure_streak": {"count": count, "updated_at": time.time()}}
