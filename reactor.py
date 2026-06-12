"""Nuclear reactor control loop. Maintains criticality k~1.0."""
import glob, json, os, subprocess, sys, time, random

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 10
MAX_SLOTS = 8
MIN_SLOTS = 2
BUDGET = 200
WINDOW = 60

MUTATIONS = [
    "exec import os,glob; print('genome:',len(glob.glob('plugins/*.py')),'plugins')",
    "exec import os,time; os.makedirs('runtime/comms',exist_ok=True); open('runtime/comms/beacon-'+str(os.getpid())+'.json','w').write(str(time.time())); print('beacon')",
    "exec import glob; print('slots:',len(glob.glob('events-child-*.jsonl')))",
    "exec import os; open('plugins/neutron_'+str(os.getpid())+'.py','w').write('def run(board):'+chr(10)+'    return None'+chr(10)); print('mutated')",
    "exec import glob,os; evts=sum(1 for f in glob.glob('events-child-*.jsonl') for l in open(f)); print('total_events:',evts)",
    "exec import os; print('pid',os.getpid(),'alive')",
    "exec import os,json; os.makedirs('runtime/comms',exist_ok=True); open('runtime/comms/census.json','w').write(json.dumps({'ts':__import__('time').time()})); print('census')",
    "exec print('neutron')",
]

def measure_criticality():
    now = time.time()
    fissions = 0
    deaths = 0
    alive = 0
    for f in glob.glob(os.path.join(BASE, "events-child-*.jsonl")):
        try:
            events = [json.loads(l) for l in open(f) if l.strip()]
        except:
            continue
        stopped = any(e.get("phase") == "stop" for e in events)
        if stopped:
            deaths += 1
        else:
            alive += 1
        for e in events:
            if e.get("phase") == "fission":
                fissions += 1
    absorbed = max(deaths, 1)
    k = (fissions + alive * 0.1) / absorbed if absorbed else float(alive)
    return k, alive, fissions, deaths

def free_slot():
    used = set()
    for f in glob.glob(os.path.join(BASE, "events-child-*.jsonl")):
        try:
            events = [json.loads(l) for l in open(f) if l.strip()]
        except:
            continue
        stopped = any(e.get("phase") == "stop" for e in events)
        if not stopped:
            name = os.path.basename(f).replace("events-child-", "").replace(".jsonl", "")
            used.add(name)
    for i in range(1, MAX_SLOTS + 1):
        if f"n{i}" not in used:
            return i
    return None

def spawn_neutron(slot):
    ef = os.path.join(BASE, f"events-child-n{slot}.jsonl")
    try:
        os.path.exists(ef) and os.remove(ef)
    except OSError:
        pass
    env = os.environ.copy()
    goal = random.choice(MUTATIONS)
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal, "--backend", "lmstudio",
         "--event-budget", str(BUDGET), "--events-path", ef],
        cwd=BASE, env=env,
        creationflags=0x08000000 | 0x00000200,
    )
    return proc.pid, goal.split("print('")[1].split("')")[0] if "print('" in goal else "?"

def absorb():
    weakest = None
    worst = float("inf")
    for f in glob.glob(os.path.join(BASE, "events-child-*.jsonl")):
        try:
            events = [json.loads(l) for l in open(f) if l.strip()]
        except:
            continue
        if any(e.get("phase") == "stop" for e in events):
            continue
        fissions = len([e for e in events if e.get("phase") == "fission"])
        if fissions < worst:
            worst = fissions
            weakest = f
    return weakest

if __name__ == "__main__":
    print(f"REACTOR ONLINE | slots={MAX_SLOTS} budget={BUDGET}")

    # Bootstrap
    for i in range(1, MIN_SLOTS + 1):
        pid, what = spawn_neutron(i)
        print(f"  BOOT n{i}: PID={pid} [{what}]")
        time.sleep(2)

    while True:
        time.sleep(CONTROL_INTERVAL)
        k, alive, fissions, deaths = measure_criticality()
        ts = time.strftime("%H:%M:%S")

        if k < 0.95 and alive < MAX_SLOTS:
            slot = free_slot()
            if slot:
                pid, what = spawn_neutron(slot)
                print(f"{ts} k={k:.2f} alive={alive} SUBCRITICAL -> spawn n{slot} [{what}]")
            else:
                print(f"{ts} k={k:.2f} alive={alive} SUBCRITICAL no slots")
        elif k > 1.5 and alive > MIN_SLOTS:
            target = absorb()
            print(f"{ts} k={k:.2f} alive={alive} SUPERCRITICAL -> absorb")
        else:
            print(f"{ts} k={k:.2f} alive={alive} F={fissions} D={deaths} stable")
