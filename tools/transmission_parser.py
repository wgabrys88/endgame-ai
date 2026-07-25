#!/usr/bin/env python3
"""
transmission_parser.py - reusable forensic parser for endgame-ai .transmissions/*.json

Each transmission file is one model turn with this shape:
  at            float epoch seconds
  turn          int
  record_type   execution | verification | recovery
  api           e.g. "responses"
  request.body.input   the full assembled prompt (str)
  request.body.model / temperature / reasoning
  raw_response  raw model text (str)
  extracted_content    the model reply JSON string: {record_type, data{...}}
  error         null or error info

This parser is NOT a core organism file; it is free to use pip deps (pandas).
Goal: produce the most complete, untruncated forensic view for multi-agent,
multi-session evaluation - not grep-style snippets.

Usage:
  python tools/transmission_parser.py [--dir DIR] [--full] [--csv OUT.csv]
                                      [--turn N] [--grep REGEX]
"""
import argparse
import json
import re
import sys
from pathlib import Path

# capability calls we want to detect inside returned code (the real signal of
# self-evolution / node graph / spawn / web behaviour)
CAP_PATTERNS = {
    "commit_section": re.compile(r"\bcommit_section\s*\("),
    "save_node": re.compile(r"\bsave_node\s*\("),
    "call_node": re.compile(r"\bcall_node\s*\("),
    "suggest_next": re.compile(r"\bsuggest_next\s*\("),
    "spawn_actor": re.compile(r"\bspawn_actor\s*\("),
    "web_search": re.compile(r"\bweb_search\s*\("),
    "ask_model": re.compile(r"\bask_model\s*\("),
    "desktop.": re.compile(r"\bdesktop\.\w+\s*\("),
    "open_url": re.compile(r"\bopen_url\s*\("),
}

TURN_RE = re.compile(r"turn-(\d+)-([a-z]+)-(\d+)\.json$")


def iter_files(d: Path):
    files = sorted(d.glob("turn-*.json"))
    return files


def parse_file(fp: Path) -> dict:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    rec = {
        "file": fp.name,
        "turn": raw.get("turn"),
        "at": raw.get("at"),
        "record_type": raw.get("record_type"),
        "api": raw.get("api"),
        "model": raw.get("request", {}).get("body", {}).get("model"),
        "temperature": raw.get("request", {}).get("body", {}).get("temperature"),
        "reasoning": raw.get("request", {}).get("body", {}).get("reasoning"),
        "error": raw.get("error"),
        "prompt_len": len(raw.get("request", {}).get("body", {}).get("input", "") or ""),
        "raw_response_len": len(raw.get("raw_response", "") or ""),
    }
    # parse the model reply
    ec = raw.get("extracted_content") or ""
    rec["extracted_len"] = len(ec)
    data = {}
    rec["reply_parse_ok"] = False
    try:
        j = json.loads(ec)
        rec["reply_parse_ok"] = True
        rec["reply_record_type"] = j.get("record_type")
        data = j.get("data", {}) or {}
    except Exception as e:
        rec["reply_parse_error"] = str(e)

    code = data.get("code", "") or ""
    rec["code_len"] = len(code)
    rec["code"] = code
    rec["goal_interpretation"] = data.get("goal_interpretation", "")
    rec["developer_feedback"] = data.get("developer_feedback", "")
    # verification/recovery specific
    rec["intent"] = data.get("intent", "")
    rec["perceived"] = data.get("perceived", "")
    rec["alternatives"] = data.get("alternatives", "")
    rec["lesson"] = data.get("lesson", "")
    rec["strategy"] = data.get("strategy", "")
    rec["target"] = data.get("target", "")
    # capability calls detected inside the returned code
    caps = {}
    for name, pat in CAP_PATTERNS.items():
        n = len(pat.findall(code))
        if n:
            caps[name] = n
    rec["caps"] = caps
    # verdict/signal often set in code by verify (look for common markers)
    for key in ("verdict", "signal"):
        m = re.search(key + r"\s*=\s*['\"]([a-z_]+)['\"]", code)
        rec[key] = m.group(1) if m else ""
    return rec


def build_frame(records):
    try:
        import pandas as pd
    except ImportError:
        return None
    rows = []
    for r in records:
        rows.append({
            "turn": r["turn"],
            "at": r["at"],
            "type": r["record_type"],
            "reply_ok": r["reply_parse_ok"],
            "code_len": r["code_len"],
            "verdict": r.get("verdict", ""),
            "signal": r.get("signal", ""),
            "dev_feedback": (r["developer_feedback"] or "")[:60],
            "caps": ",".join("%s:%d" % (k, v) for k, v in r["caps"].items()),
            "error": bool(r["error"]),
        })
    return pd.DataFrame(rows)


