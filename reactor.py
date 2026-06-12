"""Nuclear reactor. Maintains k~1.0. Spawns personality-driven agents."""
import glob, json, os, subprocess, sys, time, random

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 10
MAX_SLOTS = 8
REMOTE_SLOTS = 6
LOCAL_SLOTS = 2
BUDGET = 999999  # effectively unlimited
REMOTE = "http://192.168.16.31:1234"
LOCAL = "http://localhost:1234"

# Personality assignment: slot -> personality file
# 2 git experts, 2 doc inspectors, 1 implementor, 1 comms, 1 critic, 1 wild
ROSTER = {
    1: "git_expert",
    2: "git_expert",
    3: "doc_inspector",
    4: "doc_inspector",
    5: "implementor",
    6: "comms_operator",
    7: "quality_critic",
    8: None,  # wild — empty goal, pure planner personality
}

slots = {}  # slot_id -> {"pid": int, "host": str, "personality": str}

def count_by_host():
    r = sum(1 for s in slots.values() if s["host"] == "remote")
    l = sum(1 for s in slots.values() if s["host"] == "local")
    return r, l

def pick_host():
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
    dead = []
    for sid in list(slots):
        if not is_alive(sid):
            dead.append(sid)
            del slots[sid]
    return dead

def measure_k():
    fissions = 0
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

    personality = ROSTER.get(slot_id)
    if personality:
        # Load personality as the goal — planner uses it to generate plans
        pfile = os.path.join(BASE, "prompts", "personalities", f"{personality}.txt")
        goal = open(pfile).readline().strip() if os.path.exists(pfile) else ""
    else:
        goal = ""  # wild agent — pure planner personality drives it

    env = os.environ.copy()
    env["ENDGAME_LMS_HOST"] = host_url
    if personality:
        env["ENDGAME_PERSONALITY"] = personality
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal, "--backend", "lmstudio",
         "--event-budget", str(BUDGET), "--events-path", ef],
        cwd=BASE, env=env,
        creationflags=0x08000000,
    )
    slots[slot_id] = {"pid": proc.pid, "host": host_label, "personality": personality or "wild"}
    return proc.pid

def next_slot_id():
    for i in range(1, MAX_SLOTS + 1):
        if i not in slots:
            return i
    return None

if __name__ == "__main__":
    print(f"REACTOR | {MAX_SLOTS} slots | personalities")
    for sid, p in ROSTER.items():
        print(f"  n{sid}: {p or 'wild'}")
    print()

    # Bootstrap all slots
    for sid in range(1, MAX_SLOTS + 1):
        host_url, host_label = pick_host()
        if not host_url:
            break
        pid = spawn(sid, host_url, host_label)
        r, l = count_by_host()
        p = slots[sid]["personality"]
        print(f"  BOOT n{sid} [{host_label}] {p} PID={pid}")
        time.sleep(2)

    print(f"\nREACTOR CRITICAL. {len(slots)} rods loaded.\n")
    while True:
        time.sleep(CONTROL_INTERVAL)
        dead = reap_dead()
        k, alive, fissions = measure_k()
        r, l = count_by_host()

        # Refill dead slots with same personality
        spawned = []
        for sid in dead:
            host_url, host_label = pick_host()
            if host_url:
                pid = spawn(sid, host_url, host_label)
                spawned.append(f"n{sid}[{slots[sid]['personality']}]")

        ts = time.strftime("%H:%M:%S")
        status = f"{ts} k={k:.2f} R={r} L={l} F={fissions}"
        if dead:
            status += f" reaped={[f'n{s}' for s in dead]}"
        if spawned:
            status += f" respawned={spawned}"
        print(status)
