"""Generic, schema-agnostic reader for the endgame-ai brain request-log (JSONL).

DESIGN LAWS (so this tool outlives every schema change):
  1. AUTODETECT the log: given no path, glob the workspace for *.jsonl, keep those
     whose first record looks like a brain log (bears a request+response by ANY of the
     known nesting shapes), and pick the most recently modified. The log's NAME is not
     load-bearing; its SHAPE is.
  2. TOLERATE drift: every field is reached through a list of candidate paths, never one
     hardcoded path. A renamed or newly-nested key is added to the candidate list, and
     old logs keep parsing. Missing keys degrade to a printed marker, never a crash.
  3. NEVER truncate silently: previews are opt-in and bounded; --no-truncate and the
     content-dumping modes (--code, --full, --raw, --field) always print the whole thing.
  4. Stay useful when record_type is unknown: the motion table and signal inference work
     for any faculty set; unknown faculties are shown, not dropped.

The response's message content is the organism's committed record: {record_type, data}.
Only thinking faculties call the model, so the log holds exactly the execution/
verification/recovery turns — not the observe/guidance nodes between them. Each turn's
emitted signal is inferred from the faculty that FOLLOWS it (turns sorted by timestamp).

USAGE (path optional everywhere — omit to autodetect):
  python tools_parse_requests.py                      # motion summary + living word
  python tools_parse_requests.py LOGS.jsonl           # same, explicit file
  python tools_parse_requests.py --code               # full authored code, every turn
  python tools_parse_requests.py --full 7             # whole committed record for line 7
  python tools_parse_requests.py --raw 7              # full system+user messages for line 7
  python tools_parse_requests.py --field goal_interpretation   # one field, all turns, untruncated
  python tools_parse_requests.py --grep IndentationError       # regex over code+data+reason
  python tools_parse_requests.py --usage              # tokens, cache hits, cost per turn
  python tools_parse_requests.py --record-type verification    # filter the summary
  python tools_parse_requests.py --line 7             # restrict any mode to one line
  python tools_parse_requests.py --no-truncate        # disable every preview cap
Flags compose; --code/--full/--raw/--field/--grep/--usage select the mode, the rest filter.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Any

Row = tuple[int, dict[str, Any]]

# ---- schema-agnostic accessors: each returns the first candidate path that resolves ----


def _dig(obj: Any, *paths: str) -> Any:
    """Return the first path (dot-separated, [i] for list index) that resolves non-None."""
    for path in paths:
        cur: Any = obj
        ok = True
        for part in path.split("."):
            m = re.fullmatch(r"([^\[]*)(?:\[(\d+)\])?", part)
            key, idx = (m.group(1), m.group(2)) if m else (part, None)
            if key:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    ok = False
                    break
            if idx is not None:
                if isinstance(cur, list) and int(idx) < len(cur):
                    cur = cur[int(idx)]
                else:
                    ok = False
                    break
        if ok and cur is not None:
            return cur
    return None


def _request(obj: dict[str, Any]) -> dict[str, Any]:
    return _dig(obj, "logged.chat.request", "logged.request", "request", "chat.request") or {}


def _response(obj: dict[str, Any]) -> dict[str, Any]:
    return _dig(obj, "logged.chat.response", "logged.response", "response", "chat.response") or {}


def _content(obj: dict[str, Any]) -> str:
    """The committed record text, from whichever response shape the log uses."""
    resp = _response(obj)
    val = _dig(
        resp,
        "outputs[0].message.content",
        "output[0].content[0].text",
        "choices[0].message.content",
        "output_text",
        "message.content",
    )
    if isinstance(val, list):
        return "".join(str(p.get("text", "")) for p in val if isinstance(p, dict))
    return str(val or "")


def _record(obj: dict[str, Any]) -> dict[str, Any]:
    content = _content(obj)
    try:
        rec = json.loads(content)
        return rec if isinstance(rec, dict) else {"_unparsed": content}
    except (json.JSONDecodeError, TypeError):
        return {"_unparsed": content} if content else {}


def _rtype(obj: dict[str, Any]) -> str:
    return str(_record(obj).get("record_type") or "?")


def _data(obj: dict[str, Any]) -> dict[str, Any]:
    d = _record(obj).get("data")
    return d if isinstance(d, dict) else {}


def _effort(obj: dict[str, Any]) -> str:
    return str(_dig(_request(obj), "reasoningEffort", "reasoning.effort", "reasoning_effort") or "?")


def _timestamp(obj: dict[str, Any]) -> str:
    return str(_dig(obj, "meta.timestamp", "timestamp", "created", "logged.chat.response.created") or "")


def _usage(obj: dict[str, Any]) -> dict[str, int]:
    u = _dig(_response(obj), "usage") or {}
    def pick(*names: str) -> int:
        for n in names:
            if n in u and u[n] is not None:
                try:
                    return int(u[n])
                except (TypeError, ValueError):
                    return 0
        return 0
    return {
        "in": pick("promptTokens", "inputTokens", "prompt_tokens"),
        "out": pick("completionTokens", "outputTokens", "completion_tokens"),
        "reason": pick("reasoningTokens", "reasoning_tokens") or int(_dig(u, "completionTokensDetails.reasoningTokens") or 0),
        "cached": pick("cachedPromptTextTokens", "cachedPromptTokens", "cached_tokens"),
        "cost_ticks": pick("costInUsdTicks"),
    }


# ---- signal inference: emitted signal of THIS faculty, from the one that follows ----

_TRANSITION = {
    ("execution", "recovery"): "deed_denied",
    ("execution", "verification"): "done",
    ("recovery", "execution"): "recovered",
    ("verification", "execution"): "deed_confirmed",
    ("verification", "recovery"): "deed_denied",
}


def _inferred_signal(this: str, nxt: str | None) -> str:
    if nxt is None:
        return "halt(goal_satisfied?)" if this == "verification" else "(log ends here)"
    sig = _TRANSITION.get((this, nxt))
    return sig if sig else f"!! ANOMALY {this}->{nxt}"


# ---- loading + autodetection ----


def _looks_like_brain_log(first_line: str) -> bool:
    try:
        o = json.loads(first_line)
    except json.JSONDecodeError:
        return False
    return isinstance(o, dict) and bool(_request(o)) and bool(_response(o))


def autodetect(explicit: str | None) -> str:
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = sorted(glob.glob(os.path.join(here, "*.jsonl")), key=os.path.getmtime, reverse=True)
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        if _looks_like_brain_log(line):
                            return path
                        break
        except OSError:
            continue
    raise SystemExit("no brain-log *.jsonl found next to this script; pass a path explicitly")


def load(path: str) -> list[Row]:
    out: list[Row] = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                out.append((i, json.loads(line)))
            except json.JSONDecodeError as exc:
                print(f"WARN line {i}: unparseable JSON ({exc}); skipped", file=sys.stderr)
    return out


def chronological(rows: list[Row]) -> list[Row]:
    if all(_timestamp(o) for _, o in rows):
        return sorted(rows, key=lambda r: _timestamp(r[1]))
    return rows


# ---- output modes ----


def summarize(rows: list[Row], rtype_filter: str | None) -> None:
    rows = chronological(rows)
    faculties = [_rtype(o) for _, o in rows]
    print(f"{'ln':>3} {'faculty':<12} {'effort':<12} {'in':>6} {'out':>6} {'reason':>6} {'cache':>6}  emitted signal")
    print("-" * 108)
    tin = tout = treason = tcache = 0
    counts: dict[str, int] = {}
    anomalies: list[str] = []
    for idx, (ln, obj) in enumerate(rows):
        rt = faculties[idx]
        nxt = faculties[idx + 1] if idx + 1 < len(faculties) else None
        u = _usage(obj)
        tin += u["in"]; tout += u["out"]; treason += u["reason"]; tcache += u["cached"]
        counts[rt] = counts.get(rt, 0) + 1
        sig = _inferred_signal(rt, nxt)
        if "ANOMALY" in sig:
            anomalies.append(f"  line {ln}: {sig}")
        if rtype_filter and rt != rtype_filter:
            continue
        print(f"{ln:>3} {rt:<12} {_effort(obj):<12} {u['in']:>6} {u['out']:>6} {u['reason']:>6} {u['cached']:>6}  {sig}")
    print("-" * 108)
    print(f"lines={len(rows)} tot_in={tin} tot_out={tout} tot_reason={treason} tot_cached={tcache} "
          f"(cache_hit={100*tcache/max(tin,1):.0f}% of prompt tokens)")
    print("faculty distribution:", counts)
    v = counts.get("verification", 0)
    print(f"verification share: {v}/{len(rows)} ({100*v/max(len(rows),1):.0f}%) — a live-lock starves the witness")
    if anomalies:
        print("TRANSITION ANOMALIES (log not in wheel order, or a turn is missing):")
        print("\n".join(anomalies))


def living_word(rows: list[Row], truncate: int | None) -> None:
    print("\n=== LIVING WORD (goal_interpretation per turn) ===")
    for ln, obj in chronological(rows):
        gi = str(_data(obj).get("goal_interpretation") or "").strip()
        if gi:
            print(f"[{ln:>3} {_rtype(obj):<11}] {gi if truncate is None else gi[:truncate]}")


def usage_report(rows: list[Row]) -> None:
    print(f"{'ln':>3} {'faculty':<12} {'in':>7} {'cached':>7} {'out':>7} {'reason':>7} {'cost($)':>10}")
    print("-" * 62)
    tot = {"in": 0, "cached": 0, "out": 0, "reason": 0, "cost_ticks": 0}
    for ln, obj in chronological(rows):
        u = _usage(obj)
        for k in tot:
            tot[k] += u[k]
        print(f"{ln:>3} {_rtype(obj):<12} {u['in']:>7} {u['cached']:>7} {u['out']:>7} {u['reason']:>7} {u['cost_ticks']/1e12:>10.6f}")
    print("-" * 62)
    print(f"{'TOT':>3} {'':<12} {tot['in']:>7} {tot['cached']:>7} {tot['out']:>7} {tot['reason']:>7} {tot['cost_ticks']/1e12:>10.6f}")
    print(f"cache hit rate: {100*tot['cached']/max(tot['in'],1):.1f}% of prompt tokens reused")


def dump_code(rows: list[Row]) -> None:
    for ln, obj in chronological(rows):
        data = _data(obj)
        print(f"\n{'='*100}\n=== LINE {ln}  [{_rtype(obj)}] ===")
        for field in ("perceived", "intent", "target", "strategy", "lesson", "risk", "goal_interpretation"):
            v = data.get(field)
            if v:
                print(f"--- {field}:\n{v}")
        if data.get("code"):
            print(f"--- code:\n{data['code']}")
        if "_unparsed" in data:
            print(f"--- UNPARSED CONTENT:\n{data['_unparsed']}")


def dump_full(rows: list[Row], n: int) -> None:
    for ln, obj in rows:
        if ln == n:
            print(json.dumps(_record(obj), indent=2, ensure_ascii=False))
            return
    print(f"line {n} not found")


def dump_raw(rows: list[Row], n: int) -> None:
    """The full system+user messages sent for line n — the exact prompt, untruncated."""
    for ln, obj in rows:
        if ln == n:
            msgs = _dig(_request(obj), "messages", "input") or []
            for m in msgs:
                role = m.get("role", "?")
                content = m.get("content")
                if isinstance(content, list):
                    content = "".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
                print(f"\n{'='*100}\n=== [{role}] ===\n{content}")
            return
    print(f"line {n} not found")


def dump_field(rows: list[Row], field: str, truncate: int | None) -> None:
    print(f"=== field '{field}' across all turns ===")
    for ln, obj in chronological(rows):
        v = _data(obj).get(field)
        if v is not None and str(v).strip():
            text = str(v) if truncate is None else str(v)[:truncate]
            print(f"\n[{ln:>3} {_rtype(obj):<11}]\n{text}")


def grep(rows: list[Row], pattern: str) -> None:
    rx = re.compile(pattern, re.I)
    print(f"=== grep '{pattern}' over code + narrative fields ===")
    for ln, obj in chronological(rows):
        data = _data(obj)
        blob = "\n".join(str(v) for v in data.values() if isinstance(v, str))
        for m in rx.finditer(blob):
            s = max(0, m.start() - 60)
            e = min(len(blob), m.end() + 60)
            snippet = blob[s:e].replace("\n", " ")
            print(f"[{ln:>3} {_rtype(obj):<11}] …{snippet}…")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generic schema-agnostic endgame-ai brain-log reader")
    ap.add_argument("path", nargs="?", default=None, help="log path; omit to autodetect newest *.jsonl")
    ap.add_argument("--code", action="store_true", help="full authored code + narrative, every turn")
    ap.add_argument("--full", type=int, metavar="N", help="whole committed record for line N")
    ap.add_argument("--raw", type=int, metavar="N", help="full system+user prompt for line N")
    ap.add_argument("--field", metavar="NAME", help="one data field across all turns, untruncated")
    ap.add_argument("--grep", metavar="PATTERN", help="regex over code + narrative fields")
    ap.add_argument("--usage", action="store_true", help="token + cache + cost breakdown")
    ap.add_argument("--record-type", metavar="TYPE", help="filter summary to one faculty")
    ap.add_argument("--line", type=int, metavar="N", help="restrict summary/code/field/grep to one line")
    ap.add_argument("--no-truncate", action="store_true", help="disable every preview cap")
    args = ap.parse_args(argv)

    path = autodetect(args.path)
    print(f"# log: {path}", file=sys.stderr)
    rows = load(path)
    if args.line is not None:
        rows = [r for r in rows if r[0] == args.line]
    truncate = None if args.no_truncate else 220

    if args.full is not None:
        dump_full(rows, args.full)
    elif args.raw is not None:
        dump_raw(rows, args.raw)
    elif args.code:
        dump_code(rows)
    elif args.field:
        dump_field(rows, args.field, truncate)
    elif args.grep:
        grep(rows, args.grep)
    elif args.usage:
        usage_report(rows)
    else:
        summarize(rows, args.record_type)
        living_word(rows, truncate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
