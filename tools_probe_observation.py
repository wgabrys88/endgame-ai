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


def _dump(logdir, name, obj):
    import os
    os.makedirs(logdir, exist_ok=True)
    path = os.path.join(logdir, name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    return path


def _run_pipeline(cfg, desktop, logdir):
    """Run the REAL organism observation path (core_observation.observe, including the
    resolve_clicks step) via its trace seam, logging each phase to disk. Nothing here
    reimplements the pipeline — a fix always lands in the original code, never the harness."""
    import core_observation as obs
    timing = {}
    marks = {"last": time.time()}
    written = []

    def trace(phase, payload):
        now = time.time()
        timing[phase] = round((now - marks["last"]) * 1000)
        marks["last"] = now
        if phase == "scan":
            snap = {"screen": payload["screen"], "node_count": len(payload["nodes"]), "nodes": payload["nodes"]}
        elif phase in ("filter", "resolve"):
            elim = payload.get("eliminated", {})
            tally = {}
            for reason in elim.values():
                tally[reason] = tally.get(reason, 0) + 1
            snap = {"action_element_count": len(payload["action_elements"]), "eliminated_count": len(elim), "eliminated_by_reason": dict(sorted(tally.items(), key=lambda kv: -kv[1])), "text_hints": payload["text_hints"], "action_elements": payload["action_elements"], "eliminated": elim}
        elif phase == "build":
            snap = payload
        else:
            snap = payload
        written.append(_dump(logdir, f"phase_{len(written)+1}_{phase}.json", snap))

    marks["last"] = time.time()
    result = obs.observe(desktop, cfg, trace=trace)
    timing["total"] = round((time.time() - marks["last"]) * 1000) if not timing else sum(v for k, v in timing.items() if k != "total")
    return result, timing, written


def _injection(cfg, desktop, result, logdir):
    """Reproduce the EXACT text the executor receives, by reusing the original renderers
    (bus.observation_brief / state_brief / render_* and core_wiring.prompt) — not by
    reimplementing them. This is the single log that shows precisely what the pipeline
    feeds the LLM: the observation injection as node_execute -> core_brain.think builds it."""
    import core_bus as bus
    w = wiring.load_wiring()
    # State exactly as node_observe writes it, plus a probe row as node_probe would add.
    import node_probe
    probe = node_probe.run({"wiring": w, "state": {}, "goal": ""}).patch["environment_probe"]
    state = {
        "observed_at": result.get("observed_at"),
        "desktop_tree_text": result.get("desktop_tree_text", ""),
        "action_index": result.get("action_index", {}),
        "screen_elements": result.get("screen_elements", []),
        "observation_artifact": result.get("observation_artifact", {}),
    }
    # The observation injection, verbatim, via the original function the executor path uses.
    observation = bus.observation_brief(state)
    # The full user-message tail the executor sees, assembled with the same renderers
    # core_brain.think uses (ledger + living word + standing host), so the operator sees
    # exactly what reaches the model.
    tail = "\n\n".join([
        bus.render_proven_ledger([]),
        bus.render_interpretation_table("<goal is injected here at run time>", {}),
        bus.render_environment_probe(probe),
    ])
    system_prompt = wiring.prompt(w, "node_execute")
    _dump(logdir, "injection_observation.json", observation)
    _dump(logdir, "injection_desktop_tree_text.txt", observation.get("desktop_tree_text", ""))
    _dump(logdir, "injection_user_tail.txt", tail)
    _dump(logdir, "injection_system_prompt.txt", system_prompt)
    return observation


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


def _metrics(result, phase_snaps, timing):
    """phase_snaps: {phase_name: written_path}. We read counts from the real observe()
    result and the scan snapshot rather than reimplementing anything."""
    tree = result.get("desktop_tree_text", "")
    action_index = result.get("action_index", {})
    raw = result.get("screen_elements", [])
    artifact = result.get("observation_artifact", {})
    scan_count = artifact.get("desktop_tree", {}).get("element_count")
    depths = Counter(int(e.get("depth", 0)) for e in action_index.values())
    anon = sum(1 for e in action_index.values() if not str(e.get("name", "")).strip())
    occluded = sum(1 for e in action_index.values() if e.get("occluded_by"))
    per_window = Counter(e.get("hwnd", 0) for e in action_index.values())
    numbering = _numbering(tree)
    n_actions = max(1, len(action_index))
    return {
        "scan_visible_element_count": len(raw),
        "build_element_count": len(action_index),
        "build_window_count": artifact.get("desktop_tree", {}).get("window_count", 0),
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
        "timing_ms": timing,
    }


_BARS = {
    "scan_visible_element_count": lambda v: "FAIL" if v == 0 else ("WARN" if v < 10 else "PASS"),
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


def _test_expand(cfg, desktop, result, sample_n):
    """Exercise expand() on a spread of elements and detect SILENT TRUNCATION by comparing
    the returned text against a fresh independent live re-harvest at the same point."""
    import core_observation as obs
    action_index = result.get("action_index", {})
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
    scanner = obs.UiaScanner({}, desktop)
    details, silent_trunc, ghost_children, failures = [], 0, 0, 0
    for e in picks:
        key = e.get("short_id") or e.get("id")
        try:
            res = desktop.expand([{"px": e["px"], "py": e["py"], "short_id": key}])
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


def one_run(cfg, phase, expand_samples, logdir):
    desktop = _desktop(cfg)
    result, timing, phase_logs = _run_pipeline(cfg, desktop, logdir)
    injection = _injection(cfg, desktop, result, logdir)
    metrics = _metrics(result, phase_logs, timing)
    failures, warnings = _grade(metrics)
    report = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "logdir": logdir, "metrics": metrics, "phase_logs": phase_logs}
    if phase in ("all", "expand"):
        expand_report = _test_expand(cfg, desktop, result, expand_samples)
        report["expand"] = expand_report
        _dump(logdir, "phase_expand.json", expand_report)
        if expand_report["failures"]:
            warnings.append(f"expand_failures={expand_report['failures']}")
        if expand_report["silent_truncation"]:
            failures.append(f"expand_silent_truncation={expand_report['silent_truncation']}")
        if expand_report["ghost_children"]:
            warnings.append(f"expand_ghost_children={expand_report['ghost_children']}")
    report["failures"] = failures
    report["warnings"] = warnings
    report["verdict"] = "FAIL" if failures else ("DEGRADED" if warnings else "PASS")
    _dump(logdir, "report.json", report)
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
    ap.add_argument("--logdir", default="obs_logs", help="directory for per-phase and injection logs")
    ap.add_argument("--csv", default=None, help="append one flat row per run to this CSV for trend tracking")
    ap.add_argument("--output", default=None, help="write full JSON report here (default stdout)")
    args = ap.parse_args(argv)

    cfg = _hover_cfg()
    if args.fixtures:
        _fixtures_up()
    reports = []
    try:
        for i in range(max(1, args.loops)):
            logdir = args.logdir if args.loops == 1 else f"{args.logdir}/run_{i+1}"
            report = one_run(cfg, args.phase, args.expand_samples, logdir)
            reports.append(report)
            print(json.dumps({k: report[k] for k in ("timestamp", "verdict", "logdir", "failures", "warnings", "metrics")}, ensure_ascii=False, default=str))
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
        "scan_visible_element_count": m["scan_visible_element_count"], "build_element_count": m["build_element_count"],
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
