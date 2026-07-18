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
  python tools_parse_requests.py --stats              # untruncated motion + failure-streak + effects
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
    """The committed record text, from whichever response shape the log uses.

    The /v1/responses output is a LIST whose reasoning and message items may appear in
    any order (reasoning commonly precedes the message), so the message is found by SHAPE
    — the non-reasoning item bearing output_text — never by a fixed index."""
    resp = _response(obj)
    output = _dig(resp, "output", "outputs")
    if isinstance(output, list):
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") == "reasoning":
                continue
            content = item.get("content")
            if isinstance(content, list):
                texts.extend(str(c.get("text", "")) for c in content if isinstance(c, dict) and c.get("text"))
            elif isinstance(content, str):
                texts.append(content)
        if texts:
            return "".join(texts)
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
    # LEGAL self-loop: a witness probe that raised routes verify -> observe:verify ->
    # verify again (the run-berta fix: a probe fault is NOT a deed denial). Two
    # consecutive verification turns are this "unwitnessed" re-look, never an anomaly.
    ("verification", "verification"): "unwitnessed",
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


# ---- effect extraction: what did an execution's authored code ACTUALLY do? ----
# Schema-agnostic: scans the authored [code] string for the desktop-hand verbs and
# stdlib effects that move the world or the disk. Names come from core_desktop's
# public methods + the file/process primitives; each is a real effect, not a claim.

_EFFECT_PATTERNS: dict[str, str] = {
    "open_url": r"\.open_url\s*\(",
    "click": r"\.click\s*\(",
    "type_text": r"\.type_text\s*\(",
    "press_key": r"\.press_key\s*\(",
    "hotkey": r"\.hotkey\s*\(",
    "scroll": r"\.scroll\s*\(",
    "observe": r"\.observe\s*\(",
    "expand": r"\.expand\s*\(",
    "consult_model": r"\bconsult_model\s*\(",
    "file_write": r"open\s*\([^)]*['\"][wax]\b|\.write_text\s*\(|\.write\s*\(|json\.dump\s*\(",
    "file_read": r"\.read_text\s*\(|\.read\s*\(|json\.load\s*\(|open\s*\([^)]*['\"]r\b",
    "subprocess": r"\bsubprocess\.|\bos\.system\s*\(|\bPopen\s*\(",
    "glob_scan": r"\bglob\.|\.glob\s*\(|\.rglob\s*\(|os\.walk\s*\(|\.iterdir\s*\(",
    "http": r"\brequests\.|urllib|http\.client|\.urlopen\s*\(",
}


def _effects(code: str) -> list[str]:
    if not code:
        return []
    return [name for name, pat in _EFFECT_PATTERNS.items() if re.search(pat, code)]


# Whole-goal axes for THIS run's goal, so axis attribution is printed & reproducible,
# never a hidden judgment. Ordered; an effect/text is tagged to the first axis it hits.
_GOAL_AXES: list[tuple[str, str]] = [
    ("inventory_selftalk", r"inventory|self_inventory|witness\.json|self-aware|self aware|capabilit|creator|readme|README"),
    ("open_code_improve", r"open\s*code|opencode|self[- ]?diagnose|self[- ]?improve|diagnose"),
    ("chrome_publish", r"chrome|x\.com|twitter|linkedin|article|publish|browser|navigate|url"),
]


def _axis(code: str, data: dict[str, Any]) -> str:
    blob = (code or "") + "\n" + "\n".join(str(v) for v in data.values() if isinstance(v, str))
    hits = [name for name, pat in _GOAL_AXES if re.search(pat, blob, re.I)]
    # An execution that only touches inventory AND mentions later axes only as
    # "blocked/next" is still an inventory-axis deed. Prefer the axis whose verbs
    # the CODE actually enacts; fall back to the first textual hit.
    code_hits = [name for name, pat in _GOAL_AXES if code and re.search(pat, code, re.I)]
    if code_hits:
        return code_hits[0]
    return hits[0] if hits else "(none)"


