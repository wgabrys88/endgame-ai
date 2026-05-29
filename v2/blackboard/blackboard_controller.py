import json, time, os, sys, subprocess, signal
from pathlib import Path
from datetime import datetime, timezone
from event_schema import create_event, validate_event

BB_PATH = Path(__file__).parent / "blackboard_state.json"
POLL_INTERVAL = 0.5
children = {}

def locked_read():
    import msvcrt
    with open(BB_PATH, "r") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        data = json.load(f)
    return data

def locked_write(data):
    import msvcrt
    with open(BB_PATH, "w") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        json.dump(data, f, indent=2)

def handle_post_event(evt, state):
    state["events"].append(evt["payload"])
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)

def handle_read_events(evt, state):
    evt["status"] = "done"
    print(json.dumps(state["events"], indent=2))

def handle_cleanup(evt, state):
    state["events"] = [e for e in state["events"] if e.get("status") != "done"]
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)

def handle_spawn_child(evt, state):
    cmd = evt["payload"].get("command", "")
    name = evt["payload"].get("name", cmd)
    p = subprocess.Popen(cmd, shell=True)
    children[name] = p
    state["agents"][name] = {"pid": p.pid, "started": datetime.now(timezone.utc).isoformat()}
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)

def handle_stop_child(evt, state):
    name = evt["payload"].get("name", "")
    if name in children:
        children[name].terminate()
        del children[name]
        state["agents"].pop(name, None)
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)

DISPATCH = {"post_event": handle_post_event, "read_events": handle_read_events, "cleanup": handle_cleanup, "spawn_child": handle_spawn_child, "stop_child": handle_stop_child}

def poll():
    print("Controller polling...")
    while True:
        state = locked_read()
        for evt in state["events"]:
            if evt.get("status") == "pending" and evt.get("verb") in DISPATCH:
                DISPATCH[evt["verb"]](evt, state)
        time.sleep(POLL_INTERVAL)

def cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("verb")
    ap.add_argument("--source", default="cli")
    ap.add_argument("--target", default="controller")
    ap.add_argument("--payload", default="{}")
    args = ap.parse_args()
    evt = create_event(args.verb, args.source, args.target, json.loads(args.payload))
    state = locked_read()
    state["events"].append(evt)
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)
    print(f"Posted: {evt['id']}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--poll":
        cli()
    else:
        poll()
