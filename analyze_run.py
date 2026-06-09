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
        print("No events.")
        return

    phases = Counter(e.get("phase", "") for e in events)
    t_start = datetime.fromisoformat(events[0]["t"])
    t_end = datetime.fromisoformat(events[-1]["t"])
    wall = (t_end - t_start).total_seconds()
    total = len(events)

    start_evt = next((e for e in events if e.get("phase") == "start"), None)
    budget = start_evt["d"]["budget"] if start_evt else total

    actions = [e for e in events if e.get("phase") == "action"]
    successes = [a for a in actions if a.get("d", {}).get("ok")]
    plans = [e for e in events if e.get("phase") == "plan"]

    print(f"{'='*50}")
    print(f"  endgame-ai run analysis")
    print(f"{'='*50}")
    print(f"  Wall time:     {wall:.1f}s")
    print(f"  Events:        {total}/{budget} ({total*100//max(budget,1)}%)")
    print(f"  Plans:         {len(plans)}")
    print(f"  Actions:       {len(actions)} ({len(successes)} ok)")
    print()

    for a in actions:
        d = a.get("d", {})
        status = "OK" if d.get("ok") else "FAIL"
        print(f"    {d.get('verb','?'):8} {status:4} {d.get('obs','')[:50]}")
    print()

    efficiency = len(successes) / max(len(plans), 1)
    print(f"  Efficiency:    {efficiency:.2f} actions/plan")
    if wall > 0:
        print(f"  Actions/min:   {len(successes)/(wall/60):.1f}")
    print()

    print(f"  Events by phase:")
    for phase, cnt in phases.most_common(10):
        print(f"    {phase:20} {cnt}")
    print()

    verifies = [e for e in events if e.get("phase") == "verify"]
    if verifies:
        confirmed = sum(1 for v in verifies if v.get("d", {}).get("verdict") == "confirmed")
        print(f"  Verifier:      {len(verifies)} calls, {confirmed} confirmed")

    outcome = "COMPLETE" if phases.get("complete") else "INCOMPLETE"
    if phases.get("halt"):
        outcome = "HALTED"
    print(f"  Outcome:       {outcome}")
    print(f"{'='*50}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("events.jsonl")
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(1)
    analyze(target)