def stats(rows: list[Row]) -> None:
    """Untruncated per-turn motion: signal, failure_streak, effects, goal-axis; then
    run-length encodings and histograms. This is the enriched instrument for deduction."""
    rows = chronological(rows)
    faculties = [_rtype(o) for _, o in rows]

    # failure_streak per the KB law: monotonic count of turns since the last
    # INDEPENDENTLY WITNESSED deed (deed_confirmed). Cleared only by deed_confirmed.
    print("=== PER-TURN MOTION (untruncated) ===")
    print(f"{'ln':>3} {'faculty':<12} {'signal':<14} {'fstreak':>7} {'axis':<18} effects")
    print("-" * 100)
    streak = 0
    streak_traj: list[int] = []
    signals: list[str] = []
    axes: list[str] = []
    effect_hist: dict[str, int] = {}
    axis_hist: dict[str, int] = {}
    confirmed_effects: list[list[str]] = []
    prior: list[tuple[str, list[str]]] = []
    for idx, (ln, obj) in enumerate(rows):
        rt = faculties[idx]
        nxt = faculties[idx + 1] if idx + 1 < len(faculties) else None
        sig = _inferred_signal(rt, nxt)
        signals.append(sig)
        data = _data(obj)
        code = str(data.get("code") or "")
        eff = _effects(code) if rt == "execution" else []
        ax = _axis(code, data) if rt == "execution" else "-"
        for e in eff:
            effect_hist[e] = effect_hist.get(e, 0) + 1
        if rt == "execution":
            axis_hist[ax] = axis_hist.get(ax, 0) + 1
            axes.append(ax)
        # streak update: a confirmed deed clears it; every other turn increments.
        # deed_confirmed is emitted BY a verification turn ABOUT the deed of the
        # preceding execution, so the confirmed effect is that prior execution's code.
        if sig == "deed_confirmed":
            prev_eff = next((e for (r, e) in reversed(prior) if r == "execution"), [])
            confirmed_effects.append(prev_eff)
            streak = 0
        else:
            streak += 1
        prior.append((rt, eff))
        streak_traj.append(streak)
        print(f"{ln:>3} {rt:<12} {sig:<14} {streak:>7} {ax:<18} {','.join(eff) if eff else ''}")
    print("-" * 100)

    # run-length encoding of the signal stream
    print("\n=== SIGNAL RUN-LENGTH ENCODING (chronological) ===")
    rle: list[tuple[str, int]] = []
    for s in signals:
        if rle and rle[-1][0] == s:
            rle[-1] = (s, rle[-1][1] + 1)
        else:
            rle.append((s, 1))
    print("  " + "  ".join(f"{s}x{n}" if n > 1 else s for s, n in rle))

    print("\n=== FAILURE-STREAK TRAJECTORY ===")
    print("  max streak reached:", max(streak_traj) if streak_traj else 0,
          "| final streak:", streak_traj[-1] if streak_traj else 0)
    print("  (KB law: streak clears ONLY on deed_confirmed; the wider it climbs the more"
          " recovery must change KIND of road. A proxy that keeps yielding confirmable"
          " micro-advances keeps this near 0 and defeats the only escape mechanism.)")
    print("  trajectory:", streak_traj)

    print("\n=== EFFECT HISTOGRAM (what the executor's code actually did) ===")
    for name, n in sorted(effect_hist.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<14} {n}")
    if not effect_hist:
        print("  (no world/disk effects detected in any execution's code)")

    print("\n=== GOAL-AXIS HISTOGRAM (which axis each execution advanced) ===")
    for name, n in sorted(axis_hist.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<20} {n}")

    print("\n=== CONFIRMED-DEED EFFECTS (what each independently-witnessed deed did) ===")
    for i, eff in enumerate(confirmed_effects):
        print(f"  confirm #{i+1}: {','.join(eff) if eff else '(no code effect — narrative/again)'}")
    print(f"\n  confirmed deeds: {len(confirmed_effects)} | "
          f"of which touched chrome_publish axis: "
          f"{sum(1 for e in confirmed_effects if any(x in ('open_url','click') for x in e))}"
          " (proxy-divisibility test: if ~all confirms are file_write on inventory,"
          " the witness honestly confirmed advances orthogonal to the real goal)")


def verdicts(rows: list[Row]) -> None:
    """Untruncated verification digest: for every verification turn, the witness's
    bar (goal_satisfied / deed_confirmed) and its full reason, paired with the recovery
    lesson that followed a denial. This maps the SEMANTIC frontier — where an honest
    witness denies honest deeds because the confirmable bar sits many turns away — as
    distinct from the proxy-gaming frontier that --stats exposes. When failure_streak
    climbs monotonically with zero confirms, the bottleneck is HERE, not in the actor."""
    chrono = chronological(rows)
    print("=== VERDICT DIGEST (chronological) — the witness bar and why each deed was judged ===")
    for ln, obj in ((r[0], r[1]) for r in chrono):
        rt = _rtype(obj)
        data = _data(obj)
        if rt == "verification":
            # The runtime verdict (goal_satisfied/deed_confirmed/reason) is computed by
            # EXECUTING this code in node_verify and is NOT committed to the API log; the
            # committed record carries only the authored verify code + goal_interpretation.
            # The witness's own stated bar therefore lives in goal_interpretation here, and
            # the realised denial reason surfaces in the FOLLOWING recovery lesson.
            gi = str(data.get("goal_interpretation") or "").strip()
            print(f"\n[ln {ln}] VERIFY (runtime verdict not logged) — witness bar:")
            print(f"  {gi}")
        elif rt == "recovery":
            lesson = str(data.get("lesson") or "").strip()
            strat = str(data.get("strategy") or "").strip()
            print(f"\n[ln {ln}] RECOVER")
            print(f"  lesson:   {lesson}")
            print(f"  strategy: {strat}")
        elif rt == "execution":
            intent = str(data.get("intent") or "").strip()
            print(f"\n[ln {ln}] EXECUTE intent: {intent}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generic schema-agnostic endgame-ai brain-log reader")
    ap.add_argument("path", nargs="?", default=None, help="log path; omit to autodetect newest *.jsonl")
    ap.add_argument("--code", action="store_true", help="full authored code + narrative, every turn")
    ap.add_argument("--full", type=int, metavar="N", help="whole committed record for line N")
    ap.add_argument("--raw", type=int, metavar="N", help="full system+user prompt for line N")
    ap.add_argument("--field", metavar="NAME", help="one data field across all turns, untruncated")
    ap.add_argument("--grep", metavar="PATTERN", help="regex over code + narrative fields")
    ap.add_argument("--usage", action="store_true", help="token + cache + cost breakdown")
    ap.add_argument("--stats", action="store_true",
                    help="untruncated per-turn motion: signal, failure_streak trajectory, "
                         "code-effects, goal-axis, RLE + histograms (the deduction instrument)")
    ap.add_argument("--verdicts", action="store_true",
                    help="untruncated verification bar + reason paired with recovery lesson "
                         "(maps the semantic-frontier / honest-denial bottleneck)")
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
    elif args.stats:
        stats(rows)
    elif args.verdicts:
        verdicts(rows)
    else:
        summarize(rows, args.record_type)
        living_word(rows, truncate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
