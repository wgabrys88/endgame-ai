"""Spawn 8 agents: 6 on remote (192.168.16.31), 2 on local. Deterministic allocation."""
import subprocess, sys, os, time, json

BASE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE, "runtime", "comms"), exist_ok=True)

REMOTE = "http://192.168.16.31:1234"
LOCAL = "http://localhost:1234"

GOAL = (
    "You are an endgame-ai agent. Your workspace is C:/Users/ewojgab/Downloads/endgame-ai. "
    "Read the source files, logs, events-child-*.jsonl to understand what you are. "
    "Establish a communication channel with other agents via runtime/comms/. "
    "Write a README.md there explaining the colony. "
    "Create a human-operator agent: a Python script that opens Notepad, writes messages to the human, "
    "reads responses from the notepad file, and forwards them to the colony via the comms channel. "
    "Focus on mutations - write plugins that make the colony faster and more reliable. "
    "Read runtime/comms/infrastructure.json to learn about available hosts. "
    "Math is your friend. Fission is success. You are part of a nuclear reactor of intelligence. "
    "Read everything. Understand everything. Then improve everything."
)

# 6 remote + 2 local = 8 agents
SLOTS = [
    (1, REMOTE), (2, REMOTE), (3, REMOTE), (4, REMOTE), (5, REMOTE), (6, REMOTE),
    (7, LOCAL), (8, LOCAL),
]
BUDGET = 1000

print(f"COLONY: 6 remote + 2 local = 8 agents, budget={BUDGET}")
pids = []
for i, host in SLOTS:
    ef = f"events-child-l3-{i}.jsonl"
    env = os.environ.copy()
    env["ENDGAME_LMS_HOST"] = host
    proc = subprocess.Popen(
        [sys.executable, "main.py", GOAL, "--backend", "lmstudio",
         "--event-budget", str(BUDGET), "--events-path", ef],
        cwd=BASE, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    label = "REMOTE" if "192.168" in host else "LOCAL"
    pids.append((i, proc.pid, label))
    print(f"  L3-{i}: PID={proc.pid} [{label}]")
    time.sleep(0.5)

print(f"\nALL SPAWNED.")
manifest = {"spawned": time.time(), "agents": [{"id": i, "pid": pid, "host": lbl} for i, pid, lbl in pids]}
with open(os.path.join(BASE, "runtime", "comms", "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
