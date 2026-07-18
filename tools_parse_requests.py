"""Reusable parser for the xAI request-logs JSONL (one request/response per line).

Reverse-engineered structure (per line):
  meta:   requestId, apiKeyId, timestamp, modelName, kind, bodyAvailability
  logged.chat.request:  messages[], model, maxTokens, responseFormat, temperature,
                        reasoningEffort, include
  logged.chat.response: id, outputs[{finishReason, message.content(JSON str)}],
                        created, model, systemFingerprint, usage{...}

The response message.content is the organism's committed record (record_type + data).

Signal reconstruction (the shape of the motion):
  Only thinking faculties call the model, so the JSONL holds exactly the
  execution/verification/recovery turns — not the observe/guidance nodes between
  them. The emitted signal of each turn is therefore inferred from the wiring by
  the faculty that FOLLOWS it (turns sorted by timestamp):
    execution   -> recovery      : execute emitted 'deed_denied' (authored script raised)
    execution   -> verification  : execute emitted 'done'
    verification-> guidance/exec  : verify emitted 'deed_confirmed' (goal advanced, not whole)
    verification-> recovery      : verify emitted 'deed_denied'
    verification-> (end)         : verify emitted 'halt' (goal_satisfied) — the only clean exit
    recovery    -> execution     : recover emitted 'recovered'
  A recovery followed directly by a verification is a TOPOLOGY VIOLATION under the
  current wiring (recover routes only to guidance->observe:act->execute) and is
  flagged, because it means the log is not in pure wheel order or a turn is missing.

Usage:
  python3 tools_parse_requests.py <file.jsonl>            # motion summary + living-word trace
  python3 tools_parse_requests.py <file.jsonl> --full N   # full record for line N
  python3 tools_parse_requests.py <file.jsonl> --code     # full authored code, every turn
"""
from __future__ import annotations

import json
import sys
from typing import Any

Row = tuple[int, dict[str, Any]]


def _load(path: str) -> list[Row]:
    out: list[Row] = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            out.append((i, json.loads(line)))
    return out


def _resp(obj: dict[str, Any]) -> dict[str, Any]:
    return obj.get("logged", {}).get("chat", {}).get("response", {}) or {}


def _req(obj: dict[str, Any]) -> dict[str, Any]:
    return obj.get("logged", {}).get("chat", {}).get("request", {}) or {}


def _record(resp: dict[str, Any]) -> dict[str, Any]:
    outs = resp.get("outputs") or []
    if not outs:
        return {}
    content = (outs[0].get("message") or {}).get("content") or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"_unparsed": content[:200]}


def _rtype(obj: dict[str, Any]) -> str:
    return str(_record(_resp(obj)).get("record_type", "?"))


def _data(obj: dict[str, Any]) -> dict[str, Any]:
    rec = _record(_resp(obj))
    return rec.get("data", {}) if isinstance(rec, dict) else {}


def _usage(obj: dict[str, Any]) -> tuple[int, int, int]:
    u = _resp(obj).get("usage", {}) or {}
    pin = int(u.get("promptTokens") or u.get("inputTokens") or u.get("prompt_tokens") or 0)
    pout = int(u.get("completionTokens") or u.get("outputTokens") or u.get("completion_tokens") or 0)
    preason = int(u.get("reasoningTokens") or (u.get("completionTokensDetails") or {}).get("reasoningTokens") or 0)
    return pin, pout, preason


# emitted signal of THIS faculty, inferred from the faculty that follows it
_TRANSITION = {
    ("execution", "recovery"): "deed_denied",
    ("execution", "verification"): "done",
    ("recovery", "execution"): "recovered",
    ("verification", "execution"): "deed_confirmed",
    ("verification", "recovery"): "deed_denied",
}


def _inferred_signal(this: str, nxt: str | None) -> str:
    if nxt is None:
        if this == "verification":
            return "halt(goal_satisfied?)"
        return "(log ends here)"
    sig = _TRANSITION.get((this, nxt))
    if sig:
        return sig
    return f"!! ANOMALY {this}->{nxt}"


def _chronological(rows: list[Row]) -> list[Row]:
    def ts(obj: dict[str, Any]) -> str:
        return str(obj.get("meta", {}).get("timestamp") or obj.get("timestamp") or "")
    if all(ts(o) for _, o in rows):
        return sorted(rows, key=lambda r: ts(r[1]))
    return rows


def summarize(rows: list[Row]) -> None:
    rows = _chronological(rows)
    faculties = [_rtype(o) for _, o in rows]
    print(f"{'ln':>3} {'faculty':<12} {'effort':<6} {'in':>6} {'out':>6} {'reason':>6}  emitted signal")
    print("-" * 100)
    tot_in = tot_out = tot_reason = 0
    counts: dict[str, int] = {}
    anomalies: list[str] = []
    for idx, (ln, obj) in enumerate(rows):
        rtype = faculties[idx]
        nxt = faculties[idx + 1] if idx + 1 < len(faculties) else None
        effort = str(_req(obj).get("reasoningEffort", "?"))
        pin, pout, preason = _usage(obj)
        tot_in += pin; tot_out += pout; tot_reason += preason
        counts[rtype] = counts.get(rtype, 0) + 1
        sig = _inferred_signal(rtype, nxt)
        if "ANOMALY" in sig:
            anomalies.append(f"  line {ln}: {sig}")
        print(f"{ln:>3} {rtype:<12} {effort:<6} {pin:>6} {pout:>6} {preason:>6}  {sig}")
    print("-" * 100)
    print(f"lines={len(rows)} tot_in={tot_in} tot_out={tot_out} tot_reason={tot_reason}")
    print("faculty distribution:", counts)
    verifications = counts.get("verification", 0)
    print(f"verification share: {verifications}/{len(rows)} "
          f"({100 * verifications / max(len(rows), 1):.0f}%) — a live-lock starves the witness")
    if anomalies:
        print("TRANSITION ANOMALIES (log not in wheel order, or a turn is missing):")
        print("\n".join(anomalies))


def living_word_trace(rows: list[Row]) -> None:
    print("\n=== LIVING WORD (goal_interpretation per turn) ===")
    for ln, obj in _chronological(rows):
        gi = str(_data(obj).get("goal_interpretation") or "").strip()
        if gi:
            print(f"[{ln:>3} {_rtype(obj):<11}] {gi[:220]}")


def dump_full(rows: list[Row], n: int) -> None:
    for ln, obj in rows:
        if ln == n:
            print(json.dumps(_record(_resp(obj)), indent=2, ensure_ascii=False))
            return
    print(f"line {n} not found")


def dump_code(rows: list[Row]) -> None:
    """Dump the FULL authored code + narrative fields for every turn — the crime scene, untruncated."""
    for ln, obj in _chronological(rows):
        rtype = _rtype(obj)
        data = _data(obj)
        print(f"\n{'='*100}\n=== LINE {ln}  [{rtype}] ===")
        for field in ("perceived", "intent", "target", "strategy", "lesson", "risk"):
            v = data.get(field)
            if v:
                print(f"--- {field}:\n{v}")
        gi = data.get("goal_interpretation")
        if gi:
            print(f"--- goal_interpretation:\n{gi}")
        code = data.get("code")
        if code:
            print(f"--- code:\n{code}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "request-logs-2026-07-18.jsonl"
    rows = _load(path)
    if "--full" in sys.argv:
        dump_full(rows, int(sys.argv[sys.argv.index("--full") + 1]))
    elif "--code" in sys.argv:
        dump_code(rows)
    else:
        summarize(rows)
        living_word_trace(rows)
