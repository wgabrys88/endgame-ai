"""
reactor.py — Colony supervisor. Spawns and monitors rods.
Each rod = same server.py with different wiring.json (persona + slot).

Usage:
  python reactor.py                      → spawn all configured rods
  python reactor.py --goal "do thing"    → spawn rods + inject goal to comms_operator
"""
import json, subprocess, sys, time, pathlib, shutil, urllib.request, os

ROOT = pathlib.Path(__file__).parent
COLONY_DIR = ROOT / "colony"

# Colony configuration: which rods to spawn
COLONY = [
    {"slot": 1, "persona": "implementor", "port": 9077, "permissions": ["desktop_exec", "bus_post"]},
    {"slot": 2, "persona": "reviewer", "port": 9078, "permissions": ["bus_post"]},
    {"slot": 3, "persona": "comms_operator", "port": 9079, "permissions": ["bus_post", "moe_route"]},
]

def make_rod_wiring(rod_cfg):
    """Create a wiring.json for this rod (clone of base with instance overrides)."""
    base = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))
    base["instance"] = {
        "role": rod_cfg["persona"],
        "persona": rod_cfg["persona"],
        "slot": rod_cfg["slot"],
        "permissions": rod_cfg["permissions"]
    }
    # comms_operator gets MoE routing topology
    if rod_cfg["persona"] == "comms_operator":
        # Insert moe_route between entry and planner
        nodes = base["topology"]["nodes"]
        edges = base["topology"]["edges"]
        # Add moe_route node if not present
        if not any(n["id"] == "moe_route" for n in nodes):
            nodes.insert(1, {"id": "moe_route", "type": "moe_route", "label": "MoE: self or delegate"})
        # Rewire: goal_inbox → moe_route → planner (self) or → satisfied (delegated)
        edges = [e for e in edges if not (e["from"] == "goal_inbox" and e["on"] == "ready")]
        edges.insert(0, {"from": "goal_inbox", "to": "moe_route", "on": "ready"})
        edges.insert(1, {"from": "moe_route", "to": "planner", "on": "self"})
        edges.insert(2, {"from": "moe_route", "to": "satisfied", "on": "delegated"})
        base["topology"]["nodes"] = nodes
        base["topology"]["edges"] = edges
    return base

def spawn_rod(rod_cfg):
    """Spawn a rod process."""
    # Create rod directory with its own wiring
    rod_dir = COLONY_DIR / f"rod_{rod_cfg['slot']}"
    rod_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = rod_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    # Write rod-specific wiring
    wiring = make_rod_wiring(rod_cfg)
    (prompts_dir / "wiring.json").write_text(json.dumps(wiring, indent=2), encoding="utf-8")

    # Symlink/copy shared files
    for f in ["model.json", "unified.txt", "manager.txt", "schema.json", "planner.txt", "verifier.txt", "reflector.txt", "self_modify.txt"]:
        src = ROOT / "prompts" / f
        dst = prompts_dir / f
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    # Copy personalities
    pers_src = ROOT / "prompts" / "personalities"
    pers_dst = prompts_dir / "personalities"
    if pers_src.exists():
        shutil.copytree(pers_src, pers_dst, dirs_exist_ok=True)

    # Copy server files
    for f in ["server.py", "actions.py", "desktop.py"]:
        src = ROOT / f
        dst = rod_dir / f
        if src.exists():
            shutil.copy2(src, dst)

    # Spawn
    port = rod_cfg["port"]
    env = dict(os.environ)
    env["ENDGAME_BUS"] = str(ROOT / "bus.json")  # Shared bus for all rods
    log_dir = COLONY_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"rod_{rod_cfg['slot']}.log"
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server.py", str(port)],
        cwd=str(rod_dir), env=env,
        stdout=log_f, stderr=subprocess.STDOUT,
    )
    proc._log_f = log_f  # keep handle alive
    return proc

def check_health(port):
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        return json.loads(r.read())
    except:
        return None

def rod_port(slot):
    return next((c["port"] for c in COLONY if c["slot"] == slot), 9076 + int(slot))

def start_run(goal, port):
    """Start autonomous execution on a rod via POST /run."""
    body = json.dumps({"goal": goal}).encode()
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/run",
                data=body,
                headers={"Content-Type": "application/json"},
            ),
            timeout=5,
        )
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    args = sys.argv[1:]
    COLONY_DIR.mkdir(exist_ok=True)

    print(f"{'='*50}")
    print(f"  REACTOR — spawning {len(COLONY)} rods")
    print(f"{'='*50}\n")

    procs = {}
    for cfg in COLONY:
        print(f"  Spawning rod {cfg['slot']} ({cfg['persona']}) on :{cfg['port']}")
        procs[cfg["slot"]] = spawn_rod(cfg)

    time.sleep(2)

    # Health check all rods
    print("\n  Health check:")
    for cfg in COLONY:
        h = check_health(cfg["port"])
        status = f"OK (slot={h.get('slot')})" if h else "FAILED"
        print(f"    Rod {cfg['slot']} ({cfg['persona']}): {status}")

    # Start execution if goal provided — comms_operator routes, implementor executes
    if "--goal" in args:
        goal = " ".join(args[args.index("--goal")+1:])
        if goal:
            comms_port = rod_port(3)
            print(f"\n  Starting colony run via comms_operator (:{comms_port}): {goal}")
            result = start_run(goal, comms_port)
            print(f"    Result: {result}")

    # Monitor loop
    print(f"\n  Colony running. Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(5)
            for cfg in COLONY:
                proc = procs[cfg["slot"]]
                if proc.poll() is not None:
                    print(f"  [!] Rod {cfg['slot']} died (exit={proc.returncode}). Respawning...")
                    procs[cfg["slot"]] = spawn_rod(cfg)
    except KeyboardInterrupt:
        print("\n  Shutting down colony...")
        for proc in procs.values():
            proc.terminate()
        print("  Done.")
