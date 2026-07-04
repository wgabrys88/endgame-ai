"""CLI: python -m hover_cache_probe [options]

Examples:
  python -m hover_cache_probe
  python -m hover_cache_probe --step-px 48 --delay-ms 5
  python -m hover_cache_probe --point 800 400
  python -m hover_cache_probe --point 800 400 --point 200 300
"""
from __future__ import annotations

import argparse
import json
import time

from . import DEFAULT_REPORT, run_fullscreen_scan, run_point, write_report


def main() -> int:
    ap = argparse.ArgumentParser(description="Hover + UIA cache observation probe (independent module)")
    ap.add_argument("--pattern", choices=("grid", "sinusoidal"), default="grid")
    ap.add_argument("--start-delay", type=int, default=0, help="seconds before scan starts (arrange windows)")
    ap.add_argument("--step-px", type=int, default=32)
    ap.add_argument("--delay-ms", type=int, default=5, help="hover delay after SetCursorPos (tooltips/Text)")
    ap.add_argument("--max-subtree", type=int, default=200, help="max cached nodes per probe point")
    ap.add_argument("--max-total", type=int, default=2000, help="max unique nodes total")
    ap.add_argument("--max-probes", type=int, default=None, help="limit grid probes (debug)")
    ap.add_argument("--point", nargs=2, type=int, action="append", metavar=("X", "Y"), help="probe specific point(s)")
    ap.add_argument("--out", default=str(DEFAULT_REPORT))
    args = ap.parse_args()

    if args.point:
        results = {
            "mode": "points",
            "runs": [run_point(x, y, delay_ms=args.delay_ms, max_subtree_nodes=args.max_subtree) for x, y in args.point],
        }
        for i, run in enumerate(results["runs"]):
            print(f"point {args.point[i]}: {run['subtree_count']} nodes, {len(run['text_blobs'])} text blobs, {run['elapsed_s']}s")
            for tb in run["text_blobs"][:3]:
                print(f"  text[{tb['length']}] {tb['role']} {tb['name']!r}: {tb['text_full'][:120]!r}...")
    else:
        if args.start_delay > 0:
            for remaining in range(args.start_delay, 0, -1):
                print(f"starting in {remaining}s — arrange your windows...", flush=True)
                time.sleep(1)
        print(
            f"fullscreen scan pattern={args.pattern} step_px={args.step_px} delay_ms={args.delay_ms} ...",
            flush=True,
        )
        results = {
            "mode": "fullscreen",
            "run": run_fullscreen_scan(
                step_px=args.step_px,
                delay_ms=args.delay_ms,
                max_probe_points=args.max_probes,
                max_subtree_nodes_per_point=args.max_subtree,
                max_total_nodes=args.max_total,
                pattern=args.pattern,
            ),
        }
        st = results["run"]["stats"]
        print(
            f"done: {st['unique_nodes']} unique nodes, {st['nodes_with_text']} with text, "
            f"{st.get('nodes_with_text_sources', 0)} with text_sources, "
            f"{st['probes']} probes, {st['elapsed_s']}s",
            flush=True,
        )
        for tb in results["run"]["llm_preview"].get("text_blobs_top", [])[:5]:
            print(f"  text[{tb['length']}] {tb['role']} {tb['name']!r}")

    path = write_report(results, __import__("pathlib").Path(args.out))
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())