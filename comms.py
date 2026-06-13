"""Unified colony message bus — chat in messages.json, events in events_bus.jsonl."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

_MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)\b")

# Conference handles → canonical peer id (@Human = human operator).
MENTION_ALIASES: dict[str, str] = {
    "human": "human",
    "grok": "grok",
    "git_expert": "git_expert",
    "implementor": "implementor",
    "doc_inspector": "doc_inspector",
    "comms_operator": "comms_operator",
    "quality_critic": "quality_critic",
    "gui_operator": "gui_operator",
    "gui": "gui_operator",
    "n1": "git_expert",
    "n2": "implementor",
    "n3": "doc_inspector",
    "n4": "comms_operator",
    "n5": "quality_critic",
    "n6": "gui_operator",
    "colony": "colony",
    "all": "colony",
    "tui": "tui",
    "reactor": "reactor",
}

BUS_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "messages.json"
EVENTS_BUS_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "events_bus.jsonl"
INJECT_PATH: Path = config.BASE_DIR / "runtime" / "comms" / "inject.jsonl"

ROLES: dict[str, str] = {
    "human": "human_agent",
    "grok": "external_ai",
    "git_expert": "colony",
    "implementor": "colony",
    "doc_inspector": "colony",
    "comms_operator": "colony",
    "quality_critic": "colony",
    "gui_operator": "gui_specialist",
    "tui": "console",
    "reactor": "console",
}

_SKIP_BUS_PHASES: frozenset[str] = frozenset({
    "math", "stagnation", "lorenz", "pid", "schedule", "token_usage",
    "plugin.load", "plugin.telemetry", "fission_sustain",
})
_SKIP_BUS_REASONS: frozenset[str] = frozenset({"plan_cooldown"})
_WORK_BUS_PHASES: frozenset[str] = frozenset({
    "start", "stop", "plan", "plan.rejected", "plan.blocked", "actor", "action",
    "verify", "fission_judge", "fission", "fission_blocked", "reflect", "mutator",
    "mutation", "personality.evolve", "goal_change", "planner.error", "actor.error",
    "verifier.error", "reflector.error", "fission_judge.error", "mutator.error",
    "llm_retry", "llm_fallback", "planner.pending", "plugin.web_sentinel",
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
    if slot:
        return f"n{slot}"
    return f"pid-{os.getpid()}"


def _role_for(agent: str) -> str:
    return ROLES.get(agent, "colony")


def parse_mentions(text: str) -> list[str]:
    """Extract @handles from message text; return canonical peer ids."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _MENTION_RE.finditer(text):
        canonical = MENTION_ALIASES.get(match.group(1).lower(), match.group(1).lower())
        if canonical not in seen:
            seen.add(canonical)
            found.append(canonical)
    return found


def ping_for(peer: str, mentions: list[str] | None) -> bool:
    if not peer or not mentions:
        return False
    if peer in mentions:
        return True
    return "colony" in mentions


def _canonical_peer(name: str) -> str:
    return MENTION_ALIASES.get(name.lstrip("@").lower(), name.lstrip("@").lower())


