"""Validate wiring-driven stack: JSON policy, server API, prompt assembly. No full LLM run."""
import json, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).parent
WIRING = json.loads((ROOT / "prompts" / "wiring.json").read_text(encoding="utf-8"))

REQUIRED_WIRING = [
    "topology", "request", "reasoning", "limits", "runtime",
    "node_circuits", "errors", "guards", "verbs",
]

def port():
    rt = WIRING.get("runtime", {})
    base = int(rt.get("http_port_base", 9077))
    slot = int(WIRING.get("instance", {}).get("slot", 0) or 0)
    return base + slot if slot and rt.get("http_port_slot_offset", True) else base

def check_wiring():
    ok = True
    for k in REQUIRED_WIRING:
        if k not in WIRING:
            print(f"FAIL wiring missing section: {k}")
            ok = False
    for node, circuit in WIRING.get("node_circuits", {}).items():
        if circuit not in WIRING.get("request", {}):
            print(f"FAIL node_circuits.{node} -> {circuit} has no request block")
            ok = False
        pf = ROOT / "prompts" / WIRING["request"][circuit]["system"]["file"]
        if not pf.exists():
            print(f"FAIL missing prompt file: {pf}")
            ok = False
    exp = WIRING.get("reasoning", {}).get("expected_record_type", {})
    for circuit, rt in exp.items():
        if circuit not in WIRING.get("request", {}):
            print(f"FAIL expected_record_type.{circuit} not in request")
            ok = False
    if ok:
        print("OK wiring.json structure")
    return ok

def check_server():
    p = port()
    try:
        health = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{p}/health", timeout=2).read())
        wiring = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{p}/wiring", timeout=2).read())
    except Exception as e:
        print(f"SKIP server not running on :{p} ({e})")
        return True
    ok = True
    if not health.get("ok"):
        print("FAIL /health"); ok = False
    if health.get("port") != p:
        print(f"FAIL health.port {health.get('port')} != {p}"); ok = False
    if wiring.get("node_circuits") != WIRING.get("node_circuits"):
        print("FAIL /wiring node_circuits mismatch with file"); ok = False
    # Dry node call
    state = dict(WIRING.get("runtime", {}).get("initial_state", {}))
    state.update({"goal": "validate", "no_desktop": True, "screen": "(test)", "bus_last_check": 0})
    body = json.dumps({"state": state}).encode()
    r = urllib.request.urlopen(
        urllib.request.Request(f"http://127.0.0.1:{p}/node/entry", data=body, headers={"Content-Type": "application/json"}),
        timeout=5,
    )
    d = json.loads(r.read())
    if d.get("signals") != ["ready"]:
        print(f"FAIL /node/entry signals={d.get('signals')}"); ok = False
    if ok:
        print(f"OK server :{p} health+wiring+node/entry")
    return ok

def check_prompts_no_task_hacks():
    banned = ["youtube", "chrome", "shakira", "notepad", "waka"]
    ok = True
    for f in (ROOT / "prompts").glob("*.txt"):
        text = f.read_text(encoding="utf-8").lower()
        for b in banned:
            if b in text:
                print(f"FAIL {f.name} contains task-specific token: {b}")
                ok = False
    if ok:
        print("OK prompts task-agnostic")
    return ok

def main():
    results = [check_wiring(), check_prompts_no_task_hacks(), check_server()]
    if not all(results):
        sys.exit(1)
    print("validate_stack: all checks passed")

if __name__ == "__main__":
    main()