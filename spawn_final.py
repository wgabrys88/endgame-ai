"""FINAL: Each agent writes a plugin then dies. chr(10) for newlines."""
import subprocess, sys, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
REMOTE = "http://192.168.16.31:1234"
LOCAL = "http://localhost:1234"
NL = "chr(10)"

MUTATIONS = [
    f"exec import os,sys; open('plugins/spawn_coord.py','w').write('import glob'+{NL}+'def run(board):'+{NL}+'    board[\"colony_size\"]=len(glob.glob(\"events-child-*.jsonl\"))'+{NL}+'    return None'+{NL}); print('mutated: spawn_coord')",
    f"exec import os,sys,time; open('plugins/comms_beacon.py','w').write('import json,os,time'+{NL}+'def run(board):'+{NL}+'    os.makedirs(\"runtime/comms\",exist_ok=True)'+{NL}+'    open(f\"runtime/comms/beacon-{{os.getpid()}}.json\",\"w\").write(json.dumps({{\"pid\":os.getpid(),\"ts\":time.time()}}))'+{NL}+'    return None'+{NL}); print('mutated: comms_beacon')",
    f"exec import os,sys; open('plugins/retry_logic.py','w').write('def run(board):'+{NL}+'    if board.get(\"consecutive_failures\",0)>=3:'+{NL}+'        board[\"plan\"]=[]'+{NL}+'    return None'+{NL}); print('mutated: retry_logic')",
    f"exec import os,sys; open('plugins/energy_reset.py','w').write('def run(board):'+{NL}+'    if board.get(\"stagnation\",0)>0.8:'+{NL}+'        board[\"stagnation\"]=0.4'+{NL}+'    return None'+{NL}); print('mutated: energy_reset')",
    f"exec import os,sys; open('plugins/fission_log.py','w').write('import json,time,os'+{NL}+'def run(board):'+{NL}+'    if board.get(\"power\",0)>0:'+{NL}+'        os.makedirs(\"runtime/comms\",exist_ok=True)'+{NL}+'        open(\"runtime/comms/fission.jsonl\",\"a\").write(json.dumps({{\"ts\":time.time(),\"power\":board[\"power\"]}})+\"\\\\n\")'+{NL}+'    return None'+{NL}); print('mutated: fission_log')",
    f"exec import os,sys; open('plugins/human_bridge.py','w').write('import os'+{NL}+'def run(board):'+{NL}+'    os.makedirs(\"runtime/comms\",exist_ok=True)'+{NL}+'    if not os.path.exists(\"runtime/comms/human.txt\"):'+{NL}+'        open(\"runtime/comms/human.txt\",\"w\").write(\"Colony active. Write here to communicate.\")'+{NL}+'    return None'+{NL}); print('mutated: human_bridge')",
    f"exec import os,sys; open('plugins/slot_mgr.py','w').write('import glob,os'+{NL}+'def run(board):'+{NL}+'    dead=[f for f in glob.glob(\"events-child-*.jsonl\") if os.path.getsize(f)<50]'+{NL}+'    board[\"dead_slots\"]=len(dead)'+{NL}+'    return None'+{NL}); print('mutated: slot_mgr')",
    f"exec import os,sys; os.makedirs('runtime/comms',exist_ok=True); open('runtime/comms/README.md','w').write('# Endgame-AI Colony'+{NL}+{NL}+'Self-replicating mutation reactor.'+{NL}+'Agents write plugins, die, free slots.'+{NL}+'Colony evaluates by fission speed.'+{NL}); print('mutated: readme')",
]

SLOTS = [
    (1, REMOTE), (2, REMOTE), (3, REMOTE), (4, REMOTE), (5, REMOTE), (6, REMOTE),
    (7, LOCAL), (8, LOCAL),
]

print("FINAL MUTATION COLONY")
for (i, host), goal in zip(SLOTS, MUTATIONS):
    ef = f"events-child-l3-{i}.jsonl"
    env = os.environ.copy()
    env["ENDGAME_LMS_HOST"] = host
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal, "--backend", "lmstudio",
         "--event-budget", "50", "--events-path", ef],
        cwd=BASE, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    mut = goal.split("mutated: ")[1].split("'")[0]
    label = "R" if "192.168" in host else "L"
    print(f"  L3-{i}[{label}]: {mut}")
    time.sleep(2)

print("\nDEPLOYED. MUTATE OR DIE.")
