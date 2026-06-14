"""Message bus — the colony blackboard (protocol v1).

Two stores, one envelope:
  messages.json    — intent (coordinate, route, assign)
  events_bus.jsonl — observation (telemetry, pipeline phases)

Every entry shares the v1 envelope:

  v, id, ts, from, slot, kind, pri, mentions?, to?, text, payload

Kinds (closed set):
  message   — chat (human/colony)
  ping      — @mention wake-up
  request   — assigned task  payload: {to, status, goal?}
  route     — MoE gate decision payload: {to, slot?, pri, reason, scores?}
  telemetry — pressure snapshot payload: {stagnation, power, velocity, fissions, phase, cycles}
  event     — pipeline phase   payload: {phase, ...}
  beacon    — system online    payload: {status}
  evolve    — AgentBreeder     payload: {target, action, fitness?, diff?}
  verdict   — verify/fission   payload: {verdict, evidence}
  status    — reactor/tui      payload: {state, detail?}

MoE: power = confidence, stagnation = 1-power. route.scores maps persona→telemetry.
"""
from __future__ import annotations
from collections import Counter
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import config

BUS_VERSION = 1

KIND_MESSAGE = "message"
KIND_PING = "ping"
KIND_REQUEST = "request"
KIND_ROUTE = "route"
KIND_TELEMETRY = "telemetry"
KIND_EVENT = "event"
KIND_BEACON = "beacon"
KIND_EVOLVE = "evolve"
KIND_VERDICT = "verdict"
KIND_STATUS = "status"

INTENT_KINDS = frozenset({KIND_MESSAGE, KIND_PING, KIND_REQUEST, KIND_ROUTE, KIND_BEACON, KIND_EVOLVE, KIND_VERDICT, KIND_STATUS})
OBSERVE_KINDS = frozenset({KIND_TELEMETRY, KIND_EVENT})
INBOX_KINDS = frozenset({KIND_PING, KIND_REQUEST, KIND_MESSAGE, KIND_ROUTE})
_COLONY_PEERS = frozenset(config.WORKER_PERSONAS) | frozenset({"comms_operator"})

_MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]*)")
_BEACON_STAG_RE = re.compile(r"stag=([0-9.]+)")
_BEACON_PWR_RE = re.compile(r"power=([0-9.]+)")

ALIASES: dict[str, str] = {
    "human": "human", "colony": "colony", "all": "colony",
    "tui": "tui", "reactor": "reactor",
    **{name: name for name in config.PERSONAS},
}

ROLES: dict[str, str] = {
    "human": "human", "colony": "colony", "reactor": "reactor", "tui": "tui",
    **{name: name for name in config.PERSONAS},
}

_SKIP_PHASES: frozenset[str] = frozenset({
    "schedule", "plugin.web_sentinel",
})


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


def slot_id() -> int:
    try:
        return int(os.environ.get("ENDGAME_SLOT", "0") or 0)
    except ValueError:
        return 0


def canonical(name: str) -> str:
    return ALIASES.get(name.lstrip("@").lower(), name.lstrip("@").lower())


def parse_mentions(text: str) -> list[str]:
    seen: set[str] = set()
    return [c for m in _MENTION_RE.finditer(text) if (c := canonical(m.group(1))) not in seen and not seen.add(c)]


def ping_for(peer: str, mentions: list[str]) -> bool:
    return bool(peer and mentions and (peer in mentions or "colony" in mentions))


def _entry_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload")
    if isinstance(payload, dict):
        return payload
    data = entry.get("data")
    return data if isinstance(data, dict) else {}


def inbox_match(peer: str, entry: dict[str, Any]) -> bool:
    """Whether a blackboard entry belongs in peer's actionable inbox."""
    me = canonical(peer)
    if not me or str(entry.get("from", "")) == me:
        return False
    if str(entry.get("kind", "")) not in INBOX_KINDS:
        return False
    payload = _entry_payload(entry)
    if payload.get("human_ack"):
        return False
    ments = entry.get("mentions") or parse_mentions(str(entry.get("text", "")))
    if ping_for(me, ments) or canonical(str(entry.get("to", ""))) == me:
        return True
    if (
        str(entry.get("from", "")) == "human"
        and int(entry.get("pri", 0) or 0) >= config.PRI_HUMAN
        and me in _COLONY_PEERS
    ):
        return True
    return False


