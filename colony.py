"""Colony manager — spawn N endgame-ai slots sharing bus.json (stdlib only)."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent
MAIN_WIRING_PATH = ROOT / "prompts" / "wiring.json"
RELAY_WIRING_PATH = ROOT / "prompts" / "wiring_relay.json"
WIRING = json.loads(MAIN_WIRING_PATH.read_text(encoding="utf-8"))
BUS = pathlib.Path(os.environ.get("ENDGAME_BUS", str(ROOT / "bus.json")))


def read_wiring(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def slot_wiring_path(slot: int) -> pathlib.Path:
    if slot == 2 and RELAY_WIRING_PATH.exists():
        return RELAY_WIRING_PATH
    return MAIN_WIRING_PATH


def slot_permissions(slot: int, slots: list[int]) -> str:
    if slot == 2 and RELAY_WIRING_PATH.exists():
        return "desktop_exec"
    return "desktop_exec" if slot == min(slots) else ""


def http_port(slot: int) -> int:
    rt = WIRING.get("runtime", {})
    base = int(rt.get("http_port_base", 9077))
    if slot and rt.get("http_port_slot_offset", True):
        return base + int(slot)
    return base


def wait_health(port: int, timeout: float = 20.0) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if json.loads(r.read()).get("ok"):
                    return True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.5)
    return False


def spawn_slot(slot: int, permissions: str | None = None, wiring_path: pathlib.Path | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["ENDGAME_SLOT"] = str(slot)
    env["ENDGAME_STATE"] = str(ROOT / f"state.slot{slot}.json")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if wiring_path is not None:
        env["ENDGAME_WIRING"] = str(wiring_path)
    if permissions is not None:
        env["ENDGAME_PERMISSIONS"] = permissions
    return subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        cwd=str(ROOT),
        env=env,
    )


def post_goal(port: int, goal: str) -> bool:
    body = json.dumps({"goal": goal}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/run",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()).get("started", False)
    except urllib.error.URLError:
        return False


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    slots = [int(a) for a in argv if a.isdigit()] or [1, 2]

    atomic_write_text(BUS, "[]")
    procs: list[tuple[int, subprocess.Popen]] = []

    print(f"endgame-ai colony starting slots {slots}")
    for slot in slots:
        perms = slot_permissions(slot, slots)
        wiring_path = slot_wiring_path(slot)
        proc = spawn_slot(slot, permissions=perms, wiring_path=wiring_path)
        procs.append((slot, proc))
        port = http_port(slot)
        print(f"  slot {slot} pid={proc.pid} port={port} perms={perms or '(delegate)'} wiring={wiring_path.name}")
        if not wait_health(port):
            print(f"  [!] slot {slot} health timeout on :{port}")
        else:
            print(f"  [ok] http://127.0.0.1:{port}/health")
            auto_goal = read_wiring(wiring_path).get("runtime", {}).get("auto_start_goal", "")
            if auto_goal:
                started = post_goal(port, auto_goal)
                print(f"  [{'ok' if started else '!!'}] auto-start goal: {auto_goal[:80]}")

    print("\nColony running. Ctrl+C to stop.")
    print("Post goal to slot 1:", f"http://127.0.0.1:{http_port(slots[0])}/")
    try:
        while True:
            alive = [(s, p) for s, p in procs if p.poll() is None]
            if not alive:
                print("All slots exited.")
                break
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping colony...")
        for _, proc in procs:
            proc.terminate()
        for _, proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
