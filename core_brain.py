import json
from typing import Any

import core_bus as bus
import core_wiring as wiring


def _messages(system_prompt: str, user_text: str, stable_context: str = "") -> list[dict[str, str]]:
    system = system_prompt + ("\n\n" + stable_context if stable_context else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]


def get_record_contract(w: dict[str, Any], record_type: str) -> dict[str, Any]:
    contract = w["record_contracts"][record_type]
    if not isinstance(contract, dict):
        raise RuntimeError(f"wiring.record_contracts.{record_type} must be object")
    return contract


def _validate_record_contract(w: dict[str, Any], record: bus.Record, expected_record_type: str | None = None) -> None:
    if expected_record_type and record.record_type != expected_record_type:
        raise RuntimeError(f"brain record_type mismatch: expected {expected_record_type!r}, got {record.record_type!r}")
    contract = get_record_contract(w, record.record_type)
    required = list(contract["required"])
    enums = dict(contract["enums"])
    types = dict(contract.get("types", {}))
    non_empty = set(contract.get("non_empty", []))
    missing = [key for key in required if key not in record.data]
    if missing:
        raise RuntimeError(f"{record.record_type} record missing required data keys: {missing}")
    if not contract.get("additional_properties", True):
        allowed = set(required) | set(enums) | set(types)
        unexpected = sorted(set(record.data) - allowed)
        if unexpected:
            raise RuntimeError(f"{record.record_type} record has unexpected data keys: {unexpected}")
    json_types = {"string": str, "boolean": bool, "array": list, "object": dict, "number": (int, float), "integer": int}
    for key, type_name in types.items():
        if key in record.data and (not isinstance(record.data[key], json_types[type_name]) or type_name in {"number", "integer"} and isinstance(record.data[key], bool)):
            raise RuntimeError(f"{record.record_type}.data.{key} must be {type_name}")
    for key in non_empty:
        if key in record.data and not record.data[key]:
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-empty")
        if key in record.data and isinstance(record.data[key], str) and not record.data[key].strip():
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-blank")
    for key, values in enums.items():
        if key in record.data and record.data[key] not in set(values):
            raise RuntimeError(f"{record.record_type}.data.{key}={record.data[key]!r} outside {values!r}")


def _commit_record(content: str, w: dict[str, Any], expected_record_type: str | None = None) -> bus.Record:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str) or "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record must contain string record_type and object data: {record}")
    committed = bus.Record.from_json(record)
    _validate_record_contract(w, committed, expected_record_type)
    return committed



def _node_docstring(w: dict[str, Any], node: str) -> str:
    import ast
    base = node.split(":", 1)[0]
    node_dir = wiring.root_path(w["paths"]["nodes"])
    path = node_dir / f"{base}.py"
    if not path.is_file():
        raise RuntimeError(f"node '{node}' declareth no input contract")
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    if not doc:
        raise RuntimeError(f"node '{base}' declareth no input contract")
    return doc.strip()


def downstream_contract(w: dict[str, Any], emitting_node: str | None) -> str:
    if not emitting_node:
        return ""
    edges = w.get("topology", {}).get("edges", {}).get(emitting_node, {})
    seen: list[tuple[str, str]] = []
    for signal, target in edges.items():
        if signal == "error":
            continue
        if isinstance(target, str) and target != "halt":
            seen.append((signal, target))
    if not seen:
        return ""
    lines = ["DOWNSTREAM CONTRACT — thine output is wired (through the [topology]) unto these consumers; bring forth that which they await:"]
    for signal, succ in seen:
        lines.append(f"\n[on signal '{signal}' -> {succ}]\n{_node_docstring(w, succ)}")
    return "\n".join(lines)


def _organ_tuning(w: dict[str, Any], record_type: str | None) -> dict[str, Any]:
    organ = w["model"]["organs"].get(record_type) if record_type else None
    return dict(organ) if isinstance(organ, dict) else {}


def _normalize_observation(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict) or not obj.get("desktop_tree_text"):
        return None
    fields = (
        "desktop_tree_text", "focused_elements", "observed_at", "screen",
    )
    return {key: obj[key] for key in fields if key in obj}


