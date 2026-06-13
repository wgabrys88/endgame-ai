"""Colony message bus — chat in messages.json, events in events_bus.jsonl."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

_MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)")

MENTION_ALIASES: dict[str, str] = {
    "human": "human", "grok": "grok",
    "git_expert": "git_expert", "implementor": "implementor",
    "doc_inspector": "doc_inspector", "comms_operator": "comms_operator",
    "quality_critic": "quality_critic", "gui_operator": "gui_operator",
    "gui": "gui_operator",
    "n1": "git_expert", "n2": "implementor", "n3": "doc_inspector",
    "n4": "comms_operator", "n5": "quality_critic", "n6": "gui_operator",
    "colony": "colony", "all": "colony", "tui": "tui", "reactor": "reactor",
}

BUS_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "messages.json"
EVENTS_BUS_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "events_bus.jsonl"
INJECT_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "inject.jsonl"

ROLES: dict[str, str] = {
    "human": "human_agent", "grok": "external_ai",
    "git_expert": "colony", "implementor": "colony", "doc_inspector": "colony",
    "comms_operator": "colony", "quality_critic": "colony",
    "gui_operator": "gui_specialist", "tui": "console", "reactor": "console",
}

_SKIP_BUS_PHASES: frozenset[str] = frozenset({
    "math", "stagnation", "lorenz", "pid", "schedule", "token_usage",
    "plugin.load", "plugin.telemetry", "fission_sustain",
})
_WORK_BUS_PHASES: frozenset[str] = frozenset({
    "start", "stop", "plan", "plan.rejected", "actor", "verify", "fission_judge",
    "fission", "fission_blocked", "reflect", "mutator", "mutation", "personality.evolve",
    "goal_change", "planner.error", "actor.error", "mutator.error", "llm_retry", "llm_fallback",
})


def _ensure() -> None:
    BUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BUS_PATH.exists():
        BUS_PATH.write_text("[]\n", encoding="utf-8")
    if not EVENTS_BUS_PATH.exists():
        EVENTS_BUS_PATH.write_text("", encoding="utf-8")


def agent_id() -> str:
    personality = os.environ.get("ENDGAME_PERSONALITY", "").strip()
    if personality:
        return personality
    slot = os.environ.get("ENDGAME_SLOT", "").strip()
    return f"n{slot}" if slot else f"pid-{os.getpid()}"


def parse_mentions(text: str) -> list[str]:
    seen: set[str] = set()
    found: list[str] = []
    for match in _MENTION_RE.finditer(text):
        canonical = MENTION_ALIASES.get(match.group(1).lower(), match.group(1).lower())
        if canonical not in seen:
            seen.add(canonical)
            found.append(canonical)
    return found


def ping_for(peer: str, mentions: list[str] | None) -> bool:
    if not peer or not mentions:
        return False
    return peer in mentions or "colony" in mentions


def pending_for(peer: str, limit: int = 6) -> list[dict[str, Any]]:
    me = MENTION_ALIASES.get(peer.lstrip("@").lower(), peer.lstrip("@").lower())
    if not me:
        return []
    hits: list[dict[str, Any]] = []
    for entry in _read_chat():
        if str(entry.get("from", "")) == me:
            continue
        mentions = entry.get("mentions") if isinstance(entry.get("mentions"), list) else parse_mentions(str(entry.get("text", "")))
        if not ping_for(me, mentions):
            continue
        hits.append(entry)
    return hits[-limit:]


def request(from_id: str, to: str, text: str, *, task: str = "work") -> dict[str, Any]:
    target = MENTION_ALIASES.get(to.lstrip("@").lower(), to.lstrip("@").lower())
    return post(from_id, ROLES.get(from_id, "colony"), f"@{target} {text}".strip(), kind="request", data={"to": target, "task": task})


def _read_chat() -> list[dict[str, Any]]:
    _ensure()
    try:
        raw = BUS_PATH.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else []
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_chat(entries: list[dict[str, Any]]) -> None:
    _ensure()
    cap = config.BUS_CHAT_MAX
    trimmed = entries[-cap:] if cap > 0 else entries
    BUS_PATH.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def post(from_id: str, role: str, text: str, *, kind: str = "message", data: dict[str, Any] | None = None) -> dict[str, Any]:
    body = text.strip()
    mentions = parse_mentions(body)
    entry: dict[str, Any] = {
        "id": int(time.time() * 1000),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "from": from_id, "role": role,
        "kind": "ping" if mentions and kind == "message" else kind,
        "text": body,
    }
    if mentions:
        entry["mentions"] = mentions
    if data:
        entry["data"] = data
    entries = _read_chat()
    entries.append(entry)
    _write_chat(entries)
    return entry


def mirror_event(phase: str, data: Any = None, *, source: str | None = None) -> None:
    if phase in _SKIP_BUS_PHASES:
        return
    if phase not in _WORK_BUS_PHASES and not phase.endswith(".error"):
        return
    src = source or agent_id()
    brief = _brief_event(phase, data)
    entry = {
        "id": int(time.time() * 1000),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "from": src, "role": ROLES.get(src, "colony"), "kind": "event",
        "text": brief, "data": {"phase": phase, "payload": data},
    }
    _ensure()
    try:
        with EVENTS_BUS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        pass
    # Trim events bus
    cap = config.BUS_EVENTS_MAX_LINES
    if cap > 0 and EVENTS_BUS_PATH.exists():
        try:
            lines = EVENTS_BUS_PATH.read_text(encoding="utf-8").splitlines()
            if len(lines) > cap:
                EVENTS_BUS_PATH.write_text("\n".join(lines[-cap:]) + "\n", encoding="utf-8")
        except OSError:
            pass


def _brief_event(phase: str, data: Any) -> str:
    if not isinstance(data, dict):
        return phase
    if phase in ("actor", "action"):
        return f"{phase} {'ok' if data.get('ok') else 'FAIL'} {data.get('obs', '')[:120]}"
    if phase == "plan":
        return f"plan {data.get('mode', '')} steps={data.get('steps', '')} {str(data.get('done_when', ''))[:80]}"
    if phase == "fission":
        return f"fission power={data.get('power', '')} n={data.get('completions', '')}"
    return f"{phase} {str(data)[:120]}"


def drain_inject() -> int:
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
        post(fid, str(obj.get("role", ROLES.get(fid, "colony"))), str(obj.get("text", "")), kind=str(obj.get("kind", "message")))
        count += 1
    return count


def read_events(limit: int = 20) -> list[dict[str, Any]]:
    _ensure()
    if not EVENTS_BUS_PATH.exists():
        return []
    try:
        lines = [ln for ln in EVENTS_BUS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def read_chat(limit: int = 30) -> list[dict[str, Any]]:
    return _read_chat()[-limit:]


def format_bus_context(limit: int | None = None, for_agent: str | None = None) -> str:
    n = limit or config.CONTEXT_BUS_MAX
    chat = read_chat(n)
    if not chat:
        return ""
    me = MENTION_ALIASES.get((for_agent or agent_id()).lstrip("@").lower(), "")
    lines = [
        "MESSAGE BUS:",
        "Peers: @Human @grok @GUI @git_expert @implementor @doc_inspector @comms_operator @quality_critic @colony",
    ]
    inbox = pending_for(me, 5) if me else []
    if inbox:
        lines.append("YOUR INBOX:")
        for entry in inbox:
            lines.append(f"  [{entry.get('kind')}] @{entry.get('from')}: {entry.get('text', '')} ** PING FOR YOU **")
    shown_ids = {int(e.get("id", 0) or 0) for e in inbox}
    for entry in chat[-n:]:
        if int(entry.get("id", 0) or 0) in shown_ids:
            continue
        fid = entry.get("from", "?")
        mentions = entry.get("mentions") if isinstance(entry.get("mentions"), list) else []
        ping = " ** PING FOR YOU **" if me and ping_for(me, mentions) and fid != me else ""
        lines.append(f"  [{entry.get('kind')}] @{fid}: {entry.get('text', '')}{ping}")
    return "\n".join(lines)


def read_bus(limit: int = 50) -> list[dict[str, Any]]:
    chat = _read_chat()
    events = read_events(max(10, limit // 2))
    merged = chat[-max(10, limit // 2):] + events
    merged.sort(key=lambda e: str(e.get("ts", "")))
    return merged[-limit:]


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "post":
        from_id = sys.argv[2]
        text = " ".join(sys.argv[3:])
        role = ROLES.get(from_id, "colony")
        if from_id in ("grok", "human"):
            INJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with INJECT_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"from": from_id, "role": role, "text": text}, ensure_ascii=False) + "\n")
            drain_inject()
        else:
            post(from_id, role, text)
        print(f"bus @{from_id}: {text[:120]}")
    else:
        print(format_bus_context(15) or "(bus empty)")
