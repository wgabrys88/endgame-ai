"""Run 2 endgame-ai agents for a limited time, then kill and report.

Usage: python run_test.py [seconds] [backend]
  seconds: how long to run (default 60)
  backend: lmstudio or acp (default lmstudio)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.resolve()
SLOTS = 2
DEFAULT_SECONDS = 60
BUDGET = 50

def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SECONDS
    backend = sys.argv[2] if len(sys.argv) > 2 else "lmstudio"

    # Clean runtime
    subprocess.run([sys.executable, "-c", "import log; log.cleanup_runtime(kill_reactor=False)"],
                   cwd=str(BASE), capture_output=True)

    # Ensure runtime/comms exists
    (BASE / "runtime" / "comms").mkdir(parents=True, exist_ok=True)
    for name, content in [("messages.json", "[]\n"), ("events_bus.jsonl", ""), ("inject.jsonl", "")]:
        (BASE / "runtime" / "comms" / name).write_text(content, encoding="utf-8")

    # Create pause file (start paused)
    (BASE / "pause").write_text("", encoding="utf-8")

    print(f"=== endgame-ai test run: {SLOTS} agents, {seconds}s, backend={backend} ===")
    print(f"Budget per agent: {BUDGET} events")
    print()

    # Spawn agents
    procs = []
    for slot in range(1, SLOTS + 1):
        roster = {1: "git_expert", 2: "implementor"}
        personality = roster.get(slot, "")
        ef = f"events-child-n{slot}.jsonl"
        pfile = BASE / "prompts" / "personalities" / f"{personality}.txt"
        goal = pfile.read_text(encoding="utf-8").strip() if pfile.exists() else ""

        env = os.environ.copy()
        env["ENDGAME_LMS_HOST"] = "http://localhost:1234"
        env["ENDGAME_LMS_HOSTS"] = "http://localhost:1234"
        env["ENDGAME_PERSONALITY"] = personality
        env["ENDGAME_SLOT"] = str(slot)

        proc = subprocess.Popen(
            [sys.executable, "main.py", goal, "--backend", backend,
             "--event-budget", str(BUDGET), "--events-path", ef],
            cwd=str(BASE), env=env,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        procs.append((slot, personality, proc))
        print(f"  Spawned n{slot} [{personality}] PID={proc.pid}")

    # Unpause after 2s (let math settle)
    time.sleep(2)
    (BASE / "pause").unlink(missing_ok=True)
    print(f"\n  LIVE — running for {seconds}s...")

    # Wait with countdown
    start = time.time()
    try:
        while time.time() - start < seconds:
            alive = sum(1 for _, _, p in procs if p.poll() is None)
            if alive == 0:
                print("  All agents finished naturally.")
                break
            time.sleep(5)
            elapsed = int(time.time() - start)
            print(f"  T+{elapsed}s — {alive}/{SLOTS} alive")
    except KeyboardInterrupt:
        print("\n  Ctrl+C — stopping early")

    # Kill remaining
    for slot, personality, proc in procs:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print(f"  Killed n{slot} [{personality}]")

    # Pause again
    (BASE / "pause").write_text("", encoding="utf-8")

    # Report
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    for slot in range(1, SLOTS + 1):
        ef = BASE / f"events-child-n{slot}.jsonl"
        if not ef.exists():
            print(f"\n  n{slot}: no events file")
            continue
        lines = [l for l in ef.read_text(encoding="utf-8").splitlines() if l.strip()]
        phases = {}
        fissions = 0
        errors = []
        for line in lines:
            try:
                e = json.loads(line)
                p = e.get("phase", "?")
                phases[p] = phases.get(p, 0) + 1
                if p == "fission":
                    fissions += 1
                if "error" in p:
                    d = e.get("d", {})
                    errors.append(f"{p}: {str(d.get('error', d))[:80]}")
            except json.JSONDecodeError:
                pass
        print(f"\n  n{slot} [{roster.get(slot, '?')}]: {len(lines)} events, {fissions} fissions")
        top = sorted(phases.items(), key=lambda x: -x[1])[:8]
        print(f"    Phases: {', '.join(f'{k}={v}' for k, v in top)}")
        if errors:
            print(f"    Errors ({len(errors)}):")
            for err in errors[-5:]:
                print(f"      {err}")

    # Show bus
    bus = BASE / "runtime" / "comms" / "messages.json"
    if bus.exists():
        msgs = json.loads(bus.read_text(encoding="utf-8"))
        if msgs:
            print(f"\n  Bus messages: {len(msgs)}")
            for m in msgs[-5:]:
                print(f"    @{m.get('from')}: {str(m.get('text', ''))[:80]}")

    print(f"\n{'='*60}")
    print("Done. Event files preserved for analysis.")


if __name__ == "__main__":
    main()