def summarize(records):
    from collections import Counter
    print("=" * 78)
    print("TRANSMISSION FORENSIC SUMMARY  (%d turns)" % len(records))
    print("=" * 78)
    t0 = min(r["at"] for r in records)
    t1 = max(r["at"] for r in records)
    span = t1 - t0
    print("first at: %.3f  last at: %.3f  span: %.1fs (%.1f min)" % (t0, t1, span, span / 60))
    types = Counter(r["record_type"] for r in records)
    print("record types:", dict(types))
    errs = [r for r in records if r["error"]]
    print("turns with error:", len(errs), [r["turn"] for r in errs][:20])
    bad = [r for r in records if not r["reply_parse_ok"]]
    print("turns with unparseable reply:", len(bad), [r["turn"] for r in bad][:20])

    print("\n--- CAPABILITY CALLS in returned code (real self-evolution signal) ---")
    total = Counter()
    per_cap_turns = {}
    for r in records:
        for k, v in r["caps"].items():
            total[k] += v
            per_cap_turns.setdefault(k, []).append(r["turn"])
    for k, v in total.most_common():
        print("  %-16s %4d calls   turns: %s" % (k, v, per_cap_turns[k][:30]))

    print("\n--- developer_feedback (declared body defects) ---")
    fb = [r for r in records if (r["developer_feedback"] or "").strip()]
    print("turns with non-empty developer_feedback:", len(fb))
    for r in fb:
        print("  turn %s [%s]: %s" % (r["turn"], r["record_type"], (r["developer_feedback"] or "").replace("\n", " ")[:200]))

    print("\n--- inter-turn gaps (top 10 slowest) ---")
    srt = sorted(records, key=lambda r: r["at"])
    gaps = []
    for a, b in zip(srt, srt[1:]):
        gaps.append((b["at"] - a["at"], a["turn"], b["turn"], b["record_type"]))
    for g, ta, tb, tt in sorted(gaps, reverse=True)[:10]:
        print("  %6.1fs  turn %s -> %s (%s)" % (g, ta, tb, tt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent / ".transmissions"))
    ap.add_argument("--full", action="store_true", help="dump full code/narrative per turn")
    ap.add_argument("--turn", type=int, default=None)
    ap.add_argument("--grep", default=None, help="regex over code+narrative; print matching turns")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--narrative", action="store_true", help="print goal_interpretation per turn (living word)")
    args = ap.parse_args()

    d = Path(args.dir)
    files = iter_files(d)
    if not files:
        print("no transmission files in", d, file=sys.stderr)
        sys.exit(1)
    records = [parse_file(f) for f in files]

    if args.turn is not None:
        r = next((x for x in records if x["turn"] == args.turn), None)
        if not r:
            print("no such turn", args.turn); sys.exit(1)
        print(json.dumps({k: v for k, v in r.items() if k != "code"}, indent=2, default=str))
        print("\n===== CODE =====\n" + r["code"])
        return

    if args.grep:
        pat = re.compile(args.grep, re.I)
        for r in records:
            hay = (r["code"] or "") + "\n" + (r["goal_interpretation"] or "") + "\n" + (r["developer_feedback"] or "")
            if pat.search(hay):
                print("turn %s [%s] matches" % (r["turn"], r["record_type"]))
        return

    if args.narrative:
        for r in records:
            gi = (r["goal_interpretation"] or "").replace("\n", " ")
            print("turn %3s [%-12s] %s" % (r["turn"], r["record_type"], gi[:220]))
        return

    summarize(records)

    if args.csv:
        df = build_frame(records)
        if df is not None:
            df.to_csv(args.csv, index=False)
            print("\nwrote", args.csv)
        else:
            print("\npandas not installed; skipped csv (pip install pandas)")

    if args.full:
        for r in records:
            print("\n" + "#" * 78)
            print("TURN %s [%s] at=%s caps=%s" % (r["turn"], r["record_type"], r["at"], r["caps"]))
            print("- goal_interpretation:", (r["goal_interpretation"] or "")[:500])
            if (r["developer_feedback"] or "").strip():
                print("- developer_feedback:", r["developer_feedback"])
            print("- CODE:\n" + (r["code"] or ""))


if __name__ == "__main__":
    main()
