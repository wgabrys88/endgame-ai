import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import core_bus as bus
import core_wiring as wiring

_SESSION_CACHE_KEY = f"endgame-{uuid.uuid4()}"
_ROOT = pathlib.Path(__file__).resolve().parent
_DUMP_DIR = _ROOT / "_transmissions"
_FUSE = False
_INJECT_CONTENT: str | None = None
_INJECT_FROM: str | None = None


def set_fuse(enabled: bool) -> None:
    global _FUSE
    _FUSE = bool(enabled)


def set_inject(path: str | pathlib.Path) -> None:
    global _INJECT_CONTENT, _INJECT_FROM
    p = pathlib.Path(path).expanduser()
    p = p.resolve() if p.is_absolute() else (_ROOT / p).resolve()
    if not p.is_file():
        raise RuntimeError(f"inject path must be one existing file: {p}")
    text = p.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise RuntimeError(f"inject file empty: {p}")
    content = _content_from_file(p, text)
    if not content.strip():
        raise RuntimeError(f"inject file has no usable content: {p}")
    _INJECT_CONTENT = content
    _INJECT_FROM = str(p)


def _content_from_file(path: pathlib.Path, text: str) -> str:
    name = path.name
    if name.endswith("transmission.json") or name == "transmission.json":
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise RuntimeError(f"transmission.json must be object: {path}")
        return str(obj.get("extracted_content") or "")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(obj, dict):
        return text
    if "extracted_content" in obj:
        return str(obj.get("extracted_content") or "")
    if isinstance(obj.get("record_type"), str) and isinstance(obj.get("data"), dict):
        return text
    if "content" in obj and isinstance(obj["content"], str):
        return obj["content"]
    return text


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
        if key in record.data and (
            not isinstance(record.data[key], json_types[type_name])
            or type_name in {"number", "integer"} and isinstance(record.data[key], bool)
        ):
            raise RuntimeError(f"{record.record_type}.data.{key} must be {type_name}")
    for key in non_empty:
        if key in record.data and not record.data[key]:
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-empty")
        if key in record.data and isinstance(record.data[key], str) and not record.data[key].strip():
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-blank")
    for key, values in enums.items():
        if key in record.data and record.data[key] not in set(values):
            raise RuntimeError(f"{record.record_type}.data.{key}={record.data[key]!r} outside {values!r}")


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _commit_record(content: str, w: dict[str, Any], expected_record_type: str | None = None) -> bus.Record:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str) or "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record must contain string record_type and object data: {record}")
    committed = bus.Record.from_json(record)
    _validate_record_contract(w, committed, expected_record_type)
    return committed


def downstream_contract(w: dict[str, Any], emitting_node: str | None) -> str:
    if not emitting_node:
        return ""
    import core_nodes as nodes

    edges = w.get("topology", {}).get("edges", {}).get(emitting_node, {})
    seen = [
        (signal, target)
        for signal, target in edges.items()
        if signal != "error" and isinstance(target, str) and target != "halt"
    ]
    if not seen:
        return ""
    lines = [
        "DOWNSTREAM CONTRACT — thine output is wired (through the [topology]) unto these consumers; "
        "bring forth that which they await:"
    ]
    for signal, succ in seen:
        lines.append(f"\n[on signal '{signal}' -> {succ}]\n{nodes.node_contract(succ)}")
    return "\n".join(lines)


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
    for key, values in dict(contract["enums"]).items():
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


def _transport_body(cfg: dict[str, Any], messages: list[dict[str, str]], body_override: dict | None, response_format: dict | None) -> dict[str, Any]:
    body = bus.deep_merge(cfg["request"], body_override or {})
    body.setdefault("prompt_cache_key", _SESSION_CACHE_KEY)
    body["input"] = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if m.get("role", "user") in {"system", "user", "assistant"}
    ]
    if isinstance(response_format, dict):
        if str(response_format.get("type", "json_schema")) == "json_object":
            body["text"] = {"format": {"type": "json_object"}}
        else:
            body["text"] = {"format": {
                "type": response_format.get("type", "json_schema"),
                "name": response_format.get("name", "record"),
                "schema": response_format.get("schema", {}),
                "strict": bool(response_format.get("strict", True)),
            }}
    return bus.drop_nulls(body)


