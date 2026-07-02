"""Brain chokepoint for endgame-ai.

Brain transports are hot-swappable modules selected only by wiring.json model.transport.
Every transport lives under brain_transports/ and is loaded directly.
No selected transport has a fallback path.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import threading
import time
from typing import Any

import stop_check

ROOT = pathlib.Path(__file__).parent.resolve()
_RAW_LOG_PATH: pathlib.Path | None = None
_RAW_SEQ = 0
_RAW_LOCK = threading.Lock()
_CALLS_MADE = 0

_OPEN_OBJECT_SCHEMA = {"type": "object", "additionalProperties": True}

_RECORD_DATA_SCHEMAS: dict[str, dict[str, Any]] = {
    "plan": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["step_ready", "reflect"]},
            "intent": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "description": {"type": "string"},
                        "done_when": {"type": "string"},
                    },
                },
            },
        },
        "required": ["next_signal", "intent"],
    },
    "schedule": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["step_ready", "plan_complete"]},
            "step": {
                "anyOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ]
            },
        },
        "required": ["next_signal", "step"],
    },
    "execution": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "conclusion": {"enum": ["EXECUTE", "CANNOT"]},
            "code": {"type": "string"},
        },
        "required": ["conclusion", "code"],
    },
    "verification": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["step_confirmed", "step_denied"]},
            "success": {"type": "boolean"},
            "reasoning": {"type": "string"},
        },
        "required": ["next_signal", "success", "reasoning"],
    },
    "reflection": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["retry", "replan", "escalate", "give_up"]},
            "lesson": {"type": "string"},
            "diagnosis": {"type": "string"},
        },
        "required": ["next_signal", "lesson", "diagnosis"],
    },
    "git_evolution_patch": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "summary": {"type": "string"},
            "rationale": {"type": "string"},
            "file_writes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
            "file_deletes": {"type": "array", "items": {"type": "string"}},
            "wiring_patches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "op": {"enum": ["set", "delete"]},
                        "path": {"type": "string"},
                    },
                    "required": ["op", "path"],
                },
            },
            "commands": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "expected_validation": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ]
            },
        },
        "required": ["summary", "rationale", "file_writes", "file_deletes", "wiring_patches", "commands", "expected_validation"],
    },
    "satisfied": {
        "type": "object",
        "additionalProperties": True,
        "properties": {"next_signal": {"const": "halt"}},
        "required": ["next_signal"],
    },
}




def _messages(system_prompt: str, user_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]


def _commit_record(content: str) -> dict[str, Any]:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str):
        raise RuntimeError(f"brain record missing string record_type: {record}")
    if "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record missing object data: {record}")
    return record


def _effective_reasoning_config(wiring: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    model_global = wiring.get("model", {}).get("global", {})
    reasoning_cfg = dict(cfg.get("reasoning") or {})
    reasoning_cfg["enabled"] = bool(reasoning_cfg.get("enabled", model_global.get("reasoning_enabled", False)))
    reasoning_cfg.setdefault("pattern", "two_pass" if reasoning_cfg["enabled"] else "single_pass")
    reasoning_cfg.setdefault("extractor", "think_tags")
    reasoning_cfg.setdefault("injection_template", "REASONING_FEEDBACK:\n{reasoning}\n\nReturn only the requested JSON record.")
    return reasoning_cfg


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = os.path.expandvars(os.path.expanduser(str(value or default)))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {path}: {exc}") from exc


def atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def append_ndjson(path: pathlib.Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def raw_log_path(cfg: dict[str, Any] | None = None) -> pathlib.Path:
    global _RAW_LOG_PATH
    cfg = cfg or {}
    if _RAW_LOG_PATH is None:
        explicit = cfg.get("raw_log_path")
        if explicit:
            _RAW_LOG_PATH = root_path(str(explicit))
        else:
            _RAW_LOG_PATH = ROOT / f"{time.strftime('%Y%m%dT%H%M%S')}.txt"
        _RAW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RAW_LOG_PATH.touch(exist_ok=True)
    return _RAW_LOG_PATH


def _next_raw_seq() -> int:
    global _RAW_SEQ
    with _RAW_LOCK:
        _RAW_SEQ += 1
        return _RAW_SEQ


def log_raw_entry(cfg: dict[str, Any] | None, entry: dict[str, Any]) -> None:
    cfg = cfg or {}
    if cfg.get("raw_log", True) is False or cfg.get("log_raw", True) is False:
        return
    row = dict(entry)
    row.setdefault("ts", time.time())
    row.setdefault("iso", time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()))
    append_ndjson(raw_log_path(cfg), row)


def reset_call_budget() -> None:
    global _CALLS_MADE
    _CALLS_MADE = 0


def _load_transport_module(name: str, wiring: dict[str, Any]):
    paths = wiring.get("paths", {})
    brain_dir = root_path(paths.get("brains"), "brain_transports")
    module_path = brain_dir / f"{name}.py"
    if not module_path.exists():
        raise RuntimeError(
            f"selected brain transport '{name}' has no module at {module_path}; "
            "brain selection is fail-hard and no fallback was attempted"
        )
    spec = importlib.util.spec_from_file_location(f"endgame_brain_transport_{name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load selected brain transport module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "call"):
        raise RuntimeError(f"brain transport '{name}' does not export call(messages, cfg)")
    return mod


def _get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract transport name and merged config from wiring.json.
    
    New schema: model.transport_config.{transport} for per-transport config
    Legacy schema: model.{transport} for backward compatibility
    """
    model = wiring.get("model")
    if not isinstance(model, dict):
        raise RuntimeError("wiring.json missing object model")
    
    transport = str(model.get("transport") or "").strip()
    if not transport:
        raise RuntimeError("wiring model.transport is empty; no fallback transport is allowed")
    
    # New normalized schema: transport_config.{transport}
    transport_config = model.get("transport_config", {})
    if isinstance(transport_config, dict) and transport in transport_config:
        cfg = dict(transport_config[transport])
    else:
        # Legacy fallback: model.{transport}
        cfg = dict(model.get(transport) or {})
    
    # Merge global config (timeout, max_brain_calls, raw_log, etc.)
    global_keys = {"timeout", "max_brain_calls", "raw_log", "raw_log_path", "log_raw"}
    global_cfg = model.get("global", {})
    for k in global_keys:
        if isinstance(global_cfg, dict) and k in global_cfg and k not in cfg:
            cfg[k] = global_cfg[k]
        if k in model and k not in cfg:
            cfg[k] = model[k]
    
    cfg["transport"] = transport
    return transport, cfg


