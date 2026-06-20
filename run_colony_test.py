"""Run colony test for 2 minutes, capture logs, then kill."""
import json, os, pathlib, subprocess, sys, threading, time, urllib.request

ROOT = pathlib.Path(__file__).parent
LOG = ROOT / "colony_run.log"
ANALYSIS = ROOT / "colony_analysis.json"
GOAL = "open chrome and play shakira waka waka on youtube"
WAIT_S = int(os.environ.get("COLONY_TEST_SECS", "120"))


def fetch(port, path):
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def build_report(lines):
    report = {"goal": GOAL, "duration_s": WAIT_S, "reactor_log_lines": len(lines), "reactor_log": lines[-30:]}
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
    return report


def kill_tree(pid):
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )


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
    reader_done = threading.Event()

    def _read_stdout():
        try:
            for line in proc.stdout:
                lines.append(line.rstrip())
                print(line, end="")
        finally:
            reader_done.set()

    print(f"Started reactor PID={proc.pid}, waiting {WAIT_S}s...")
    threading.Thread(target=_read_stdout, daemon=True).start()
    time.sleep(WAIT_S)
    print("\n=== KILLING ===")
    kill_tree(proc.pid)
    reader_done.wait(timeout=5)
    try:
        proc.stdout.close()
    except Exception:
        pass
    LOG.write_text("\n".join(lines), encoding="utf-8")
    report = build_report(lines)
    ANALYSIS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    step = (report.get("rod_1_state_file") or {}).get("step")
    satisfied = (report.get("rod_1_state_file") or {}).get("satisfied")
    print(json.dumps({"step": step, "satisfied": satisfied, "analysis": str(ANALYSIS)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())