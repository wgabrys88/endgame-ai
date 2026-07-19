"""tools_probe_observation — a standalone harness to loop-test the 3-phase observation
mechanism (scan -> filter -> build) and expand(), driving them toward output that is
neither empty nor bloated and whose hierarchical numbering the model can trust.

NOT a core file: it may pip-install deps (pandas optional) since it is an instrument,
not part of the organism's body. Windows-only (comtypes/uiautomation); run via
powershell.exe. It never mutates any project file — read-only observer + metrics.

Usage (from Windows):
  python tools_probe_observation.py                 # one end-to-end run, JSON verdict to stdout
  python tools_probe_observation.py --fixtures      # launch Notepad+Calc+Explorer first
  python tools_probe_observation.py --loops 5 --delay 3 --csv obs_trend.csv
  python tools_probe_observation.py --phase scan    # isolate one phase
  python tools_probe_observation.py --expand-samples 12
"""
import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter

import core_wiring as wiring


def _hover_cfg():
    w = wiring.load_wiring()
    return w["observe_config"]["hover_cache"]


def _desktop(cfg):
    import core_desktop
    return core_desktop.get_desktop({"hover_cache": cfg})


def _run_phases(cfg, desktop):
    """Invoke each phase in isolation, timing every one, returning the raw stage outputs."""
    import obs_scan, obs_filter, obs_build
    t0 = time.time()
    scanned = obs_scan.run(cfg, desktop)
    t1 = time.time()
    filtered = obs_filter.run(scanned["nodes"], cfg, scanned["screen"])
    t2 = time.time()
    built = obs_build.run(filtered["action_elements"], filtered["text_hints"], scanned["nodes"], filtered["hwnd_to_z"], scanned["screen"], cfg)
    t3 = time.time()
    return {
        "scanned": scanned, "filtered": filtered, "built": built,
        "timing_ms": {"scan": round((t1 - t0) * 1000), "filter": round((t2 - t1) * 1000), "build": round((t3 - t2) * 1000), "total": round((t3 - t0) * 1000)},
    }


def _numbering(tree_text):
    """Parse e-numbers from the rendered tree; report count, max, gaps, duplicates."""
    nums = [int(m) for m in re.findall(r"\be(\d+)\b", tree_text)]
    if not nums:
        return {"count": 0, "max": 0, "gaps": [], "duplicates": []}
    counts = Counter(nums)
    expected = set(range(1, max(nums) + 1))
    return {
        "count": len(nums),
        "max": max(nums),
        "gaps": sorted(expected - set(nums)),
        "duplicates": sorted(n for n, c in counts.items() if c > 1),
    }


def _metrics(stages):
    scanned, filtered, built = stages["scanned"], stages["filtered"], stages["built"]
    tree = built["desktop_tree_text"]
    action_index = built["action_index"]
    raw = scanned["nodes"]
    depths = Counter(int(n.get("depth", 0)) for n in raw if not n.get("offscreen"))
    anon = sum(1 for e in action_index.values() if not str(e.get("name", "")).strip())
    occluded = sum(1 for e in action_index.values() if e.get("occluded_by"))
    per_window = Counter(e.get("hwnd", 0) for e in action_index.values())
    numbering = _numbering(tree)
    n_actions = max(1, len(action_index))
    return {
        "scan_node_count": len(raw),
        "filter_element_count": len(filtered["action_elements"]),
        "build_element_count": built["element_count"],
        "build_window_count": built["window_count"],
        "tree_line_count": tree.count("\n") + 1,
        "tree_char_total": len(tree),
        "per_window_max": max(per_window.values()) if per_window else 0,
        "numbering_count": numbering["count"],
        "numbering_max": numbering["max"],
        "numbering_gaps": numbering["gaps"],
        "numbering_duplicates": numbering["duplicates"],
        "anonymous_ratio": round(anon / n_actions, 3),
        "occluded_ratio": round(occluded / n_actions, 3),
        "max_depth_observed": max(depths) if depths else 0,
        "depth_distribution": dict(sorted(depths.items())),
        "action_distribution": dict(Counter(e.get("action", "") for e in action_index.values())),
        "timing_ms": stages["timing_ms"],
    }


