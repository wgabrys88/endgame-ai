"""Post-run analyzer for endgame-ai one-minute experiments.

Usage:
    python analyze_run.py [blackboard_events.txt]

Reads the event stream and prints efficiency metrics.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def analyze(path: Path) -> None:
    events: list[dict[str, Any]] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not events:
        print("No events found.")
        return

    phases = Counter(e.get("phase", "") for e in events)
    t_start = datetime.fromisoformat(events[0]["timestamp_utc"])
    t_end = datetime.fromisoformat(events[-1]["timestamp_utc"])
    wall = (t_end - t_start).total_seconds()
    iters = max((e.get("iteration", 0) for e in events), default=0)

    llm_reqs = [e for e in events if e.get("phase") == "llm.request"]
    role_counts = Counter(e.get("data", {}).get("role", "?") for e in llm_reqs)
    actions = [e for e in events if e.get("phase") == "action.result"]
    successes = [a for a in actions if a.get("data", {}).get("result", {}).get("success")]

    decisions = len(llm_reqs)
    state_changes = len(successes)
    efficiency = state_changes / decisions if decisions else 0

    print(f"{'='*60}")
    print(f"  endgame-ai run analysis")
    print(f"{'='*60}")
    print(f"  Wall time:        {wall:.1f}s")
    print(f"  Iterations:       {iters}")
    print(f"  Total events:     {len(events)}")
    print()
    print(f"  DECISIONS (LLM calls):  {decisions}")
    for role, count in role_counts.most_common():
        print(f"    {role}: {count}")
    print()
    print(f"  STATE CHANGES (successful actions): {state_changes}")
    for a in actions:
        r = a.get("data", {}).get("result", {})
        status = "OK" if r.get("success") else "FAIL"
        print(f"    {r.get('verb','?'):8} {status:4} | {r.get('observation','')[:60]}")
    print()
    print(f"  EFFICIENCY:")
    print(f"    Actions per decision:   {efficiency:.2f}  (1.0 = ideal)")
    print(f"    Actions per minute:     {state_changes / (wall/60):.1f}")
    print(f"    Decisions per minute:   {decisions / (wall/60):.1f}")
    print()

    continuations = phases.get("actor.continue", 0)
    idle_skips = phases.get("idle.stagnation", 0)
    print(f"  EVENT-DRIVEN SIGNALS:")
    print(f"    Actor continuations:    {continuations}  (planner skipped)")
    print(f"    Idle stagnation skips:  {idle_skips}  (no-op on unchanged screen)")
    print(f"    Checklist advances:     {phases.get('checklist.advance', 0)}")
    print(f"    Reflect skips:          {phases.get('reflect.skip', 0)}")
    print(f"    Reflector calls:        {phases.get('reflector', 0)}")
    print()

    print(f"  OUTCOME:")
    if phases.get("goal.complete", 0):
        print(f"    GOAL COMPLETE")
    elif phases.get("stop.signal", 0):
        print(f"    Stopped (stop signal)")
    elif phases.get("backend.unavailable", 0):
        print(f"    Backend unavailable")
    else:
        print(f"    Incomplete (time/stagnation)")

    verifier = phases.get("verifier", 0)
    if verifier:
        print(f"    Verifier called: {verifier}")

    windows: set[str] = set()
    for e in events:
        if e.get("phase") == "observe.rendered":
            data_val: dict[str, Any] = e.get("data", {})
            wnd_list: list[dict[str, Any]] = data_val.get("windows", [])
            for w in wnd_list:
                name = str(w.get("name", ""))
                if name and name not in ("Taskbar", "Program Manager"):
                    windows.add(name)
    if windows:
        print(f"    Windows observed: {sorted(windows)}")

    print(f"{'='*60}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("blackboard_events.txt")
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(1)
    analyze(target)