def _now_id() -> tuple[str, int]:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds"), int(time.time() * 1000)


def _normalize(entry: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy entries to v1 shape in-memory."""
    e = dict(entry)
    if "v" not in e:
        e["v"] = 0
    data = e.get("data") if isinstance(e.get("data"), dict) else {}
    if "pri" not in e and "priority" in data:
        e["pri"] = int(data["priority"])
    elif "pri" not in e:
        e["pri"] = config.PRI_MAINTENANCE
    if "slot" not in e:
        e["slot"] = 0
    if "payload" not in e:
        if e.get("kind") == KIND_EVENT and isinstance(data, dict):
            e["payload"] = {"phase": data.get("phase", ""), **(data.get("payload") or {})}
        elif e.get("kind") == "beacon" and isinstance(e.get("text"), str):
            m_s = _BEACON_STAG_RE.search(e["text"])
            m_p = _BEACON_PWR_RE.search(e["text"])
            e["payload"] = {
                "stagnation": float(m_s.group(1)) if m_s else 0.0,
                "power": float(m_p.group(1)) if m_p else 0.0,
            }
            e["kind"] = KIND_TELEMETRY
        else:
            e["payload"] = dict(data)
    if "to" not in e and isinstance(data, dict) and data.get("to"):
        e["to"] = data["to"]
    return e


def envelope(
    from_id: str,
    kind: str,
    *,
    text: str = "",
    pri: int | None = None,
    mentions: list[str] | None = None,
    to: str | None = None,
    payload: dict[str, Any] | None = None,
    slot: int | None = None,
) -> dict[str, Any]:
    """Build a v1 blackboard entry."""
    ts, eid = _now_id()
    body = text.strip()
    ments = mentions if mentions is not None else parse_mentions(body)
    entry: dict[str, Any] = {
        "v": BUS_VERSION,
        "id": eid,
        "ts": ts,
        "from": from_id,
        "slot": slot if slot is not None else slot_id(),
        "kind": kind,
        "pri": pri if pri is not None else config.PRI_MAINTENANCE,
        "text": body,
        "payload": payload or {},
    }
    if ments:
        entry["mentions"] = ments
    if to:
        entry["to"] = canonical(to)
    return entry


def _append_event(entry: dict[str, Any]) -> None:
    _ensure()
    try:
        with config.BUS_EVENTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        return
    _trim_events()


def _mirror_breeder_observation(entry: dict[str, Any]) -> None:
    kind = str(entry.get("kind", ""))
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    if kind == KIND_EVOLVE:
        _append_event(entry)
    elif kind == KIND_STATUS and str(payload.get("action", "")).startswith("breed."):
        _append_event(entry)


# --- Intent layer (messages.json) ---

def _read_chat() -> list[dict[str, Any]]:
    _ensure()
    try:
        raw = config.BUS_CHAT_PATH.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else []
        return [_normalize(e) for e in data] if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_chat(entries: list[dict[str, Any]]) -> None:
    _ensure()
    trimmed = entries[-config.BUS_CHAT_MAX:]
    config.BUS_CHAT_PATH.write_text(json.dumps(trimmed, ensure_ascii=False) + "\n", encoding="utf-8")


def post(from_id: str, role: str, text: str, *, kind: str = KIND_MESSAGE,
         priority: int | None = None, data: dict[str, Any] | None = None,
         human_ack: bool = False, blocked_by: str = "",
         suggested_rephrase: str = "") -> dict[str, Any]:
    body = text.strip()
    mentions = parse_mentions(body)
    resolved_kind = KIND_PING if mentions and kind == KIND_MESSAGE else kind
    payload = dict(data or {})
    if priority is not None and "priority" not in payload:
        payload["priority"] = priority
    if human_ack:
        payload["human_ack"] = True
    if blocked_by:
        payload["blocked_by"] = blocked_by[:200]
    if suggested_rephrase:
        payload["suggested_rephrase"] = suggested_rephrase[:240]
    entry = envelope(
        from_id, resolved_kind, text=body,
        pri=priority, mentions=mentions,
        to=str(payload.get("to", "")) or None,
        payload=payload,
    )
    # Legacy compat: keep role + data fields readers may expect
    entry["role"] = role
    entry["data"] = payload
    entries = _read_chat()
    entries.append(entry)
    _write_chat(entries)
    _mirror_breeder_observation(entry)
    return entry


def request(from_id: str, to: str, text: str, *, priority: int = config.PRI_NORMAL,
            goal: str = "") -> dict[str, Any]:
    target = canonical(to)
    payload: dict[str, Any] = {"to": target, "status": "open"}
    if goal:
        payload["goal"] = goal[:200]
    entry = envelope(
        from_id, KIND_REQUEST,
        text=f"@{target} {text}".strip(),
        pri=priority, to=target, payload=payload,
    )
    entry["role"] = "colony"
    entry["data"] = payload
    entries = _read_chat()
    entries.append(entry)
    _write_chat(entries)
    return entry


def route(from_id: str, to: str, reason: str, *, priority: int = config.PRI_NORMAL,
          scores: dict[str, Any] | None = None, goal: str = "",
          escalate: bool = False, slot: int = 0) -> dict[str, Any]:
    """MoE gating decision — comms_operator assigns work to an expert."""
    target = canonical(to)
    payload: dict[str, Any] = {"to": target, "reason": reason[:200], "status": "open"}
    if scores:
        payload["scores"] = scores
    if goal:
        payload["goal"] = goal[:200]
    if escalate:
        payload["escalate"] = True
    if slot:
        payload["slot"] = int(slot)
    text = f"@{target} {reason}".strip()
    entry = envelope(
        from_id, KIND_ROUTE, text=text, pri=priority, to=target, payload=payload,
    )
    entry["role"] = "colony"
    entry["data"] = payload
    entries = _read_chat()
    entries.append(entry)
    _write_chat(entries)
    return entry


def post_evolve(
    from_id: str,
    target: str,
    action: str,
    *,
    fitness: float | None = None,
    completed: str = "",
    reason: str = "",
    diff: str = "",
    priority: int = config.PRI_MAINTENANCE,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish an AgentBreeder selection candidate on the blackboard."""
    target_id = canonical(target)
    payload: dict[str, Any] = {"target": target_id, "action": action[:32]}
    if fitness is not None:
        payload["fitness"] = round(max(0.0, min(1.0, float(fitness))), 4)
    if completed:
        payload["completed"] = completed[:200]
    if reason:
        payload["reason"] = reason[:200]
    if diff:
        payload["diff"] = diff[:2000]
    if data:
        payload.update(data)
    text = f"evolve @{target_id} {payload['action']}"
    if "fitness" in payload:
        text += f" fitness={payload['fitness']:.3f}"
    if reason:
        text += f" {reason[:80]}"
    entry = envelope(
        from_id,
        KIND_EVOLVE,
        text=text,
        pri=priority,
        mentions=parse_mentions(text),
        to=target_id,
        payload=payload,
    )
    entry["role"] = "colony"
    entry["data"] = payload
    entries = _read_chat()
    entries.append(entry)
    _write_chat(entries)
    _mirror_breeder_observation(entry)
    return entry


def read_chat(limit: int = 30) -> list[dict[str, Any]]:
    return _read_chat()[-limit:]


def evolve_candidates(after_id: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent AgentBreeder candidates without removing blackboard history."""
    out = []
    for entry in _read_chat():
        if str(entry.get("kind", "")) != KIND_EVOLVE:
            continue
        eid = int(entry.get("id", 0) or 0)
        if eid > after_id:
            out.append(entry)
    return out[-limit:]


def pending_for(peer: str, limit: int = 6) -> list[dict[str, Any]]:
    hits = [e for e in _read_chat() if inbox_match(peer, e)]
    return hits[-limit:]


def apply_interrupt(board: dict[str, Any]) -> dict[str, Any] | None:
    """Apply highest-priority bus message to board. Returns interrupt metadata if switched."""
    try:
        drain_inject()
    except Exception:
        pass
    me = agent_id()
    current_pri = int(board.get("priority", config.PRI_MAINTENANCE) or config.PRI_MAINTENANCE)
    inbox = sorted(
        pending_for(me, 6),
        key=lambda m: (-msg_priority(m), -int(m.get("id", 0) or 0)),
    )
    for msg in inbox:
        msg_id = int(msg.get("id", 0) or 0)
        if msg_id <= int(board.get("_last_msg_id", 0) or 0):
            continue
        payload = _entry_payload(msg)
        if payload.get("human_ack"):
            board["_last_msg_id"] = msg_id
            continue
        msg_pri = msg_priority(msg)
        is_human = str(msg.get("from", "")) == "human"
        if is_human or msg_pri >= config.PRI_HUMAN or msg_pri > current_pri:
            board["_last_msg_id"] = msg_id
            goal_text = str(payload.get("goal", "")) if payload else ""
            board["goal"] = goal_text or str(msg.get("text", ""))
            board["priority"] = config.PRI_HUMAN if is_human else msg_pri
            board["plan"] = []
            board["history"] = []
            board["_human_denials"] = 0
            board.setdefault("_pressure", {}).update(failures=0)
            return {"from": msg.get("from"), "pri": msg_pri, "text": str(msg.get("text", ""))[:120]}
        board["_last_msg_id"] = msg_id
    return None


def post_progress(from_id: str, *, goal: str = "", step: str = "", phase: str = "") -> dict[str, Any]:
    """Colony-wide progress snapshot (pri=0, not an interrupt)."""
    payload = {"progress": True, "goal": goal[:200], "step": step[:200], "phase": phase[:32]}
    text = f"progress {phase or step or 'update'}"
    if goal:
        text += f" goal={goal[:80]}"
    return post(from_id, "colony", text, priority=config.PRI_MAINTENANCE, data=payload)


# --- Observation layer (events_bus.jsonl) ---

def post_telemetry(
    from_id: str,
    *,
    stagnation: float,
    power: float,
    velocity: float = 0.0,
    fissions: int = 0,
    phase: str = "",
    cycles: int = 0,
) -> dict[str, Any]:
    """Pressure field snapshot — MoE confidence signal for the blackboard."""
    payload = {
        "stagnation": round(float(stagnation), 4),
        "power": round(float(power), 4),
        "velocity": round(float(velocity), 4),
        "fissions": int(fissions),
        "phase": phase[:32],
        "cycles": int(cycles),
    }
    text = (f"tel slot={slot_id()} stag={payload['stagnation']:.2f} "
            f"pwr={payload['power']:.2f} vel={payload['velocity']:.2f} "
            f"F={payload['fissions']} {payload['phase']}")
    entry = envelope(from_id, KIND_TELEMETRY, text=text, payload=payload)
    _append_event(entry)
    return entry


def mirror_event(phase: str, data: Any = None, *, source: str | None = None) -> None:
    if phase in _SKIP_PHASES:
        return
    src = source or agent_id()
    payload: dict[str, Any] = {"phase": phase}
    if isinstance(data, dict):
        payload.update(data)
    elif data is not None:
        payload["raw"] = data
    entry = envelope(src, KIND_EVENT, text=_brief(phase, data), payload=payload)
    _append_event(entry)


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
            out.append(_normalize(json.loads(line)))
        except json.JSONDecodeError:
            pass
    return out


def human_task_active() -> bool:
    """True while the latest human pri=3 message has no colony completion reply."""
    chat = read_chat(40)
    human_msgs = [
        e for e in chat
        if str(e.get("from", "")) == "human"
        and int(e.get("pri", 0) or 0) >= config.PRI_HUMAN
    ]
    if not human_msgs:
        return False
    latest = human_msgs[-1]
    hid = int(latest.get("id", 0) or 0)
    for e in reversed(chat):
        eid = int(e.get("id", 0) or 0)
        if eid <= hid:
            break
        if _entry_payload(e).get("human_ack"):
            return False
        text = str(e.get("text", "")).lower()
        if any(tag in text for tag in ("cannot complete", "not supported", "confirmed", "completed", "declined")):
            return False
    ments = latest.get("mentions") or parse_mentions(str(latest.get("text", "")))
    if not ments and not pending_for("comms_operator", 1):
        return False
    return True


def colony_state() -> dict[str, dict[str, Any]]:
    """Latest telemetry per persona — MoE gating input for comms_operator."""
    state: dict[str, dict[str, Any]] = {}
    try:
        lines = config.BUS_EVENTS_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return state
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = _normalize(json.loads(line))
        except json.JSONDecodeError:
            continue
        if e.get("kind") not in (KIND_TELEMETRY, "beacon"):
            continue
        who = str(e.get("from", ""))
        if not who:
            continue
        p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        state[who] = {
            "slot": int(e.get("slot", 0) or 0),
            "ts": e.get("ts", ""),
            "stagnation": float(p.get("stagnation", 0)),
            "power": float(p.get("power", 0)),
            "velocity": float(p.get("velocity", 0)),
            "fissions": int(p.get("fissions", 0)),
            "phase": str(p.get("phase", "")),
            "cycles": int(p.get("cycles", 0)),
        }
    return state


def post_control(action: str, **fields: Any) -> dict[str, Any]:
    """Reactor control channel — reassign/evict commands from comms_operator."""
    _ensure()
    pri = int(fields.pop("priority", config.PRI_NORMAL))
    payload = {"action": action, **fields}
    entry = envelope("comms_operator", KIND_STATUS, text=f"control:{action}",
                     pri=pri, payload=payload)
    try:
        with config.BUS_CONTROL_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        pass
    return entry


def drain_control(limit: int = 20) -> list[dict[str, Any]]:
    """Reactor reads and clears pending control commands."""
    if not config.BUS_CONTROL_PATH.exists():
        return []
    try:
        lines = [ln.strip() for ln in config.BUS_CONTROL_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
        config.BUS_CONTROL_PATH.write_text("", encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            e = _normalize(json.loads(line))
            p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
            if p.get("action"):
                out.append(p)
        except json.JSONDecodeError:
            pass
    return out


def msg_priority(msg: dict[str, Any]) -> int:
    """Resolve priority from v1 entry (pri field) or legacy data.priority."""
    if "pri" in msg:
        return int(msg["pri"])
    data = msg.get("data") or msg.get("payload") or {}
    if isinstance(data, dict) and "priority" in data:
        return int(data["priority"])
    if str(msg.get("from", "")) == "human":
        return config.PRI_HUMAN
    kind = str(msg.get("kind", ""))
    if kind in (KIND_REQUEST, KIND_ROUTE):
        return config.PRI_NORMAL
    if kind == KIND_PING:
        return config.PRI_NORMAL
    return config.PRI_MAINTENANCE


def softmax_route(scores: dict[str, float]) -> list[tuple[str, float]]:
    """MoE gate weights from power scores (Bause 2026)."""
    if not scores:
        return []
    import math
    exp = {k: math.exp(v * 3.0) for k, v in scores.items()}
    total = sum(exp.values()) or 1.0
    ranked = sorted(((k, exp[k] / total) for k in exp), key=lambda x: x[1], reverse=True)
    return ranked


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
            data = obj.get("data") if isinstance(obj.get("data"), dict) else None
            post(fid, str(obj.get("role", "colony")), str(obj.get("text", "")),
                 kind=str(obj.get("kind", KIND_MESSAGE)),
                 priority=obj.get("priority"),
                 data=data)
            count += 1
    return count


# --- Context rendering for LLM ---

def format_bus_context(limit: int | None = None, for_agent: str | None = None) -> str:
    n = limit or config.CONTEXT_BUS_MAX
    chat = read_chat(n)
    me = canonical((for_agent or agent_id()).strip())
    lines = ["BLACKBOARD v1:"]

    if me == "comms_operator":
        colony = colony_state()
        if colony:
            lines.append("COLONY STATE (MoE inputs — power=confidence):")
            for who, st in sorted(colony.items(), key=lambda x: x[1].get("power", 0)):
                lines.append(
                    f"  @{who} slot={st.get('slot', '?')} "
                    f"pwr={st.get('power', 0):.2f} stag={st.get('stagnation', 0):.2f} "
                    f"vel={st.get('velocity', 0):.2f} F={st.get('fissions', 0)} "
                    f"{st.get('phase', '')}"
                )
            powers = {who: st.get("power", 0) for who, st in colony.items()}
            ranked = softmax_route(powers)
            if ranked:
                lines.append("GATE WEIGHTS: " + " ".join(f"{w}={p:.2f}" for w, p in ranked[:5]))

    inbox = pending_for(me, 5)
    shown_ids: set[int] = set()
    if inbox:
        lines.append("YOUR INBOX (respond to these):")
        for e in sorted(inbox, key=lambda x: (-int(x.get("pri", 0) or 0), -int(x.get("id", 0) or 0))):
            shown_ids.add(int(e.get("id", 0) or 0))
            pri = e.get("pri", e.get("data", {}).get("priority", ""))
            pri_tag = f" [PRI={pri}]" if pri != "" else ""
            lines.append(f"  @{e.get('from')}: {str(e.get('text', ''))[:200]}{pri_tag}")
    if not chat and len(lines) == 1 and not inbox:
        return ""
    human_lines: list[str] = []
    other_lines: list[str] = []
    for entry in chat[-n * 2:]:
        eid = int(entry.get("id", 0) or 0)
        if eid in shown_ids:
            continue
        kind = str(entry.get("kind", ""))[:6]
        line = f"  @{entry.get('from', '?')} [{kind}] {str(entry.get('text', ''))[:200]}"
        if str(entry.get("from", "")) == "human" or int(entry.get("pri", 0) or 0) >= config.PRI_HUMAN:
            human_lines.append(line)
        elif kind != "route" or len(other_lines) < 3:
            other_lines.append(line)
    for line in human_lines + other_lines[-3:]:
        lines.append(line)
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
        case "pressure":
            return f"pressure stag={data.get('stagnation')} pwr={data.get('power', '')}"
        case "moe.route":
            return f"route ->@{data.get('to', '')} w={data.get('weight', '')}"
        case "moe.escalate":
            return f"ESCALATE @{data.get('from', '')} ->@{data.get('to', '')} s{data.get('slot', '')}"
        case "moe.yield":
            return f"moe.yield {str(data.get('reason', ''))[:80]}"
        case "human.decline":
            reason = str(data.get("reason", ""))[:80]
            suggestion = str(data.get("suggested_rephrase", ""))[:120]
            return f"human.decline {reason} try={suggestion}" if suggestion else f"human.decline {reason}"
        case _:
            return f"{phase} {str(data)[:120]}"


def _count_text(counts: Counter[str]) -> str:
    if not counts:
        return "none"
    return " ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def format_breeder_evidence(limit: int | None = None) -> str:
    """Summarize AgentBreeder evidence mirrored to the observation bus."""
    n = limit or config.BUS_EVENTS_MAX
    events = read_events(n)
    breeder: list[dict[str, Any]] = []
    evolve_counts: Counter[str] = Counter()
    breed_counts: Counter[str] = Counter()
    niches: set[str] = set()
    trial_ids: set[str] = set()
    for entry in events:
        kind = str(entry.get("kind", ""))
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        action = str(payload.get("action", ""))
        if kind == KIND_EVOLVE:
            breeder.append(entry)
            evolve_counts[action or "unknown"] += 1
        elif kind == KIND_STATUS and action.startswith("breed."):
            breeder.append(entry)
            breed_counts[action] += 1
        else:
            continue
        niche = str(payload.get("niche", ""))
        if niche:
            niches.add(niche[:80])
        trial_id = str(payload.get("trial_id", ""))
        if trial_id:
            trial_ids.add(trial_id[:80])

    if not breeder:
        return "BREEDER EVIDENCE: none in observation bus"

    lines = [f"BREEDER EVIDENCE (last {n} observation events)"]
    lines.append(f"  evolve: {sum(evolve_counts.values())} {_count_text(evolve_counts)}")
    lines.append(f"  breed: {sum(breed_counts.values())} {_count_text(breed_counts)}")
    if niches:
        lines.append(f"  niches: {len(niches)} " + " ".join(sorted(niches)[:8]))
    if trial_ids:
        lines.append(f"  trials: {len(trial_ids)} " + " ".join(sorted(trial_ids)[:6]))

    outcomes = [
        e for e in breeder
        if str((e.get("payload") or {}).get("action", "")) in ("breed.improve", "breed.regress", "breed.neutral")
    ]
    if outcomes:
        outcome_counts = Counter(str((e.get("payload") or {}).get("action", "")) for e in outcomes)
        best_stag = max(float((e.get("payload") or {}).get("stagnation_delta", 0.0) or 0.0) for e in outcomes)
        best_power = max(float((e.get("payload") or {}).get("power_delta", 0.0) or 0.0) for e in outcomes)
        total_fissions = sum(int((e.get("payload") or {}).get("fission_delta", 0) or 0) for e in outcomes)
        repeated = sum(1 for e in outcomes if int((e.get("payload") or {}).get("sample", 0) or 0) > 1)
        lines.append(
            f"  selection outcomes: {len(outcomes)} {_count_text(outcome_counts)} "
            f"best_stagnation_delta={best_stag:.4f} best_power_delta={best_power:.4f} "
            f"fission_delta_total={total_fissions} repeated_samples={repeated}"
        )
        lines.append("  closed_loop: yes")
    else:
        lines.append("  closed_loop: waiting_for_selection_outcome")

    lines.append("  latest:")
    for entry in breeder[-8:]:
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        kind = str(entry.get("kind", ""))
        action = str(payload.get("action", ""))
        target = str(payload.get("target") or entry.get("to") or "")
        fitness = payload.get("fitness", "")
        fit = f" fit={float(fitness):.3f}" if isinstance(fitness, (int, float)) else ""
        niche = f" niche={str(payload.get('niche', ''))[:60]}" if payload.get("niche") else ""
        deltas = []
        for key in ("trial_id", "sample", "stagnation_delta", "power_delta", "fission_delta"):
            if key in payload:
                deltas.append(f"{key}={payload.get(key)}")
        delta = " " + " ".join(deltas) if deltas else ""
        lines.append(f"    #{entry.get('id')} {kind} {action} @{target}{fit}{niche}{delta}")
    return "\n".join(lines)


# --- CLI ---

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "post":
        from_id = sys.argv[2]
        data: dict[str, Any] = {}
        text_parts: list[str] = []
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--ack":
                data["human_ack"] = True
            elif arg == "--blocked-by" and i + 1 < len(args):
                i += 1
                data["blocked_by"] = args[i][:200]
            elif arg == "--suggest" and i + 1 < len(args):
                i += 1
                data["suggested_rephrase"] = args[i][:240]
            else:
                text_parts.append(arg)
            i += 1
        text = " ".join(text_parts)
        config.BUS_INJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.BUS_INJECT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "from": from_id,
                "text": text,
                "kind": KIND_MESSAGE,
                "data": data,
            }, ensure_ascii=False) + "\n")
        drain_inject()
        print(f"bus @{from_id}: {text[:120]}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "state":
        for who, st in colony_state().items():
            print(f"@{who}: {st}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "breeder":
        try:
            event_limit = int(sys.argv[2]) if len(sys.argv) >= 3 else config.BUS_EVENTS_MAX
        except ValueError:
            event_limit = config.BUS_EVENTS_MAX
        print(format_breeder_evidence(event_limit))
    else:
        print(format_bus_context(15) or "(bus empty)")
