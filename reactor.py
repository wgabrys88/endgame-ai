"""Nuclear reactor. Maintains k~1.0. Spawns personality-driven agents."""
import glob, json, os, subprocess, sys, time
from urllib.parse import urlparse

import config
import log
from llm import discover_hosts

BASE = os.path.dirname(os.path.abspath(__file__))
CONTROL_INTERVAL = 10
MAX_SLOTS = config.REACTOR_SLOTS
BUDGET = 999999  # effectively unlimited

# One specialist per slot — personalities self-evolve via reflector lessons
ROSTER = {
    1: "git_expert",
    2: "implementor",
    3: "doc_inspector",
    4: "comms_operator",
    5: "quality_critic",
    6: "gui_operator",
}

slots = {}  # slot_id -> {"pid": int, "host_url": str, "personality": str}


def _host_label(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
        return "local"
    return parsed.hostname or url


def _candidate_hosts() -> list[str]:
    return list(config.LMS_CANDIDATE_HOSTS)


def _healthy_hosts() -> list[str]:
    healthy = discover_hosts(_candidate_hosts())
    return healthy if healthy else _candidate_hosts()


def _host_counts() -> dict[str, int]:
    counts = {h: 0 for h in _healthy_hosts()}
    for slot in slots.values():
        url = str(slot.get("host_url", "")).rstrip("/")
        if url in counts:
            counts[url] += 1
    return counts


def pick_host() -> str | None:
    """Pick the least-loaded host that responds to LM Studio."""
    healthy = _healthy_hosts()
    if not healthy:
        return None
    cap = int(getattr(config, "LMS_MAX_SLOTS_PER_HOST", 0))
    counts = _host_counts()
    for host in sorted(healthy, key=lambda h: counts.get(h, 0)):
        if cap <= 0 or counts.get(host, 0) < cap:
            return host
    return healthy[0]


def is_alive(slot_id):
    ef = os.path.join(BASE, f"events-child-n{slot_id}.jsonl")
    if not os.path.exists(ef):
        return False
    try:
        with open(ef, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", errors="ignore")
        for line in reversed(tail.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("phase") == "stop":
                    return False
            except:
                continue
        return True
    except:
        return True  # assume alive if we can't read


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


def spawn(slot_id, host_url):
    ef = os.path.join(BASE, f"events-child-n{slot_id}.jsonl")
    try:
        os.path.exists(ef) and os.remove(ef)
    except OSError:
        pass

    personality = ROSTER.get(slot_id)
    if personality:
        pfile = os.path.join(BASE, "prompts", "personalities", f"{personality}.txt")
        goal = open(pfile, encoding="utf-8").read().strip() if os.path.exists(pfile) else ""
    else:
        goal = ""

    env = os.environ.copy()
    host_url = host_url.rstrip("/")
    env["ENDGAME_LMS_HOST"] = host_url
    env["ENDGAME_LMS_HOSTS"] = ",".join(_candidate_hosts())
    if personality:
        env["ENDGAME_PERSONALITY"] = personality
    env["ENDGAME_SLOT"] = str(slot_id)
    proc = subprocess.Popen(
        [sys.executable, "main.py", goal, "--backend", "lmstudio",
         "--event-budget", str(BUDGET), "--events-path", ef],
        cwd=BASE, env=env,
        creationflags=0x08000000,
    )
    slots[slot_id] = {
        "pid": proc.pid,
        "host_url": host_url,
        "personality": personality or "none",
    }
    return proc.pid


def next_slot_id():
    for i in range(1, MAX_SLOTS + 1):
        if i not in slots:
            return i
    return None


def _format_host_map() -> str:
    counts: dict[str, int] = {}
    for slot in slots.values():
        label = _host_label(str(slot.get("host_url", "")))
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return "none"
    return " ".join(f"{k}={v}" for k, v in sorted(counts.items()))


if __name__ == "__main__":
    if not os.environ.get("ENDGAME_BOOTSTRAPPED"):
        log.cleanup_runtime()
    candidates = _candidate_hosts()
    healthy = discover_hosts(candidates)
    print(f"REACTOR | {MAX_SLOTS} slots | personalities")
    print(f"  LM hosts: {', '.join(candidates)}")
    print(f"  healthy: {', '.join(healthy) if healthy else 'none (will retry on demand)'}")
    for sid, p in ROSTER.items():
        print(f"  n{sid}: {p or 'none'}")
    print()

    # Bootstrap all slots
    for sid in range(1, MAX_SLOTS + 1):
        host_url = pick_host()
        if not host_url:
            break
        pid = spawn(sid, host_url)
        label = _host_label(host_url)
        p = slots[sid]["personality"]
        print(f"  BOOT n{sid} [{label}] {p} PID={pid}")
        time.sleep(2)

    print(f"\nREACTOR CRITICAL. {len(slots)} rods loaded.\n")
    while True:
        time.sleep(CONTROL_INTERVAL)
        dead = reap_dead()
        k, alive, fissions = measure_k()

        spawned = []
        for sid in dead:
            host_url = pick_host()
            if host_url:
                pid = spawn(sid, host_url)
                spawned.append(f"n{sid}[{slots[sid]['personality']}]")

        ts = time.strftime("%H:%M:%S")
        status = f"{ts} k={k:.2f} hosts={_format_host_map()} F={fissions}"
        if dead:
            status += f" reaped={[f'n{s}' for s in dead]}"
        if spawned:
            status += f" respawned={spawned}"
        print(status)