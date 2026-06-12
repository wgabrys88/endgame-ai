"""Spawn 7 L3 instances focused on mutation & inter-instance communication."""
import subprocess, sys, os, time, json

BASE = os.path.dirname(os.path.abspath(__file__))
GOAL = (
    "exec import os, json, time; "
    "base='C:/Users/ewojgab/Downloads/endgame-ai'; "
    "pid=os.getpid(); "
    # 1. Read architecture
    "arch=[f for f in os.listdir(base) if f.endswith('.py')]; "
    "plugins=[f for f in os.listdir(base+'/plugins') if f.endswith('.py')]; "
    # 2. Find siblings (other running instances)
    "siblings=[f for f in os.listdir(base) if f.startswith('events-child-') and f.endswith('.jsonl')]; "
    # 3. Establish communication channel
    "chan=base+'/runtime/comms'; os.makedirs(chan, exist_ok=True); "
    "msg={'pid':pid,'ts':time.time(),'status':'alive','plugins_seen':plugins,'siblings':len(siblings)}; "
    "open(chan+f'/agent-{pid}.json','w').write(json.dumps(msg)); "
    # 4. Read other agents' messages
    "peers=[json.loads(open(chan+'/'+f).read()) for f in os.listdir(chan) if f.endswith('.json') and f!=f'agent-{pid}.json']; "
    # 5. Write README contribution
    "readme=base+'/runtime/comms/README.md'; "
    "open(readme,'a').write(f'\\n## Agent {pid}\\nPlugins: {plugins}\\nPeers: {len(peers)}\\nGoal: achieve fission via mutation\\n'); "
    "print(f'agent {pid}: arch={len(arch)} plugins={plugins} siblings={len(siblings)} peers={len(peers)} channel=OK')"
)

N_AGENTS = 7
BUDGET = 30

print(f"Spawning {N_AGENTS} L3 agents with mutation+comms goal...")
print(f"Goal: {GOAL[:120]}...")
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
    print(f"  L3-{i+1}: PID={proc.pid} events={events_file}")
    time.sleep(2)  # stagger to avoid lock contention

print(f"\nAll {N_AGENTS} spawned. PIDs: {[p[1] for p in pids]}")
print(f"Monitor with: python spawn7_monitor.py")

# Save manifest for monitor
manifest = {"spawned": time.time(), "agents": [{"id": i, "pid": pid, "events": ef} for i, pid, ef in pids]}
with open(os.path.join(BASE, "runtime", "comms", "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
