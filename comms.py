"""Message bus — the nervous system of the colony.

Every entity (human, personas, reactor, TUI) is a peer on this bus.
Posts carry optional priority. Events mirror work phases.
"""
from __future__ import annotations
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import config

_MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)")

ALIASES: dict[str, str] = {
    "human": "human", "colony": "colony", "all": "colony",
    "tui": "tui", "reactor": "reactor",
    **{name: name for name in config.PERSONAS},
}

ROLES: dict[str, str] = {
    "human": "human", "colony": "colony", "reactor": "reactor", "tui": "tui",
    **{name: name for name in config.PERSONAS},
}

_SKIP_PHASES: frozenset[str] = frozenset({"schedule"})


def _ensure() -> None:
    config.BUS_DIR.mkdir(parents=True, exist_ok=True)
    if not config.BUS_CHAT_PATH.exists():
        config.BUS_CHAT_PATH.write_text("[]\n", encoding="utf-8")
    if not config.BUS_EVENTS_PATH.exists():
        config.BUS_EVENTS_PATH.write_text("", encoding="utf-8")
    if not config.BUS_INJECT_PATH.exists():
        config.BUS_INJECT_PATH.write_text("", encoding="utf-8")


def agent_id() -> str:
    p = os.environ.get("ENDGAME_PERSONALITY", "").strip()
    return p if p else f"pid-{os.getpid()}"


def canonical(name: str) -> str:
    return ALIASES.get(name.lstrip("@").lower(), name.lstrip("@").lower())


def parse_mentions(text: str) -> list[str]:
    seen: set[str] = set()
    return [c for m in _MENTION_RE.finditer(text) if (c := canonical(m.group(1))) not in seen and not seen.add(c)]


def ping_for(peer: str, mentions: list[str]) -> bool:
    return bool(peer and mentions and (peer in mentions or "colony" in mentions))


# --- Chat ---

def _read_chat() -> list[dict[str, Any]]:
    _ensure()
    try:
        raw = config.BUS_CHAT_PATH.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else []
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_chat(entries: list[dict[str, Any]]) -> None:
    _ensure()
    trimmed = entries[-config.BUS_CHAT_MAX:]
    config.BUS_CHAT_PATH.write_text(json.dumps(trimmed, ensure_ascii=False) + "\n", encoding="utf-8")


def post(from_id: str, role: str, text: str, *, kind: str = "message",
         priority: int | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
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
    if priority is not None:
        entry.setdefault("data", {})["priority"] = priority
    if data:
        entry["data"] = {**(entry.get("data") or {}), **data}
    entries = _read_chat()
    entries.append(entry)
    _write_chat(entries)
    return entry


def request(from_id: str, to: str, text: str, *, priority: int = config.PRI_NORMAL) -> dict[str, Any]:
    target = canonical(to)
    return post(from_id, "colony", f"@{target} {text}".strip(), kind="request",
                priority=priority, data={"to": target, "status": "open"})


def read_chat(limit: int = 30) -> list[dict[str, Any]]:
    return _read_chat()[-limit:]


def pending_for(peer: str, limit: int = 6) -> list[dict[str, Any]]:
    me = canonical(peer)
    hits = [e for e in _read_chat()
            if str(e.get("from", "")) != me
            and ping_for(me, e.get("mentions") or parse_mentions(str(e.get("text", ""))))
            and str(e.get("kind", "")) in ("ping", "request", "message")]
    return hits[-limit:]


# --- Events bus ---

def mirror_event(phase: str, data: Any = None, *, source: str | None = None) -> None:
    if phase in _SKIP_PHASES:
        return
    _ensure()
    src = source or agent_id()
    entry = {
        "id": int(time.time() * 1000),
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "from": src, "kind": "event",
        "text": _brief(phase, data),
        "data": {"phase": phase, "payload": data},
    }
    try:
        with config.BUS_EVENTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        return
    _trim_events()


def _trim_events() -> None:
    try:
        lines = [ln for ln in config.BUS_EVENTS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return
    if len(lines) > config.BUS_EVENTS_MAX:
        config.BUS_EVENTS_PATH.write_text("\n".join(lines[-config.BUS_EVENTS_MAX:]) + "\n", encoding="utf-8")


def read_events(limit: int = 20) -> list[dict[str, Any]]:
    _ensure()
    try:
        lines = [ln for ln in config.BUS_EVENTS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


# --- Inject ---

def drain_inject() -> int:
    if not config.BUS_INJECT_PATH.exists():
        return 0
    try:
        lines = [ln.strip() for ln in config.BUS_INJECT_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
        config.BUS_INJECT_PATH.write_text("", encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            fid = str(obj.get("from", "human"))
            post(fid, str(obj.get("role", "colony")), str(obj.get("text", "")),
                 kind=str(obj.get("kind", "message")),
                 priority=obj.get("priority"))
            count += 1
    return count


# --- Context rendering for LLM ---

def format_bus_context(limit: int | None = None, for_agent: str | None = None) -> str:
    n = limit or config.CONTEXT_BUS_MAX
    chat = read_chat(n)
    if not chat:
        return ""
    me = canonical((for_agent or agent_id()).strip())
    lines = ["MESSAGE BUS:"]
    inbox = pending_for(me, 5)
    if inbox:
        lines.append("YOUR INBOX (respond to these):")
        for e in inbox:
            pri = (e.get("data") or {}).get("priority", "")
            pri_tag = f" [PRI={pri}]" if pri else ""
            lines.append(f"  @{e.get('from')}: {str(e.get('text', ''))[:200]}{pri_tag}")
    shown_ids = {int(e.get("id", 0) or 0) for e in inbox}
    for entry in chat[-n:]:
        if int(entry.get("id", 0) or 0) in shown_ids:
            continue
        lines.append(f"  @{entry.get('from', '?')}: {str(entry.get('text', ''))[:200]}")
    return "\n".join(lines)


def _brief(phase: str, data: Any) -> str:
    if not isinstance(data, dict):
        return phase
    match phase:
        case "actor" | "action":
            return f"{phase} {'ok' if data.get('ok') else 'FAIL'} {str(data.get('obs', ''))[:120]}"
        case "plan":
            return f"plan {data.get('mode', '')} steps={data.get('steps', '')} {str(data.get('done_when', ''))[:80]}"
        case "verify":
            return f"verify {data.get('verdict', '')} {str(data.get('evidence', ''))[:80]}"
        case "fission":
            return f"fission n={data.get('fissions', '')}"
        case "interrupt":
            return f"INTERRUPT pri={data.get('pri')} from @{data.get('from', '?')}"
        case _:
            return f"{phase} {str(data)[:120]}"


# --- CLI ---

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "post":
        from_id = sys.argv[2]
        text = " ".join(sys.argv[3:])
        config.BUS_INJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.BUS_INJECT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"from": from_id, "text": text, "kind": "message"}, ensure_ascii=False) + "\n")
        drain_inject()
        print(f"bus @{from_id}: {text[:120]}")
    else:
        print(format_bus_context(15) or "(bus empty)")