def _write_full(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _new_transmission_prefix() -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    return f"{stamp}_{uid}"


def _dump_transmission(
    *,
    url: str,
    payload: dict[str, Any],
    messages: list[dict[str, str]],
    raw_response_text: str,
    response_obj: Any,
    content: str,
    reasoning: str,
    http_status: int | None,
    error: str | None,
    source: str = "live",
    inject_from: str | None = None,
) -> str:
    _DUMP_DIR.mkdir(parents=True, exist_ok=True)
    prefix = _new_transmission_prefix()

    def pref(name: str) -> pathlib.Path:
        return _DUMP_DIR / f"{prefix}_{name}"

    request_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    response_json = (
        json.dumps(response_obj, ensure_ascii=False, indent=2, default=str)
        if response_obj is not None
        else raw_response_text
    )
    meta = {
        "dumped_at": time.time(),
        "prefix": prefix,
        "source": source,
        "inject_from": inject_from,
        "url": url,
        "http_status": http_status,
        "error": error,
        "request_chars": len(request_json),
        "raw_response_chars": len(raw_response_text or ""),
        "content_chars": len(content or ""),
        "reasoning_chars": len(reasoning or ""),
        "message_roles": [m.get("role") for m in messages],
        "message_char_counts": {m.get("role", "?"): len(m.get("content") or "") for m in messages},
        "fuse": _FUSE,
    }
    bundle = {
        "meta": meta,
        "request_body": payload,
        "messages": messages,
        "raw_response_text": raw_response_text,
        "response_object": response_obj,
        "extracted_content": content,
        "extracted_reasoning": reasoning,
    }
    _write_full(pref("transmission.json"), json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
    _write_full(pref("request_body.json"), request_json)
    _write_full(pref("response_raw.json"), response_json if response_obj is not None else (raw_response_text or ""))
    _write_full(pref("response_raw.txt"), raw_response_text or "")
    _write_full(pref("content.txt"), content or "")
    _write_full(pref("reasoning.txt"), reasoning or "")
    for m in messages:
        role = str(m.get("role") or "unknown")
        _write_full(pref(f"message_{role}.txt"), str(m.get("content") or ""))
    _write_full(pref("meta.json"), json.dumps(meta, ensure_ascii=False, indent=2))
    return prefix


def _fuse_exit(prefix: str) -> None:
    sys.stderr.write(f"FUSE after live transmission prefix={prefix} (omit --breakpoint to continue)\n")
    sys.exit(42)


def _texts_from_parts(parts: Any) -> list[str]:
    out: list[str] = []
    if isinstance(parts, str) and parts.strip():
        return [parts]
    if not isinstance(parts, list):
        return out
    for part in parts:
        if isinstance(part, str) and part.strip():
            out.append(part)
        elif isinstance(part, dict) and part.get("text"):
            out.append(str(part["text"]))
    return out


def _extract_content_reasoning(obj: dict[str, Any]) -> tuple[str, str]:
    content = str(obj.get("output_text") or "")
    reasoning_parts: list[str] = []
    message_parts: list[str] = []
    if isinstance(obj.get("output"), list):
        for item in obj["output"]:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind == "reasoning":
                reasoning_parts.extend(_texts_from_parts(item.get("summary")))
                reasoning_parts.extend(_texts_from_parts(item.get("content")))
            else:
                message_parts.extend(_texts_from_parts(item.get("content")))
    if not content.strip():
        content = "\n".join(message_parts)
    return content, "\n".join(reasoning_parts).strip()


def _transport_call(messages: list[dict[str, str]], cfg: dict[str, Any], *, body_override=None, response_format=None) -> dict[str, str]:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = _transport_body(cfg, messages, body_override, response_format)
    url = str(cfg["url"])
    raw_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw_bytes,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    raw_response_text = ""
    response_obj: Any = None
    content = ""
    reasoning = ""
    http_status: int | None = None
    error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=float(cfg["timeout"])) as resp:
            http_status = int(getattr(resp, "status", 200) or 200)
            raw_response_text = resp.read().decode("utf-8")
        response_obj = json.loads(raw_response_text) if raw_response_text else {}
        if not isinstance(response_obj, dict):
            raise RuntimeError(f"xai transport expected JSON object, got {type(response_obj).__name__}")
        content, reasoning = _extract_content_reasoning(response_obj)
        prefix = _dump_transmission(
            url=url,
            payload=payload,
            messages=messages,
            raw_response_text=raw_response_text,
            response_obj=response_obj,
            content=content,
            reasoning=reasoning,
            http_status=http_status,
            error=None,
        )
        sys.stderr.write(
            f"TRANSMISSION DUMP (full, no truncation): {_DUMP_DIR} prefix={prefix}\n"
            f"  request_chars={len(raw_bytes)} response_chars={len(raw_response_text)} "
            f"content_chars={len(content)} reasoning_chars={len(reasoning)}\n"
        )
        if _FUSE:
            _fuse_exit(prefix)
        return {"content": content, "reasoning": reasoning}
    except SystemExit:
        raise
    except urllib.error.HTTPError as exc:
        http_status = int(exc.code)
        raw_response_text = exc.read().decode("utf-8")
        error = f"HTTP {exc.code}"
        try:
            response_obj = json.loads(raw_response_text) if raw_response_text else None
        except json.JSONDecodeError:
            response_obj = None
        prefix = _dump_transmission(
            url=url,
            payload=payload,
            messages=messages,
            raw_response_text=raw_response_text,
            response_obj=response_obj,
            content="",
            reasoning="",
            http_status=http_status,
            error=error,
        )
        sys.stderr.write(f"TRANSMISSION DUMP (HTTP error): {_DUMP_DIR} prefix={prefix}\n")
        if _FUSE:
            _fuse_exit(prefix)
        raise RuntimeError(f"xai transport HTTP {exc.code}: {raw_response_text}") from exc
    except urllib.error.URLError as exc:
        error = f"URL error: {getattr(exc, 'reason', exc)}"
        prefix = _dump_transmission(
            url=url,
            payload=payload,
            messages=messages,
            raw_response_text="",
            response_obj=None,
            content="",
            reasoning="",
            http_status=None,
            error=error,
        )
        sys.stderr.write(f"TRANSMISSION DUMP (URL error): {_DUMP_DIR} prefix={prefix}\n")
        if _FUSE:
            _fuse_exit(prefix)
        raise RuntimeError(f"xai transport URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc


def call(
    messages: list[dict[str, str]],
    w: dict[str, Any],
    *,
    response_format: dict[str, Any] | None = None,
    body_override: dict[str, Any] | None = None,
    profile: str | None = None,
) -> dict[str, str]:
    transport, cfg = wiring.get_transport_config(w)
    override = bus.deep_merge(resolve_profile(w, profile), body_override or {})
    try:
        result = _transport_call(messages, cfg, body_override=override, response_format=response_format)
    except Exception as exc:
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    content, reasoning = result.get("content"), result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    return {"content": content, "reasoning": reasoning or ""}


def think(
    system_prompt: str,
    payload: dict[str, Any],
    w: dict[str, Any],
    *,
    expected_record_type: str | None = None,
    emitting_node: str | None = None,
    body_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global _INJECT_CONTENT, _INJECT_FROM
    if _INJECT_CONTENT is not None:
        content = _INJECT_CONTENT
        src = _INJECT_FROM
        _INJECT_CONTENT = None
        _INJECT_FROM = None
        prefix = _dump_transmission(
            url="inject://local",
            payload={"injected": True, "emitting_node": emitting_node, "expected_record_type": expected_record_type},
            messages=[],
            raw_response_text="",
            response_obj={"source": "inject", "inject_from": src},
            content=content,
            reasoning="",
            http_status=None,
            error=None,
            source="inject",
            inject_from=src,
        )
        sys.stderr.write(f"INJECT reply from {src!r} → {_DUMP_DIR} prefix={prefix}\n")
        record = _commit_record(content, w, expected_record_type)
        return bus.Record(record.record_type, record.data, record.reasoning).to_json()

    _, cfg = wiring.get_transport_config(w)
    organ = w["model"]["organs"].get(expected_record_type) if expected_record_type else None
    organ_tuning = dict(organ) if isinstance(organ, dict) else {}
    goal = str(payload.pop("goal") or "") if "goal" in payload else ""
    environment = payload.pop("environment", None)
    brief = payload.get("state")
    interps = brief.pop("goal_interpretations", None) if isinstance(brief, dict) else None
    ledger = brief.pop("proven_ledger", None) if isinstance(brief, dict) else None
    templates = w["prompt_templates"]
    memory_text = (
        f"{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        f"{bus.render_proven_ledger(ledger, templates)}\n\n"
        f"{bus.render_interpretation_table(goal, interps, templates)}"
    )
    max_chars = int(w["exploration"]["max_environment_chars"])
    user_text = f"{memory_text}\n\n{bus.render_environment(environment, templates, max_chars=max_chars)}"
    structured = cfg.get("structured_outputs")
    structured_on = bool(structured.get("enabled", False)) if isinstance(structured, dict) else bool(structured)
    response_format = _record_response_format(w, expected_record_type) if expected_record_type and structured_on else None
    result = call(
        _messages(system_prompt, user_text, downstream_contract(w, emitting_node)),
        w,
        response_format=response_format,
        body_override=bus.deep_merge(organ_tuning, body_override or {}),
    )
    record = _commit_record(result["content"], w, expected_record_type)
    transport_reasoning = str(result.get("reasoning") or "").strip()
    return bus.Record(record.record_type, record.data, transport_reasoning or record.reasoning).to_json()
