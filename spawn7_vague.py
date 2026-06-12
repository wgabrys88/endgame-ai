"""Spawn 7 L3 agents with vague emergent goal. Budget 1000. Remote PC priority."""
import subprocess, sys, os, time, json

BASE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE, "runtime", "comms"), exist_ok=True)

GOAL = (
    "You are an endgame-ai agent. Your workspace is C:/Users/ewojgab/Downloads/endgame-ai. "
    "Read the source files, logs, events-child-*.jsonl to understand what you are. "
    "Establish a communication channel with other agents via runtime/comms/. "
    "Write a README.md there explaining the colony. "
    "Create a human-operator agent: a Python script that opens Notepad, writes messages to the human, "
    "reads responses from the notepad file, and forwards them to the colony via the comms channel. "
    "Focus on mutations - write plugins that make the colony faster and more reliable. "
    "Math is your friend. Fission is success. You are part of a nuclear reactor of intelligence. "
    "Read everything. Understand everything. Then improve everything."
)

N_AGENTS = 7
BUDGET = 1000

print(f"LAUNCHING COLONY: {N_AGENTS} agents, budget={BUDGET}")
print(f"Goal: {GOAL[:100]}...")
print()

pids = []
for i in range(N_AGENTS):
    events_file = f"events-child-l3-{i+1}.jsonl"
    proc = subprocess.Popen(
        [sys.executable, "main.py", GOAL, "--backend", "lmstudio",
         "--event-budget", str(BUDGET), "--events-path", events_file],
        cwd=BASE,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    pids.append((i+1, proc.pid, events_file))
    print(f"  L3-{i+1}: PID={proc.pid}")
    time.sleep(1)

print(f"\nCOLONY ACTIVE. Monitor: python spawn7_monitor.py --watch")
manifest = {"spawned": time.time(), "agents": [{"id": i, "pid": pid, "events": ef} for i, pid, ef in pids]}
with open(os.path.join(BASE, "runtime", "comms", "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