def _observation_payload(w: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload:
        candidates = [payload.get("observation")]
        evidence = payload.get("evidence")
        if isinstance(evidence, dict):
            candidates.append(evidence.get("observation"))
        for candidate in candidates:
            normalized = _normalize_observation(candidate)
            if normalized is not None:
                return normalized
    raise RuntimeError("observation missing: observe node must run before any brain call")


def _with_observation(payload: dict[str, Any], w: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["observation"] = _observation_payload(w, enriched)
    return enriched


def _structured_outputs_enabled(cfg: dict[str, Any]) -> bool:
    structured = cfg.get("structured_outputs")
    return bool(structured.get("enabled", False)) if isinstance(structured, dict) else bool(structured)


def resolve_profile(w: dict[str, Any], profile: str | None) -> dict[str, Any]:
    if not profile:
        return {}
    _, cfg = wiring.get_transport_config(w)
    profiles = cfg.get("request_profiles", {})
    if profile not in profiles:
        raise RuntimeError(f"unknown request profile {profile!r}; wiring defines {sorted(profiles)}")
    return dict(profiles[profile])


def _record_response_format(w: dict[str, Any], record_type: str) -> dict[str, Any]:
    contract = get_record_contract(w, record_type)
    data_properties = {key: {} for key in contract["required"]}
    for key, type_name in contract.get("types", {}).items():
        data_properties.setdefault(key, {})["type"] = type_name
    for key in contract.get("non_empty", []):
        type_name = contract.get("types", {}).get(key)
        limit_name = {"string": "minLength", "array": "minItems", "object": "minProperties"}.get(type_name)
        if limit_name:
            data_properties.setdefault(key, {})[limit_name] = 1
    enums = dict(contract["enums"])
    for key, values in enums.items():
        data_properties.setdefault(key, {})["enum"] = list(values)
    return {
        "type": "json_schema",
        "name": f"{record_type}_record",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "record_type": {"enum": [record_type]},
                "data": {
                    "type": "object",
                    "additionalProperties": contract.get("additional_properties", True),
                    "properties": data_properties,
                    "required": list(contract["required"]),
                },
            },
            "required": ["record_type", "data"],
        },
    }


def call(messages: list[dict[str, str]], w: dict[str, Any], *, response_format: dict[str, Any] | None = None, body_override: dict[str, Any] | None = None, profile: str | None = None) -> dict[str, str]:
    transport, cfg = wiring.get_transport_config(w)
    override = bus.deep_merge(resolve_profile(w, profile), body_override or {})
    try:
        result = wiring.load("transport", transport, w).call(messages, cfg, body_override=override, response_format=response_format)
    except Exception as exc:
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{transport} brain contract violation: expected dict, got {type(result).__name__}")
    content, reasoning = result.get("content"), result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    out = {"content": content, "reasoning": reasoning or ""}
    return out


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def think(system_prompt: str, payload: dict[str, Any], w: dict[str, Any], *, expected_record_type: str | None = None, emitting_node: str | None = None, body_override: dict[str, Any] | None = None) -> dict[str, Any]:
    _, cfg = wiring.get_transport_config(w)
    organ_tuning = _organ_tuning(w, expected_record_type)
    payload = _with_observation(payload, w)
    goal = str(payload.pop("goal") or "") if "goal" in payload else ""
    environment_probe = payload.pop("environment_probe", None)
    focus = payload.get("focus")
    interps = focus.pop("goal_interpretations", None) if isinstance(focus, dict) else None
    ledger = focus.pop("proven_ledger", None) if isinstance(focus, dict) else None
    user_text = json.dumps(payload, ensure_ascii=False, default=str)
    templates = w["prompt_templates"]
    user_text = f"{user_text}\n\n{bus.render_proven_ledger(ledger, templates)}\n\n{bus.render_interpretation_table(goal, interps, templates)}"
    probe_text = bus.render_environment_probe(environment_probe, templates)
    if probe_text:
        user_text = f"{user_text}\n\n{probe_text}"
    response_format = _record_response_format(w, expected_record_type) if expected_record_type and _structured_outputs_enabled(cfg) else None
    override = bus.deep_merge(organ_tuning, body_override or {})
    stable_context = downstream_contract(w, emitting_node)
    result = call(_messages(system_prompt, user_text, stable_context), w, response_format=response_format, body_override=override)
    record = _commit_record(result["content"], w, expected_record_type)
    transport_reasoning = str(result.get("reasoning") or "").strip()
    return bus.Record(record.record_type, record.data, transport_reasoning or record.reasoning).to_json()
