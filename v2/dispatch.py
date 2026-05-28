from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any

from config import PROMPTS_DIR, SCHEMAS_DIR, trace
from llm import call_llm

__all__ = ["call_role", "RoleSpec"]


@dataclass(frozen=True, slots=True)
class RoleSpec:
    name: str
    max_input_tokens: int
    max_output_tokens: int


_schema_cache: dict[str, list[str]] = {}


def _get_required_fields(role: str) -> list[str]:
    if role in _schema_cache:
        return _schema_cache[role]
    path = SCHEMAS_DIR / f"{role}.json"
    if not path.exists():
        _schema_cache[role] = []
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = data.get("json_schema", {}).get("schema", {}).get("required", [])
    _schema_cache[role] = fields
    return fields


def call_role(spec: RoleSpec, context: str) -> dict[str, Any]:
    system = _load_prompt(spec.name)
    trace("dispatch.call", f"role={spec.name} context_len={len(context)} system_len={len(system)}")
    raw = call_llm(system, context, spec.name, max_tokens=spec.max_output_tokens)
    trace("dispatch.raw", f"role={spec.name} raw_len={len(raw)} raw_start={raw[:200]}")
    required = _get_required_fields(spec.name)
    result = _extract_json(raw, required)
    if not isinstance(result, dict):
        raise ValueError(f"expected dict, got {type(result).__name__}: {str(result)[:100]}")
    return result


def _extract_json(raw: str, required_fields: list[str]) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            result = json.loads(stripped)
            if isinstance(result, dict) and _matches_schema(result, required_fields):
                trace("dispatch.parse", "clean JSON, schema match")
                return result
        except json.JSONDecodeError:
            pass
    candidates = []
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append((start, raw[start:i + 1]))
                start = -1
    schema_match = None
    actionable = None
    fallback = None
    for pos, candidate in reversed(candidates):
        try:
            result = json.loads(candidate)
            if not isinstance(result, dict):
                continue
            if schema_match is None and _matches_schema(result, required_fields):
                schema_match = (pos, result)
                if result.get("mode") != "done":
                    break
            if actionable is None and result.get("mode") != "done":
                actionable = (pos, result)
            if fallback is None:
                fallback = (pos, result)
        except json.JSONDecodeError:
            continue
    chosen = schema_match or actionable or fallback
    if chosen:
        pos, result = chosen
        preamble = raw[:pos].strip()
        method = "schema_match" if chosen == schema_match else ("actionable" if chosen == actionable else "fallback")
        trace("dispatch.salvage", f"{len(candidates)} blocks, chose {method}. Preamble ({len(preamble)} chars): {preamble}")
        return result
    trace("dispatch.no_json", f"no valid JSON in response ({len(raw)} chars): {raw}")
    raise ValueError(f"no JSON in response: {raw}")


def _matches_schema(obj: dict, required_fields: list[str]) -> bool:
    if not required_fields:
        return True
    return all(field in obj for field in required_fields)


def _load_prompt(role: str) -> str:
    path = PROMPTS_DIR / f"{role}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()