_BARS = {
    "scan_node_count": lambda v: "FAIL" if v == 0 else ("WARN" if v < 10 or v > 10000 else "PASS"),
    "build_element_count": lambda v: "FAIL" if v == 0 else ("WARN" if v < 5 or v > 480 else "PASS"),
    "build_window_count": lambda v: "FAIL" if v == 0 else "PASS",
    "tree_line_count": lambda v: "FAIL" if v <= 1 else ("WARN" if v == 2 else "PASS"),
    "tree_char_total": lambda v: "FAIL" if v < 200 or v > 80000 else ("WARN" if v > 60000 else "PASS"),
    "anonymous_ratio": lambda v: "FAIL" if v > 0.30 else ("WARN" if v > 0.15 else "PASS"),
    "occluded_ratio": lambda v: "FAIL" if v > 0.25 else ("WARN" if v > 0.10 else "PASS"),
    "max_depth_observed": lambda v: "WARN" if v == 0 else "PASS",
}


def _grade(metrics):
    failures, warnings = [], []
    for key, bar in _BARS.items():
        verdict = bar(metrics[key])
        if verdict == "FAIL":
            failures.append(f"{key}={metrics[key]}")
        elif verdict == "WARN":
            warnings.append(f"{key}={metrics[key]}")
    if metrics["numbering_gaps"]:
        failures.append(f"numbering_gaps={metrics['numbering_gaps']}")
    if metrics["numbering_duplicates"]:
        failures.append(f"numbering_duplicates={metrics['numbering_duplicates']}")
    if metrics["numbering_count"] != metrics["build_element_count"]:
        warnings.append(f"numbering_count({metrics['numbering_count']}) != build_element_count({metrics['build_element_count']})")
    return failures, warnings


def _test_expand(cfg, desktop, stages, sample_n):
    """Exercise expand() on a spread of elements and detect SILENT TRUNCATION by comparing
    the returned text against a fresh independent live re-harvest at the same point."""
    import core_observation as obs
    action_index = stages["built"]["action_index"]
    elems = list(action_index.values())
    writes = [e for e in elems if e.get("action") == "write"]
    deep = sorted([e for e in elems if int(e.get("depth", 0)) > 1], key=lambda e: -int(e.get("depth", 0)))
    focused = [e for e in elems if e.get("focused")]
    picks, seen = [], set()
    for e in focused + writes + deep + elems:
        key = e.get("short_id") or e.get("id")
        if key not in seen and e.get("px") is not None:
            seen.add(key)
            picks.append(e)
        if len(picks) >= sample_n:
            break
    budget = int(cfg["budget"]["expand_char_budget"])
    scanner = obs.UiaScanner({}, desktop)
    details, silent_trunc, ghost_children, failures = [], 0, 0, 0
    for e in picks:
        key = e.get("short_id") or e.get("id")
        try:
            res = desktop.expand([{"px": e["px"], "py": e["py"], "short_id": key}], char_budget=budget)
        except Exception as exc:
            failures += 1
            details.append({"short_id": key, "error": str(exc)[:200]})
            continue
        r = res.get(key, {})
        returned = len(r.get("text_full", "") or "") + sum(len(c.get("text", "") or "") for c in r.get("children", []))
        ghosts = sum(1 for c in r.get("children", []) if not str(c.get("role", "")).strip() and not str(c.get("name", "")).strip() and not str(c.get("text", "")).strip())
        ghost_children += ghosts
        try:
            from ctypes import wintypes
            pt = wintypes.POINT(int(e["px"]), int(e["py"]))
            root_el = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache())
            live = scanner.harvest_subtree(root_el)
            live_chars = sum(len(n.get("text_full", "") or "") for n in live)
        except Exception:
            live_chars = -1
        truncated = live_chars > 0 and returned < live_chars * 0.95
        if truncated:
            silent_trunc += 1
        details.append({"short_id": key, "chars_returned": returned, "chars_live": live_chars, "children": len(r.get("children", [])), "truncated": truncated, "ghost_children": ghosts})
    return {
        "samples": len(picks),
        "failures": failures,
        "silent_truncation": silent_trunc,
        "ghost_children": ghost_children,
        "details": details,
    }


