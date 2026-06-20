"""Live LLM tests — skips gracefully if endpoint unreachable."""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent
MODEL = json.loads((ROOT / "prompts" / "model.json").read_text(encoding="utf-8"))


def llm_reachable():
    url = MODEL["host"].rstrip("/") + "/v1/models"
    try:
        urllib.request.urlopen(url, timeout=5)
        return True
    except Exception:
        try:
            body = json.dumps({
                "model": MODEL.get("model", "local-model"),
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 8,
            }).encode()
            req = urllib.request.Request(
                MODEL["host"].rstrip("/") + "/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=min(30, MODEL.get("timeout", 30)))
            return True
        except Exception:
            return False


def test_planner_json():
    import server

    goal = "open notepad and type hello"
    state = server.fresh_state(goal)
    state["no_desktop"] = True
    state["screen"] = "(live test — no desktop)"
    r = server.NODES["planner"](state, {})
    state.update(r.get("patch", {}))
    assert r["signals"] == ["plan_ready"], {"signals": r["signals"], "error": state.get("last_error")}
    steps = state.get("plan", [])
    assert steps and isinstance(steps, list)
    assert all("description" in s and "done_when" in s for s in steps)
    print(f"PASS live_planner ({len(steps)} steps)")
    return True


def test_live_act_json():
    import server

    state = server.fresh_state("open notepad")
    state.update({
        "no_desktop": True,
        "step_goal": "open notepad",
        "current_step": {"description": "open notepad", "done_when": "Notepad is open"},
        "screen": "FOCUSED: Desktop\n  [1] Button \"Start\"",
        "history": [],
    })
    r = server.NODES["act"](state, {})
    state.update(r.get("patch", {}))
    assert r["signals"] in (["acted"], ["act_failed"]), {
        "signals": r["signals"],
        "error": state.get("last_error"),
        "parsed": state.get("last_outcome"),
    }
    if r["signals"] == ["acted"]:
        assert "OK:" in state.get("last_outcome", "") or "FAILED" in state.get("last_outcome", "")
    print(f"PASS live_act ({r['signals'][0]})")
    return True


def test_live_sim_rod():
    """Full ROD loop with real LLM + SimDesktop (bounded cycles)."""
    import actions
    import server

    prev_sim = os.environ.get("ENDGAME_SIM")
    state_backup = server.STATE_FILE.read_text(encoding="utf-8") if server.STATE_FILE.exists() else None
    os.environ["ENDGAME_SIM"] = "1"
    actions._desktop = None
    actions._executor = None

    orig_delay = server.WIRING["runtime"].get("cycle_delay_ms", 300)
    orig_cycles = server.WIRING["limits"].get("max_cycles", 300)
    server.WIRING["runtime"]["cycle_delay_ms"] = 0
    server.WIRING["limits"]["max_cycles"] = 40

    try:
        state = server.run("open notepad and type hi")
        assert state.get("step", 0) >= 1 or state.get("satisfied"), state
        print(
            f"PASS live_sim_rod step={state.get('step')} "
            f"satisfied={state.get('satisfied')} history={len(state.get('history', []))}"
        )
        return True
    finally:
        server.WIRING["runtime"]["cycle_delay_ms"] = orig_delay
        server.WIRING["limits"]["max_cycles"] = orig_cycles
        actions._desktop = None
        actions._executor = None
        if prev_sim is None:
            os.environ.pop("ENDGAME_SIM", None)
        else:
            os.environ["ENDGAME_SIM"] = prev_sim
        if state_backup is None:
            if server.STATE_FILE.exists():
                server.STATE_FILE.unlink()
        else:
            server.STATE_FILE.write_text(state_backup, encoding="utf-8")


TESTS = [
    ("live_planner", test_planner_json),
    ("live_act", test_live_act_json),
    ("live_sim_rod", test_live_sim_rod),
]


if __name__ == "__main__":
    if not llm_reachable():
        print("SKIP live LLM tests — endpoint unreachable:", MODEL.get("host"))
        raise SystemExit(0)
    print("Live LLM endpoint OK:", MODEL.get("host"))
    passed = 0
    for name, fn in TESTS:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
    print(f"\n{passed}/{len(TESTS)} live tests passed")
    raise SystemExit(0 if passed == len(TESTS) else 1)