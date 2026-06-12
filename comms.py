"""Unified colony message bus — runtime/comms/messages.json."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

BUS_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "messages.json"
INJECT_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "inject.jsonl"

ROLES: dict[str, str] = {
    "human": "human_agent",
    "grok": "external_ai",
    "git_expert": "colony",
    "implementor": "colony",
    "doc_inspector": "colony",
    "comms_operator": "colony",
    "quality_critic": "colony",
    "tui": "console",
    "reactor": "console",
}

_SKIP_BUS_PHASES: frozenset[str] = frozenset({"schedule"})
_SKIP_BUS_REASONS: frozenset[str] = frozenset({"plan_cooldown"})


def _ensure() -> None:
    BUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BUS_PATH.exists():
        BUS_PATH.write_text("[]\n", encoding="utf-8")


def agent_id() -> str:
    personality = os.environ.get("ENDGAME_PERSONALITY", "").strip()
    if personality:
        return personality
    slot = os.environ.get("ENDGAME_SLOT", "").strip()
    if slot:
        return f"n{slot}"
    return f"pid-{os.getpid()}"


def _role_for(agent: str) -> str:
    return ROLES.get(agent, "colony")


def _read_bus() -> list[dict[str, Any]]:
    _ensure()
    try:
        raw = BUS_PATH.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else []
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_bus(entries: list[dict[str, Any]]) -> None:
    _ensure()
    cap = int(getattr(config, "BUS_MAX_LINES", 400))
    trimmed = entries[-cap:] if cap > 0 else entries
    BUS_PATH.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def post(
    from_id: str,
    role: str,
    text: str,
    *,
    kind: str = "message",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a bus message. Human, grok, and colony slots are peers on one bus."""
    entry: dict[str, Any] = {
        "id": int(time.time() * 1000),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "from": from_id,
        "role": role,
        "kind": kind,
        "text": text.strip(),
    }
    if data:
        entry["data"] = data
    entries = _read_bus()
    entries.append(entry)
    _write_bus(entries)
    return entry


def mirror_event(phase: str, data: Any = None, *, source: str | None = None) -> None:
    """Mirror colony events onto the bus so human/grok see the full stream."""
    if phase in _SKIP_BUS_PHASES:
        return
    if phase == "schedule" and isinstance(data, dict) and str(data.get("reason", "")) in _SKIP_BUS_REASONS:
        return
    src = source or agent_id()
    brief = phase
    if isinstance(data, dict) and data:
        if phase in ("actor", "action"):
            brief = f"{phase} {'ok' if data.get('ok') else 'FAIL'} {data.get('verb', '')} {str(data.get('obs', ''))[:120]}"
        elif phase == "plan":
            brief = f"plan {data.get('mode', '')} steps={data.get('steps', '')} {str(data.get('done_when', ''))[:80]}"
        elif phase == "verify":
            brief = f"verify {data.get('verdict', '')} {str(data.get('evidence', ''))[:80]}"
        elif phase == "fission_judge":
            brief = f"judge {data.get('verdict', '')} {str(data.get('diagnosis', ''))[:80]}"
        elif phase == "fission":
            brief = f"fission power={data.get('power', '')} n={data.get('completions', '')}"
        elif phase == "reflect":
            brief = f"reflect {str(data.get('diagnosis', data.get('rule', '')))[:100]}"
        elif phase == "mutator":
            brief = f"mutator {data.get('action', '')} {data.get('filename', '')}"
        else:
            brief = f"{phase} {str(data)[:120]}"
    post(src, _role_for(src), brief, kind="event", data={"phase": phase, "payload": data})


def drain_inject() -> int:
    """Drain inject.jsonl (external grok/human CLI) into the bus."""
    if not INJECT_PATH.exists():
        return 0
    try:
        lines = [ln.strip() for ln in INJECT_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
        INJECT_PATH.write_text("", encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        fid = str(obj.get("from", "grok"))
        post(
            fid,
            str(obj.get("role", _role_for(fid))),
            str(obj.get("text", "")),
            kind=str(obj.get("kind", "message")),
            data=obj.get("data") if isinstance(obj.get("data"), dict) else None,
        )
        count += 1
    return count


def read_bus(limit: int = 50) -> list[dict[str, Any]]:
    entries = _read_bus()
    return entries[-limit:] if limit > 0 else entries


def format_bus_context(limit: int | None = None) -> str:
    n = limit if limit is not None else int(getattr(config, "CONTEXT_BUS_MAX", 10))
    entries = read_bus(n)
    if not entries:
        return ""
    lines = ["MESSAGE BUS (peers: human, grok, colony slots):"]
    for entry in entries:
        fid = entry.get("from", "?")
        kind = entry.get("kind", "message")
        text = str(entry.get("text", "")).replace("\n", " ")
        if len(text) > int(getattr(config, "CONTEXT_OBS_MAX", 420)):
            text = text[: int(getattr(config, "CONTEXT_OBS_MAX", 420))] + "..."
        lines.append(f"  [{kind}] @{fid}: {text}")
    return "\n".join(lines)


def bus_post_cli(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python comms.py post <human|grok|slot> <message>")
        return 1
    from_id = argv[1]
    role = _role_for(from_id)
    text = " ".join(argv[2:])
    if from_id in ("grok", "human"):
        INJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        INJECT_PATH.open("a", encoding="utf-8").write(
            json.dumps({"from": from_id, "role": role, "text": text, "kind": "message"}, ensure_ascii=False) + "\n"
        )
        drain_inject()
    else:
        post(from_id, role, text)
    print(f"bus @{from_id}: {text[:120]}")
    return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "post":
        raise SystemExit(bus_post_cli(sys.argv))
    print(format_bus_context(15) or "(bus empty)")