from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.resolve()
SCHEMAS = ROOT / "schemas"

REQUIRED = {
    "planner": {"mode", "sequence", "done_when"},
    "actor": {"actions", "conclusion"},
    "verifier": {"verdict", "evidence"},
    "reflector": {"diagnosis", "lesson", "prompt_mutation"},
    "mutator": {"diagnosis", "action", "filename", "content"},
}


def _schema(role: str) -> dict[str, Any]:
    path = SCHEMAS / f"{role}.json"
    if not path.exists():
        raise SystemExit(f"missing schema: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("type") != "json_schema":
        raise SystemExit(f"{role}: type must be json_schema")
    js = raw.get("json_schema")
    if not isinstance(js, dict) or js.get("strict") is not True:
        raise SystemExit(f"{role}: json_schema.strict must be true")
    schema: dict[str, Any] = js.get("schema") or {}
    props = schema.get("properties") or {}
    missing = REQUIRED[role] - set(props)
    if missing:
        raise SystemExit(f"{role}: missing properties {sorted(missing)}")
    required = set(schema.get("required") or [])
    if not REQUIRED[role] <= required:
        raise SystemExit(f"{role}: required keys incomplete")
    if schema.get("additionalProperties") is not False:
        raise SystemExit(f"{role}: additionalProperties must be false")
    return schema


def main() -> None:
    schemas = {role: _schema(role) for role in REQUIRED}
    planner = schemas["planner"]["properties"]
    if planner["sequence"].get("maxItems", 99) > 4:
        raise SystemExit("planner: maxItems must stay small-model friendly")
    if planner["sequence"]["items"].get("maxLength", 999) > 160:
        raise SystemExit("planner: sequence items too long")
    actor = schemas["actor"]["properties"]
    if actor["actions"].get("maxItems", 99) > 5:
        raise SystemExit("actor: too many actions")
    if actor["actions"]["items"]["properties"]["value"].get("maxLength") != 8000:
        raise SystemExit("actor: value must remain large for real write tasks")
    verifier = schemas["verifier"]["properties"]
    if verifier["evidence"].get("maxLength", 999) > 320:
        raise SystemExit("verifier: evidence too verbose")
    reflector = schemas["reflector"]["properties"]
    if reflector["diagnosis"].get("maxLength", 999) > 320:
        raise SystemExit("reflector: diagnosis too verbose")
    print("schemas ok")


if __name__ == "__main__":
    main()
