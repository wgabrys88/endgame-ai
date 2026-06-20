"""Run colony test for 2 minutes, capture logs, then kill."""
import json, os, pathlib, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).parent
LOG = ROOT / "colony_run.log"
GOAL = "open chrome and play shakira waka waka on youtube"

def fetch(port, path):
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    if LOG.exists():
        LOG.unlink()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", "reactor.py", "--goal", GOAL],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    lines = []
    start = time.time()
    print(f"Started reactor PID={proc.pid}, waiting 120s...")
    while time.time() - start < 120:
        line = proc.stdout.readline()
        if line:
            lines.append(line.rstrip())
            print(line, end="")
        elif proc.poll() is not None:
            break
        time.sleep(0.1)
    print("\n=== KILLING ===")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    # drain
    rest = proc.stdout.read()
    if rest:
        lines.extend(rest.splitlines())
    LOG.write_text("\n".join(lines), encoding="utf-8")

    report = {"goal": GOAL, "duration_s": 120, "reactor_log_lines": len(lines)}
    for port, slot in [(9077, 1), (9078, 2), (9079, 3)]:
        report[f"rod_{slot}_health"] = fetch(port, "/health")
        report[f"rod_{slot}_state"] = fetch(port, "/state")
    report["bus"] = json.loads((ROOT / "bus.json").read_text()) if (ROOT / "bus.json").exists() else []
    for slot in [1, 2, 3]:
        sf = ROOT / "colony" / f"rod_{slot}" / "state.json"
        report[f"rod_{slot}_state_file"] = json.loads(sf.read_text()) if sf.exists() else None
        lf = ROOT / "colony" / "logs" / f"rod_{slot}.log"
        if lf.exists():
            report[f"rod_{slot}_log_tail"] = lf.read_text(encoding="utf-8", errors="replace")[-4000:]
    (ROOT / "colony_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()