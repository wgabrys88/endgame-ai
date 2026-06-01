from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from event_schema import create_event

BB_PATH = Path(__file__).parent / "blackboard_state.json"
POLL_INTERVAL = 0.5
children: dict[str, subprocess.Popen[bytes]] = {}


def locked_read() -> dict[str, Any]:
    import msvcrt
    with open(BB_PATH, "r") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        data: dict[str, Any] = json.load(f)
    return data


def locked_write(data: dict[str, Any]) -> None:
    import msvcrt
    with open(BB_PATH, "w") as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        json.dump(data, f, indent=2)


def handle_post_event(evt: dict[str, Any], state: dict[str, Any]) -> None:
    state["events"].append(evt["payload"])
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)


def handle_read_events(evt: dict[str, Any], state: dict[str, Any]) -> None:
    evt["status"] = "done"
    print(json.dumps(state["events"], indent=2))


def handle_cleanup(evt: dict[str, Any], state: dict[str, Any]) -> None:
    state["events"] = [e for e in state["events"] if e.get("status") != "done"]
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)


def handle_spawn_child(evt: dict[str, Any], state: dict[str, Any]) -> None:
    cmd: str = evt["payload"].get("command", "")
    name: str = evt["payload"].get("name", cmd)
    p = subprocess.Popen(cmd, shell=True)
    children[name] = p
    state["agents"][name] = {"pid": p.pid, "started": datetime.now(timezone.utc).isoformat()}
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)


def handle_stop_child(evt: dict[str, Any], state: dict[str, Any]) -> None:
    name: str = evt["payload"].get("name", "")
    if name in children:
        children[name].terminate()
        del children[name]
        state["agents"].pop(name, None)
    evt["status"] = "done"
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    locked_write(state)


DISPATCH: dict[str, Any] = {
    "post_event": handle_post_event,
    "read_events": handle_read_events,
    "cleanup": handle_cleanup,
    "spawn_child": handle_spawn_child,
    "stop_child": handle_stop_child,
}


def poll() -> None:
    print("Controller polling...")
    while True:
        state = locked_read()
        for evt in state["events"]:
            if evt.get("status") == "pending" and evt.get("verb") in DISPATCH:
                DISPATCH[evt["verb"]](evt, state)
        time.sleep(POLL_INTERVAL)


def cli() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("verb")
    ap.add_argument("--source", default="cli")
    ap.add_argument("--target", default="controller")
    ap.add_argument("--payload", default="{}")
    args = ap.parse_args()
    evt: dict[str, Any] = create_event(args.verb, args.source, args.target, json.loads(args.payload))
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
