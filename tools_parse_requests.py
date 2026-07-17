"""Reusable parser for the xAI request-logs JSONL (one request/response per line).

Reverse-engineered structure (per line):
  meta:   requestId, apiKeyId, timestamp, modelName, kind, bodyAvailability
  logged.chat.request:  messages[], model, maxTokens, responseFormat, temperature,
                        reasoningEffort, include
  logged.chat.response: id, outputs[{finishReason, message.content(JSON str)}],
                        created, model, systemFingerprint, usage{...}

The response message.content is the organism's committed record (record_type + data).
This script reconstructs the SHAPE OF THE MOTION: for each turn — the faculty
(record_type), reasoning effort, token usage, the emitted signal proxy (verdict /
next_signal), and the living-word rows — so a run can be read as a story without
pouring raw logs into context.

Usage:
  python3 tools_parse_requests.py <file.jsonl> [--full N]   # N = dump full record for line N
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _load(path: str) -> list[dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            out.append((i, json.loads(line)))
    return out


def _record(resp: dict[str, Any]) -> dict[str, Any] | None:
    outs = resp.get("outputs") or []
    if not outs:
        return None
    content = (outs[0].get("message") or {}).get("content") or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"_unparsed": content[:200]}


def _signal_proxy(rtype: str, data: dict[str, Any]) -> str:
    if rtype == "verification":
        # verdict lives in authored probe code, not the record; infer from goal_interp
        return "verify(code-probe)"
    return str(data.get("next_signal") or "").strip() or "-"


def summarize(rows: list[tuple[int, dict[str, Any]]]) -> None:
    print(f"{'ln':>3} {'faculty':<12} {'effort':<5} {'in':>6} {'out':>6} {'reason':>6} signal / done_when")
    print("-" * 100)
    tot_in = tot_out = tot_reason = 0
    faculty_counts: dict[str, int] = {}
    for ln, obj in rows:
        req = obj.get("logged", {}).get("chat", {}).get("request", {})
        resp = obj.get("logged", {}).get("chat", {}).get("response", {})
        usage = resp.get("usage", {}) or {}
        effort = str(req.get("reasoningEffort", "?"))
        rec = _record(resp) or {}
        rtype = str(rec.get("record_type", "?"))
        data = rec.get("data", {}) if isinstance(rec, dict) else {}
        faculty_counts[rtype] = faculty_counts.get(rtype, 0) + 1
        pin = int(usage.get("promptTokens") or usage.get("inputTokens") or usage.get("prompt_tokens") or 0)
        pout = int(usage.get("completionTokens") or usage.get("outputTokens") or usage.get("completion_tokens") or 0)
        preason = int(usage.get("reasoningTokens") or (usage.get("completionTokensDetails") or {}).get("reasoningTokens") or 0)
        tot_in += pin
        tot_out += pout
        tot_reason += preason
        tail = _signal_proxy(rtype, data)
        dw = str(data.get("done_when") or "")[:50]
        print(f"{ln:>3} {rtype:<12} {effort:<5} {pin:>6} {pout:>6} {preason:>6} {tail} | {dw}")
    print("-" * 100)
    print(f"lines={len(rows)} tot_in={tot_in} tot_out={tot_out} tot_reason={tot_reason}")
    print("faculty distribution:", faculty_counts)


def living_word_trace(rows: list[tuple[int, dict[str, Any]]]) -> None:
    print("\n=== LIVING WORD (goal_interpretation per turn) ===")
    for ln, obj in rows:
        resp = obj.get("logged", {}).get("chat", {}).get("response", {})
        rec = _record(resp) or {}
        data = rec.get("data", {}) if isinstance(rec, dict) else {}
        gi = str(data.get("goal_interpretation") or "").strip()
        rtype = str(rec.get("record_type", "?"))
        if gi:
            print(f"[{ln:>3} {rtype:<11}] {gi[:220]}")


def dump_full(rows: list[tuple[int, dict[str, Any]]], n: int) -> None:
    for ln, obj in rows:
        if ln == n:
            resp = obj.get("logged", {}).get("chat", {}).get("response", {})
            print(json.dumps(_record(resp), indent=2, ensure_ascii=False))
            return
    print(f"line {n} not found")


def dump_code(rows: list[tuple[int, dict[str, Any]]]) -> None:
    """Dump the FULL authored code + full goal_interpretation for every turn.
    Nothing truncated — the launch script and the verifier probe are the crime scene."""
    for ln, obj in rows:
        resp = obj.get("logged", {}).get("chat", {}).get("response", {})
        rec = _record(resp) or {}
        rtype = str(rec.get("record_type", "?"))
        data = rec.get("data", {}) if isinstance(rec, dict) else {}
        print(f"\n{'='*100}\n=== LINE {ln}  [{rtype}] ===")
        for field in ("perceived", "intent", "done_when", "target", "strategy", "lesson"):
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
    path = sys.argv[1] if len(sys.argv) > 1 else "request-logs-2026-07-16.jsonl"
    rows = _load(path)
    if "--full" in sys.argv:
        dump_full(rows, int(sys.argv[sys.argv.index("--full") + 1]))
    elif "--code" in sys.argv:
        dump_code(rows)
    else:
        summarize(rows)
        living_word_trace(rows)