def _entry_mentions(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("mentions")
    if isinstance(raw, list):
        return [str(m) for m in raw]
    return parse_mentions(str(entry.get("text", "")))


def pending_for(peer: str, limit: int = 6) -> list[dict[str, Any]]:
    """Open bus pings/requests directed at peer (conference inbox)."""
    me = _canonical_peer(peer)
    if not me:
        return []
    hits: list[dict[str, Any]] = []
    for entry in _read_chat():
        if str(entry.get("from", "")) == me:
            continue
        mentions = _entry_mentions(entry)
        if not ping_for(me, mentions):
            continue
        if str(entry.get("kind", "")) not in ("ping", "request", "message"):
            continue
        hits.append(entry)
    return hits[-limit:] if limit > 0 else hits


def request(from_id: str, to: str, text: str, *, task: str = "work") -> dict[str, Any]:
    """Structured bus request — primary way to delegate work to a peer."""
    target = _canonical_peer(to)
    body = f"@{target} {text}".strip()
    return post(
        from_id,
        _role_for(from_id),
        body,
        kind="request",
        data={"to": target, "task": task, "status": "open"},
    )


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
    cap = int(getattr(config, "BUS_CHAT_MAX", 120))
    trimmed = entries[-cap:] if cap > 0 else entries
    BUS_PATH.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _trim_events_bus() -> None:
    cap = int(getattr(config, "BUS_EVENTS_MAX_LINES", 200))
    if cap <= 0 or not EVENTS_BUS_PATH.exists():
        return
    try:
        lines = [ln for ln in EVENTS_BUS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return
    if len(lines) <= cap:
        return
    try:
        EVENTS_BUS_PATH.write_text("\n".join(lines[-cap:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def _append_event_entry(entry: dict[str, Any]) -> None:
    _ensure()
    try:
        with EVENTS_BUS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        return
    _trim_events_bus()


def post(
    from_id: str,
    role: str,
    text: str,
    *,
    kind: str = "message",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Peer chat/beacon — always retained in messages.json."""
    body = text.strip()
    mentions = parse_mentions(body)
    entry: dict[str, Any] = {
        "id": int(time.time() * 1000),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "from": from_id,
        "role": role,
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
    """Mirror work events to events_bus.jsonl (rolling). Chat stays in messages.json."""
    if phase in _SKIP_BUS_PHASES:
        return
    if phase == "schedule" and isinstance(data, dict) and str(data.get("reason", "")) in _SKIP_BUS_REASONS:
        return
    if phase not in _WORK_BUS_PHASES and not phase.endswith(".error"):
        return
    src = source or agent_id()
    brief = _brief_event(phase, data)
    entry: dict[str, Any] = {
        "id": int(time.time() * 1000),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "from": src,
        "role": _role_for(src),
        "kind": "event",
        "text": brief,
        "data": {"phase": phase, "payload": data},
    }
    _append_event_entry(entry)


def _brief_event(phase: str, data: Any) -> str:
    if not isinstance(data, dict) or not data:
        return phase
    if phase in ("actor", "action"):
        return f"{phase} {'ok' if data.get('ok') else 'FAIL'} {data.get('verb', '')} {str(data.get('obs', ''))[:120]}"
    if phase == "plan":
        return f"plan {data.get('mode', '')} steps={data.get('steps', '')} {str(data.get('done_when', ''))[:80]}"
    if phase == "verify":
        return f"verify {data.get('verdict', '')} {str(data.get('evidence', ''))[:80]}"
    if phase == "fission_judge":
        return f"judge {data.get('verdict', '')} {str(data.get('diagnosis', ''))[:80]}"
    if phase == "fission":
        return f"fission power={data.get('power', '')} n={data.get('completions', '')}"
    if phase == "reflect":
        return f"reflect {str(data.get('diagnosis', data.get('rule', '')))[:100]}"
    if phase == "mutator":
        return f"mutator {data.get('action', '')} {data.get('filename', '')}"
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
        post(
            fid,
            str(obj.get("role", _role_for(fid))),
            str(obj.get("text", "")),
            kind=str(obj.get("kind", "message")),
            data=obj.get("data") if isinstance(obj.get("data"), dict) else None,
        )
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
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def read_bus(limit: int = 50) -> list[dict[str, Any]]:
    """Combined feed for TUI: chat messages + recent work events."""
    chat = _read_chat()
    events = read_events(max(10, limit // 2))
    merged = chat[-max(10, limit // 2):] + events
    merged.sort(key=lambda e: str(e.get("ts", "")))
    return merged[-limit:] if limit > 0 else merged


def read_chat(limit: int = 30) -> list[dict[str, Any]]:
    entries = _read_chat()
    return entries[-limit:] if limit > 0 else entries


def format_bus_context(limit: int | None = None, for_agent: str | None = None) -> str:
    n = limit if limit is not None else int(getattr(config, "CONTEXT_BUS_MAX", 10))
    chat = read_chat(n)
    events = read_events(max(4, n // 2))
    if not chat and not events:
        return ""
    me = _canonical_peer((for_agent or agent_id()).strip())
    lines = [
        "MESSAGE BUS (conference — build work from bus, not scattered goals):",
        "Peers: @Human @grok @GUI @git_expert @implementor @doc_inspector @comms_operator @quality_critic (@n1–@n6) @colony",
        "Delegate: bus_request(bus_id(), 'gui_operator', 'task') — only @GUI runs desktop_*",
    ]
    obs_max = int(getattr(config, "CONTEXT_OBS_MAX", 420))
    inbox = pending_for(me, 5)
    if inbox:
        lines.append("YOUR INBOX (reply or execute first):")
        for entry in inbox:
            fid = entry.get("from", "?")
            kind = entry.get("kind", "message")
            text = str(entry.get("text", "")).replace("\n", " ")
            if len(text) > obs_max:
                text = text[:obs_max] + "..."
            lines.append(f"  [{kind}] @{fid}: {text} ** PING FOR YOU **")
    shown_ids = {int(e.get("id", 0) or 0) for e in inbox}
    for entry in chat[-n:]:
        eid = int(entry.get("id", 0) or 0)
        if eid in shown_ids:
            continue
        fid = entry.get("from", "?")
        kind = entry.get("kind", "message")
        text = str(entry.get("text", "")).replace("\n", " ")
        if len(text) > obs_max:
            text = text[:obs_max] + "..."
        mentions = _entry_mentions(entry)
        ping = " ** PING FOR YOU **" if ping_for(me, mentions) and fid != me else ""
        lines.append(f"  [{kind}] @{fid}: {text}{ping}")
    for entry in events[-max(4, n // 3):]:
        fid = entry.get("from", "?")
        text = str(entry.get("text", "")).replace("\n", " ")
        if len(text) > obs_max:
            text = text[:obs_max] + "..."
        lines.append(f"  [event] @{fid}: {text}")
    return "\n".join(lines)


def bus_post_cli(argv: list[str]) -> int:
    if len(argv) < 4 or argv[1] != "post":
        print("usage: python comms.py post <human|grok> <message>")
        return 1
    from_id = argv[2]
    role = _role_for(from_id)
    text = " ".join(argv[3:])
    if from_id in ("grok", "human"):
        INJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INJECT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"from": from_id, "role": role, "text": text, "kind": "message"}, ensure_ascii=False) + "\n")
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