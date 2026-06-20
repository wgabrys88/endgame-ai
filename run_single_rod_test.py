"""Single-rod test: start server --run, poll state, kill after timeout."""
import json, pathlib, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).parent
GOAL = sys.argv[1] if len(sys.argv) > 1 else "open notepad and write hello"
TIMEOUT = int(sys.argv[2]) if len(sys.argv) > 2 else 300

def rod_port():
    wiring = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    slot = wiring.get("instance", {}).get("slot", 0)
    return 9077 + int(slot) if slot else 9077

def fetch_state():
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{rod_port()}/state", timeout=2)
        return json.loads(r.read())
    except Exception:
        return None

proc = subprocess.Popen(
    [sys.executable, "-u", "server.py", "--run", GOAL],
    cwd=str(ROOT),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
print(f"PID={proc.pid} goal={GOAL!r} timeout={TIMEOUT}s")
start = time.time()
last_step = -1
while time.time() - start < TIMEOUT:
    if proc.poll() is not None:
        break
    st = fetch_state()
    if st:
        step = st.get("step", 0)
        node = st.get("_resume_node", "?")
        if step != last_step:
            print(f"  t={int(time.time()-start)}s step={step} node={node} retries={st.get('retries',0)}")
            last_step = step
        if st.get("satisfied"):
            print("SATISFIED")
            break
    time.sleep(5)

if proc.poll() is None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

out = proc.stdout.read() if proc.stdout else ""
(ROOT / "single_rod_run.log").write_text(out, encoding="utf-8")
st = fetch_state() or {}
report = {
    "goal": GOAL,
    "satisfied": st.get("satisfied"),
    "step": st.get("step"),
    "plan_len": len(st.get("plan", [])),
    "last_error": st.get("last_error"),
    "history": st.get("history", [])[-5:],
    "resume_node": st.get("_resume_node"),
}
(ROOT / "single_rod_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))