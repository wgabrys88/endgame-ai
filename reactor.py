"""Nuclear reactor. Maintains k~1.0. Remote PC priority (6 slots), local fallback (2 slots)."""
import glob, json, os, subprocess, sys, time, random

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 10
MAX_SLOTS = 8
REMOTE_SLOTS = 6
LOCAL_SLOTS = 2
BUDGET = 200
WINDOW = 60

REMOTE = "http://192.168.16.31:1234"
LOCAL = "http://localhost:1234"

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

# Track which host each slot uses: slot -> "remote" | "local"
slots = {}  # slot_id -> {"pid": int, "host": str, "started": float}

def count_by_host():
    r = sum(1 for s in slots.values() if s["host"] == "remote")
    l = sum(1 for s in slots.values() if s["host"] == "local")
    return r, l

def pick_host():
    """Remote priority. Fill remote first (up to 6), then local (up to 2)."""
    r, l = count_by_host()
    if r < REMOTE_SLOTS:
        return REMOTE, "remote"
    if l < LOCAL_SLOTS:
        return LOCAL, "local"
    return None, None

def is_alive(slot_id):
    ef = os.path.join(BASE, f"events-child-n{slot_id}.jsonl")
    if not os.path.exists(ef):
        return False
    try:
        events = [json.loads(l) for l in open(ef) if l.strip()]
        return not any(e.get("phase") == "stop" for e in events)
    except:
        return False

def reap_dead():
    """Remove dead slots from tracking."""
    dead = []
    for sid in list(slots):
        if not is_alive(sid):
            dead.append(sid)
            del slots[sid]
    return dead

def measure_k():
    fissions = 0
    now = time.time()
    for f in glob.glob(os.path.join(BASE, "events-child-*.jsonl")):
        try:
            events = [json.loads(l) for l in open(f) if l.strip()]
        except:
            continue
        for e in events:
            if e.get("phase") == "fission":
                fissions += 1
    alive = len(slots)
    k = fissions / max(alive, 1)
    return k, alive, fissions

def spawn(slot_id, host_url, host_label):
    ef = os.path.join(BASE, f"events-child-n{slot_id}.jsonl")
    try:
        os.path.exists(ef) and os.remove(ef)
    except OSError:
        pass
    env = os.environ.copy()
    env["ENDGAME_LMS_HOST"] = host_url
    goal = random.choice(MUTATIONS)
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal, "--backend", "lmstudio",
         "--event-budget", str(BUDGET), "--events-path", ef],
        cwd=BASE, env=env,
        creationflags=0x08000000 | 0x00000200,
    )
    slots[slot_id] = {"pid": proc.pid, "host": host_label, "started": time.time()}
    return proc.pid

def next_slot_id():
    for i in range(1, MAX_SLOTS + 1):
        if i not in slots:
            return i
    return None

if __name__ == "__main__":
    print(f"REACTOR | remote={REMOTE_SLOTS} local={LOCAL_SLOTS} budget={BUDGET}")
    print()

    # Bootstrap: fill remote first, then local
    for _ in range(MAX_SLOTS):
        host_url, host_label = pick_host()
        if not host_url:
            break
        sid = next_slot_id()
        if not sid:
            break
        pid = spawn(sid, host_url, host_label)
        r, l = count_by_host()
        print(f"  BOOT n{sid} [{host_label}] PID={pid} (R={r} L={l})")
        time.sleep(2)

    print()
    while True:
        time.sleep(CONTROL_INTERVAL)
        dead = reap_dead()
        k, alive, fissions = measure_k()
        r, l = count_by_host()
        ts = time.strftime("%H:%M:%S")

        # Refill dead slots — always remote priority
        spawned = []
        for _ in dead:
            host_url, host_label = pick_host()
            sid = next_slot_id()
            if host_url and sid:
                pid = spawn(sid, host_url, host_label)
                spawned.append(f"n{sid}[{host_label}]")

        status = f"{ts} k={k:.2f} R={r} L={l} F={fissions}"
        if dead:
            status += f" reaped={len(dead)}"
        if spawned:
            status += f" spawned={spawned}"
        print(status)
