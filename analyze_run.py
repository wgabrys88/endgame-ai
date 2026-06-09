from __future__ import annotations
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def analyze(events_path: Path, snapshot_path: Path | None = None) -> None:
    events: list[dict[str, Any]] = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not events:
        print("No events.")
        return

    phases = Counter(e.get("phase", "") for e in events)
    t_start = datetime.fromisoformat(events[0]["t"])
    t_end = datetime.fromisoformat(events[-1]["t"])
    wall = (t_end - t_start).total_seconds()
    total = len(events)

    start_evt = next((e for e in events if e.get("phase") == "start"), None)
    budget = start_evt["d"]["budget"] if start_evt else total
    goal = start_evt["d"]["goal"] if start_evt else "?"

    actions = [e for e in events if e.get("phase") == "action"]
    successes = [a for a in actions if a.get("d", {}).get("ok")]
    plans = [e for e in events if e.get("phase") == "plan"]
    verifies = [e for e in events if e.get("phase") == "verify"]
    reflects = [e for e in events if e.get("phase") == "reflect"]
    observes = [e for e in events if e.get("phase") == "observe"]
    lorenz_forks = [e for e in events if e.get("phase") == "lorenz.fork"]

    outcome = "COMPLETE" if phases.get("complete") else "INCOMPLETE"
    if phases.get("halt"):
        outcome = "HALTED"

    print(f"{'═' * 60}")
    print(f"  endgame-ai post-execution analysis")
    print(f"{'═' * 60}")
    print(f"  Goal:          {goal}")
    print(f"  Outcome:       {outcome}")
    print(f"  Wall time:     {wall:.1f}s")
    print(f"  Events:        {total}/{budget} ({total * 100 // max(budget, 1)}% budget used)")
    print()

    print(f"{'─' * 60}")
    print(f"  PIPELINE METRICS")
    print(f"{'─' * 60}")
    print(f"  Plans:         {len(plans)}")
    print(f"  Actions:       {len(actions)} ({len(successes)} ok, {len(actions) - len(successes)} fail)")
    print(f"  Observes:      {len(observes)}")
    print(f"  Verifies:      {len(verifies)} ({sum(1 for v in verifies if v.get('d', {}).get('verdict') == 'confirmed')} confirmed)")
    print(f"  Reflects:      {len(reflects)}")
    print(f"  Lorenz forks:  {len(lorenz_forks)}")
    print()

    if plans:
        modes = Counter(e.get("d", {}).get("mode", "") for e in plans)
        print(f"  Plan modes:    {dict(modes)}")
    efficiency = len(successes) / max(len(plans), 1)
    print(f"  Efficiency:    {efficiency:.2f} successful actions per plan")
    if wall > 0:
        print(f"  Throughput:    {len(successes) / (wall / 60):.1f} actions/min")
    print()

    print(f"{'─' * 60}")
    print(f"  ACTION TRACE")
    print(f"{'─' * 60}")
    for a in actions:
        d = a.get("d", {})
        status = "✓" if d.get("ok") else "✗"
        print(f"    [{a.get('n', '?'):3}] {status} {d.get('verb', '?'):8} {d.get('obs', '')[:45]}")
    print()

    print(f"{'─' * 60}")
    print(f"  TIMING ANALYSIS")
    print(f"{'─' * 60}")
    phase_times: dict[str, float] = {}
    for i in range(1, len(events)):
        prev_t = datetime.fromisoformat(events[i - 1]["t"])
        curr_t = datetime.fromisoformat(events[i]["t"])
        delta = (curr_t - prev_t).total_seconds()
        phase = events[i].get("phase", "?")
        phase_times[phase] = phase_times.get(phase, 0.0) + delta
    for phase, t in sorted(phase_times.items(), key=lambda x: -x[1])[:8]:
        pct = t / max(wall, 0.01) * 100
        print(f"    {phase:14} {t:6.1f}s ({pct:4.1f}%)")
    print()

    llm_events = [e for e in events if e.get("phase") in ("plan", "actor", "verify", "reflect")]
    if llm_events and wall > 0:
        llm_time = sum(phase_times.get(p, 0.0) for p in ("plan", "actor", "verify", "reflect"))
        action_time = phase_times.get("action", 0.0)
        observe_time = phase_times.get("observe", 0.0)
        print(f"  Time split:    LLM={llm_time:.1f}s ({llm_time/wall*100:.0f}%) "
              f"Actions={action_time:.1f}s ({action_time/wall*100:.0f}%) "
              f"Observe={observe_time:.1f}s ({observe_time/wall*100:.0f}%)")
    print()

    snap: dict[str, Any] | None = None
    if snapshot_path and snapshot_path.exists():
        snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    elif (events_path.parent / "snapshot.json").exists():
        snap = json.loads((events_path.parent / "snapshot.json").read_text(encoding="utf-8"))

    if snap:
        print(f"{'─' * 60}")
        print(f"  MATH STATE (end of run)")
        print(f"{'─' * 60}")
        print(f"  Stagnation:    {snap.get('stagnation_score', 0):.3f}")
        print(f"  Lorenz X:      {snap.get('lorenz_x', 0):.3f}")
        print(f"  Lorenz Y:      {snap.get('lorenz_y', 0):.3f}")
        print(f"  Lorenz Z:      {snap.get('lorenz_z', 0):.3f}")
        print(f"  PID output:    {snap.get('pid_output', 0):.3f}")
        print(f"  PID integral:  {snap.get('pid_integral', 0):.3f}")
        jac = snap.get("jacobian", {})
        if jac:
            print(f"  Jacobian:      {jac}")
        print()

    if reflects:
        print(f"{'─' * 60}")
        print(f"  REFLECTIONS")
        print(f"{'─' * 60}")
        for r in reflects:
            rd = r.get("d", {})
            print(f"    [{r.get('n', '?')}] {rd.get('diagnosis', '')[:70]}")
            print(f"        → {rd.get('lesson', '')[:70]}")
        print()

    print(f"{'═' * 60}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("events.jsonl")
    snap_p = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(1)
    analyze(target, snap_p)
