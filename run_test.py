"""Run one five-slot endgame-ai colony test with timeout, kill, report.

Usage: python run_test.py [seconds] [backend]
"""
import json, os, subprocess, sys, time
from pathlib import Path

BASE = Path(__file__).parent.resolve()
SLOTS = 5
BUDGET = 80
ROSTER = {1: "comms_operator", 2: "architect", 3: "implementor", 4: "reviewer", 5: "devops"}


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    backend = sys.argv[2] if len(sys.argv) > 2 else "lmstudio"

    subprocess.run([sys.executable, "-c", "import log; log.cleanup_runtime()"], cwd=str(BASE), capture_output=True)
    (BASE / "runtime" / "comms").mkdir(parents=True, exist_ok=True)
    for name, content in [("messages.json", "[]\n"), ("events_bus.jsonl", ""), ("inject.jsonl", "")]:
        (BASE / "runtime" / "comms" / name).write_text(content, encoding="utf-8")
    (BASE / "pause").write_text("", encoding="utf-8")

    print(f"=== endgame-ai colony test: {SLOTS} agents, {seconds}s, backend={backend} ===")
    procs = []
    for slot, personality in ROSTER.items():
        ef = f"events-child-s{slot}.jsonl"
        pfile = BASE / "prompts" / "personalities" / f"{personality}.txt"
        goal = pfile.read_text(encoding="utf-8").strip() if pfile.exists() else ""
        env = os.environ.copy()
        env.update({"ENDGAME_LMS_HOST": "http://localhost:1234", "ENDGAME_LMS_HOSTS": "http://localhost:1234",
                    "ENDGAME_PERSONALITY": personality, "ENDGAME_SLOT": str(slot)})
        proc = subprocess.Popen([sys.executable, "main.py", goal, "--backend", backend, "--event-budget", str(BUDGET), "--events-path", ef],
                                cwd=str(BASE), env=env, creationflags=0x08000000)
        procs.append((slot, personality, proc))
        print(f"  s{slot} [{personality}] PID={proc.pid}")

    time.sleep(3)
    (BASE / "pause").unlink(missing_ok=True)
    print(f"  LIVE — {seconds}s...")
    start = time.time()
    try:
        while time.time() - start < seconds:
            alive = sum(1 for _, _, p in procs if p.poll() is None)
            if alive == 0:
                break
            time.sleep(10)
            print(f"  T+{int(time.time()-start)}s — {alive}/{SLOTS} alive")
    except KeyboardInterrupt:
        pass

    for slot, personality, proc in procs:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    (BASE / "pause").write_text("", encoding="utf-8")

    print(f"\n{'='*50}\nRESULTS\n{'='*50}")
    for slot, personality, _ in procs:
        ef = BASE / f"events-child-s{slot}.jsonl"
        if not ef.exists():
            print(f"  s{slot} [{personality}]: no events")
            continue
        lines = [l for l in ef.read_text(encoding="utf-8").splitlines() if l.strip()]
        fissions = sum(1 for l in lines if '"phase":"fission"' in l)
        errors = sum(1 for l in lines if '.error' in l)
        print(f"  s{slot} [{personality}]: {len(lines)} events, {fissions} fissions, {errors} errors")

    bus = BASE / "runtime" / "comms" / "messages.json"
    if bus.exists():
        msgs = json.loads(bus.read_text(encoding="utf-8"))
        if msgs:
            print(f"\n  Bus: {len(msgs)} messages")
            for m in msgs[-5:]:
                print(f"    @{m.get('from','?')}: {str(m.get('text',''))[:80]}")
    print()


if __name__ == "__main__":
    main()
