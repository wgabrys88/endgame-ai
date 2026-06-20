"""Colony delegation smoke — slot 2 delegates browser goal to slot 1."""
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
from colony import BUS, http_port, spawn_slot, wait_health


def main():
    BUS.write_text("[]", encoding="utf-8")
    procs = [
        spawn_slot(1, permissions="desktop_exec", simulation=True),
        spawn_slot(2, permissions="", simulation=True),
    ]
    try:
        assert wait_health(http_port(1)), "slot 1 health failed"
        assert wait_health(http_port(2)), "slot 2 health failed"

        with urllib.request.urlopen(f"http://127.0.0.1:{http_port(2)}/health", timeout=3) as r:
            h2 = json.loads(r.read())
        assert "desktop_exec" not in h2.get("permissions", []), h2

        body = json.dumps({"goal": "open chrome and search youtube"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{http_port(2)}/run",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            started = json.loads(r.read()).get("started")
        assert started, "slot 2 /run failed"

        delegated = []
        deadline = time.time() + 20
        while time.time() < deadline and not delegated:
            time.sleep(0.5)
            msgs = json.loads(BUS.read_text(encoding="utf-8")) if BUS.exists() else []
            delegated = [m for m in msgs if m.get("type") == "goal" and m.get("to_slot") == 1]
        assert delegated, f"no delegation on bus: {msgs if 'msgs' in dir() else []}"
        print(f"PASS colony_delegate bus_msgs={len(msgs)} delegated={len(delegated)}")
        return 0
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())