def _fixtures_up():
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", "Start-Process notepad.exe; Start-Sleep -Milliseconds 500; Start-Process calc.exe; Start-Sleep -Milliseconds 500; Start-Process explorer.exe 'C:\\'; Start-Sleep -Seconds 3"], check=False)


def _fixtures_down():
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", "Stop-Process -Name notepad,calc -Force -ErrorAction SilentlyContinue"], check=False)


def one_run(cfg, phase, expand_samples):
    desktop = _desktop(cfg)
    stages = _run_phases(cfg, desktop)
    metrics = _metrics(stages)
    failures, warnings = _grade(metrics)
    report = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "metrics": metrics}
    if phase in ("all", "expand"):
        expand_report = _test_expand(cfg, desktop, stages, expand_samples)
        report["expand"] = expand_report
        if expand_report["failures"]:
            warnings.append(f"expand_failures={expand_report['failures']}")
        if expand_report["silent_truncation"]:
            failures.append(f"expand_silent_truncation={expand_report['silent_truncation']}")
        if expand_report["ghost_children"]:
            warnings.append(f"expand_ghost_children={expand_report['ghost_children']}")
    report["failures"] = failures
    report["warnings"] = warnings
    report["verdict"] = "FAIL" if failures else ("DEGRADED" if warnings else "PASS")
    return report


def main(argv=None):
    if sys.platform != "win32":
        print(json.dumps({"error": "observation is Windows-only; run this via powershell.exe"}))
        return 3
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", action="store_true", help="launch Notepad+Calc+Explorer before probing")
    ap.add_argument("--no-cleanup", action="store_true", help="leave fixture windows open after")
    ap.add_argument("--phase", choices=["scan", "filter", "build", "expand", "all"], default="all")
    ap.add_argument("--expand-samples", type=int, default=10)
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--csv", default=None, help="append one flat row per run to this CSV for trend tracking")
    ap.add_argument("--output", default=None, help="write full JSON report here (default stdout)")
    args = ap.parse_args(argv)

    cfg = _hover_cfg()
    if args.fixtures:
        _fixtures_up()
    reports = []
    try:
        for i in range(max(1, args.loops)):
            report = one_run(cfg, args.phase, args.expand_samples)
            reports.append(report)
            print(json.dumps(report, ensure_ascii=False, default=str))
            if args.csv:
                _append_csv(args.csv, report)
            if i + 1 < args.loops:
                time.sleep(args.delay)
    finally:
        if args.fixtures and not args.no_cleanup:
            _fixtures_down()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(reports if len(reports) > 1 else reports[0], f, ensure_ascii=False, indent=2, default=str)

    verdicts = [r["verdict"] for r in reports]
    if "FAIL" in verdicts:
        return 2
    if "DEGRADED" in verdicts:
        return 1
    return 0


def _append_csv(path, report):
    import csv
    import os
    m = report["metrics"]
    row = {
        "timestamp": report["timestamp"], "verdict": report["verdict"],
        "scan_node_count": m["scan_node_count"], "build_element_count": m["build_element_count"],
        "build_window_count": m["build_window_count"], "tree_line_count": m["tree_line_count"],
        "tree_char_total": m["tree_char_total"], "anonymous_ratio": m["anonymous_ratio"],
        "occluded_ratio": m["occluded_ratio"], "max_depth_observed": m["max_depth_observed"],
        "numbering_gaps": len(m["numbering_gaps"]), "numbering_duplicates": len(m["numbering_duplicates"]),
        "total_ms": m["timing_ms"]["total"],
        "expand_silent_truncation": report.get("expand", {}).get("silent_truncation", ""),
    }
    exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
