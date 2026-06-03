from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, cast

from config import PROMPTS_DIR, SCHEMAS_DIR
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
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    fields: list[str] = data.get("json_schema", {}).get("schema", {}).get("required", [])
    _schema_cache[role] = fields
    return fields


def call_role(spec: RoleSpec, context: str) -> dict[str, Any]:
    system = _load_prompt(spec.name)
    raw = call_llm(system, context, spec.name, max_tokens=spec.max_output_tokens)
    required = _get_required_fields(spec.name)
    return _extract_json(raw, required)


def _extract_json(raw: str, required_fields: list[str]) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            top_result: dict[str, Any] = json.loads(stripped)
            if _matches_schema(top_result, required_fields):
                return top_result
        except json.JSONDecodeError:
            pass
    candidates: list[tuple[int, str]] = []
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
    schema_match: tuple[int, dict[str, Any]] | None = None
    actionable: tuple[int, dict[str, Any]] | None = None
    fallback: tuple[int, dict[str, Any]] | None = None
    for pos, candidate in reversed(candidates):
        try:
            parsed: object = json.loads(candidate)
            if not isinstance(parsed, dict):
                continue
            result: dict[str, Any] = cast(dict[str, Any], parsed)
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
        _, result = chosen
        return result
    raise ValueError(f"no JSON in response: {raw}")


def _matches_schema(obj: dict[str, Any], required_fields: list[str]) -> bool:
    if not required_fields:
        return True
    return all(field in obj for field in required_fields)


def _load_prompt(role: str) -> str:
    path = PROMPTS_DIR / f"{role}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
