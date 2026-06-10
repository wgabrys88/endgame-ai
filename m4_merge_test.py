"""M4 merge gate — run after a posterity validation session.

Usage:
  python m4_merge_test.py
  python m4_merge_test.py path/to/events.jsonl path/to/events-child.jsonl

Pass criteria (merge refactor-v4 -> main):
  1. At least two reactor boots (phase:start) across logs, OR child events-*.jsonl
  2. Parent log shows self-edit (config.py or prompts/ in exec/write_file obs)
  3. pause file existed during run OR parent spawn + pause_reactor in exec schedule
  4. m4_posterity_ok.json exists with matching proof field
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from config import BASE_DIR, EVENTS_PATH, PAUSE_PATH


def _load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _all_event_files() -> list[Path]:
    paths = [EVENTS_PATH, *sorted(BASE_DIR.glob("events-*.jsonl"))]
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        rp = p.resolve()
        if rp not in seen and p.exists():
            seen.add(rp)
            out.append(p)
    return out


def _check(files: list[Path]) -> tuple[bool, list[str]]:
    ok_lines: list[str] = []
    fail_lines: list[str] = []
    all_events: list[dict] = []
    for f in files:
        ev = _load_events(f)
        all_events.extend(ev)
        ok_lines.append(f"  read {f.name}: {len(ev)} events")

    starts = [e for e in all_events if e.get("phase") == "start"]
    if len(starts) >= 2:
        ok_lines.append(f"  reactor boots: {len(starts)} phase:start")
    elif len(files) >= 2 and any(len(_load_events(f)) > 0 for f in files[1:]):
        ok_lines.append("  posterity log present (events-*.jsonl)")
    else:
        fail_lines.append("  need 2+ phase:start OR separate child events file")

    edited = False
    spawned = False
    paused = False
    for e in all_events:
        if e.get("phase") != "actor":
            continue
        d = e.get("d", {})
        obs = str(d.get("obs", ""))
        verb = str(d.get("verb", ""))
        if verb in ("exec", "write_file") and (
            "config.py" in obs or "prompts/" in obs or "planner.txt" in obs
        ):
            if any(x in obs.lower() for x in ("updated", "wrote", "->", "appended", "evolved")):
                edited = True
        if "spawn_main" in obs or (verb == "exec" and "spawn" in obs.lower() and "pid" in obs.lower()):
            spawned = True
    for e in all_events:
        step = str(e.get("d", {}).get("step", ""))
        if "spawn_main" in step or "pause_reactor" in step:
            if "spawn_main" in step:
                spawned = True
            if "pause_reactor" in step:
                paused = True

    if edited:
        ok_lines.append("  self-edit detected in log")
    else:
        fail_lines.append("  no config/prompt self-edit in log")

    if spawned:
        ok_lines.append("  spawn_main / posterity launch detected")
    else:
        fail_lines.append("  no child spawn detected")

    if paused or PAUSE_PATH.exists():
        ok_lines.append("  parent pause detected")
    else:
        fail_lines.append("  parent did not pause (pause file / pause_reactor)")

    posterity = BASE_DIR / "m4_posterity_ok.json"
    if posterity.exists():
        try:
            data = json.loads(posterity.read_text(encoding="utf-8"))
            ok_lines.append(f"  m4_posterity_ok.json: {data}")
            if not data.get("ok"):
                fail_lines.append("  posterity json ok!=true")
            if "screen_element_value_limit" not in data:
                fail_lines.append("  posterity json missing screen_element_value_limit")
        except json.JSONDecodeError as exc:
            fail_lines.append(f"  invalid m4_posterity_ok.json: {exc}")
    else:
        fail_lines.append("  m4_posterity_ok.json missing")

    passed = len(fail_lines) == 0
    report = ["M4 merge gate:", *ok_lines]
    if fail_lines:
        report.append("FAIL:")
        report.extend(fail_lines)
    else:
        report.append("PASS — safe to merge refactor-v4 -> main")
    return passed, report


def main() -> None:
    if len(sys.argv) > 1:
        files = [Path(a) for a in sys.argv[1:]]
    else:
        files = _all_event_files()
    if not files:
        print("No events logs found.", file=sys.stderr)
        sys.exit(2)
    passed, lines = _check(files)
    print("\n".join(lines))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()