def _structured_outputs_enabled(cfg: dict[str, Any]) -> bool:
    structured = cfg.get("structured_outputs")
    if isinstance(structured, dict):
        return bool(structured.get("enabled", False))
    return bool(structured)


def _record_response_format(record_type: str) -> dict[str, Any]:
    data_schema = _RECORD_DATA_SCHEMAS.get(record_type, _OPEN_OBJECT_SCHEMA)
    return {
        "type": "json_schema",
        "name": f"{record_type}_record",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "record_type": {"const": record_type},
                "data": data_schema,
                "reasoning": {"type": "string"},
            },
            "required": ["record_type", "data"],
        },
    }


def call(
    messages: list[dict[str, str]],
    wiring: dict[str, Any],
    *,
    rod_feedback: bool = False,
    response_format: dict[str, Any] | None = None,
    request_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Call the selected transport exactly once or raise.
    
    The function logs request, response, and error rows. It never switches transport.
    """
    stop_check.check_stop("brain call")
    global _CALLS_MADE
    transport, cfg = _get_transport_config(wiring)
    if response_format is not None:
        cfg = dict(cfg)
        cfg["response_format"] = response_format
    if request_config:
        cfg = dict(cfg)
        cfg.update(request_config)
    model_cfg = wiring.get("model", {})
    max_calls = model_cfg.get("max_brain_calls")
    if max_calls is None and isinstance(model_cfg.get("global"), dict):
        max_calls = model_cfg["global"].get("max_brain_calls")
    if max_calls is not None and _CALLS_MADE >= int(max_calls):
        raise RuntimeError(f"brain call budget exceeded: {_CALLS_MADE}/{max_calls}")
    _CALLS_MADE += 1
    seq = _next_raw_seq()
    started = time.time()
    log_raw_entry(cfg, {
        "seq": seq,
        "phase": "request",
        "transport": transport,
        "rod_feedback": rod_feedback,
        "messages": messages,
    })
    mod = _load_transport_module(transport, wiring)
    try:
        result = mod.call(messages, cfg)
    except Exception as exc:
        log_raw_entry(cfg, {
            "seq": seq,
            "phase": "error",
            "transport": transport,
            "elapsed_s": round(time.time() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        })
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{transport} brain contract violation: expected dict, got {type(result).__name__}")
    content = result.get("content")
    reasoning = result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    out = {"content": content, "reasoning": reasoning or ""}
    log_raw_entry(cfg, {
        "seq": seq,
        "phase": "response",
        "transport": transport,
        "elapsed_s": round(time.time() - started, 3),
        "content": content,
        "reasoning": reasoning or "",
        "raw": {k: v for k, v in result.items() if k not in {"content", "reasoning"}},
    })
    return out


def reasoning_from(content: str, reasoning: str = "") -> str:
    if reasoning and reasoning.strip():
        return reasoning.strip()
    m = re.search(r"<think>(.*?)</think>", content or "", flags=re.S | re.I)
    if m:
        return m.group(1).strip()
    return (content or "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    s = text.strip()
    if "</think>" in s.lower():
        s = re.split(r"</think>", s, maxsplit=1, flags=re.I)[-1].strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.S | re.I)
    if fenced:
        s = fenced.group(1).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    starts: list[int] = []
    candidates: list[str] = []
    in_str = False
    esc = False
    depth = 0
    start = -1
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
                starts.append(i)
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(s[start:i + 1])
    for candidate in reversed(candidates):
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def think(
    system_prompt: str,
    payload: dict[str, Any],
    wiring: dict[str, Any],
    *,
    expected_record_type: str | None = None,
    request_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pluggable ROD brain pattern returning the committed JSON record."""
    _, cfg = _get_transport_config(wiring)
    reasoning_cfg = _effective_reasoning_config(wiring, cfg)
    user_text = json.dumps(payload, ensure_ascii=False, default=str)
    pattern = str(reasoning_cfg.get("pattern") or "single_pass")
    response_format = (
        _record_response_format(expected_record_type)
        if expected_record_type and _structured_outputs_enabled(cfg)
        else None
    )

    if not reasoning_cfg["enabled"] or pattern == "single_pass":
        result = call(
            _messages(system_prompt, user_text),
            wiring,
            rod_feedback=False,
            response_format=response_format,
            request_config=request_config,
        )
        record = _commit_record(result["content"])
        record.setdefault("reasoning", reasoning_from(result["content"], result.get("reasoning", "")))
        return record

    if pattern == "native":
        result = call(
            _messages(system_prompt, user_text),
            wiring,
            rod_feedback=False,
            response_format=response_format,
            request_config=request_config,
        )
        record = _commit_record(result["content"])
        record.setdefault("reasoning", reasoning_from(result["content"], result.get("reasoning", "")))
        return record

    if pattern != "two_pass":
        raise RuntimeError(f"unknown reasoning pattern: {pattern}")

    first = call(_messages(system_prompt, user_text), wiring, rod_feedback=False)
    reasoning = reasoning_from(first["content"], first.get("reasoning", ""))
    template = str(reasoning_cfg.get("injection_template") or "REASONING_FEEDBACK:\n{reasoning}")
    second = call(
        _messages(system_prompt, user_text + "\n\n" + template.format(reasoning=reasoning)),
        wiring,
        rod_feedback=True,
        response_format=response_format,
        request_config=request_config,
    )
    record = _commit_record(second["content"])
    record.setdefault("reasoning", reasoning)
    return record


def read_raw_log_tail(path: pathlib.Path | None = None, *, max_lines: int = 200, max_bytes: int = 600_000) -> list[dict[str, Any]]:
    p = path or raw_log_path({"raw_log": True})
    if not p.exists():
        return []
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            f.readline()
        raw = f.read()
    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines()[-max_lines:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows
