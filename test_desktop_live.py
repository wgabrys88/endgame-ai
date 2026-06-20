"""Live ROD on real Windows UIA + local LLM. Skips if desktop or LLM unavailable."""
import json
import os
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).parent


def llm_reachable():
    model = json.loads((ROOT / "prompts" / "model.json").read_text(encoding="utf-8"))
    try:
        body = json.dumps({
            "model": model.get("model", "local-model"),
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 4,
        }).encode()
        req = urllib.request.Request(
            model["host"].rstrip("/") + "/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception:
        return False


def desktop_available():
    try:
        from desktop import Desktop
        obs = Desktop().observe()
        return bool(obs.context_text and len(obs.context_text) > 20)
    except Exception as e:
        print(f"desktop unavailable: {e}")
        return False


def _reset_actions():
    import actions
    actions._desktop = None
    actions._executor = None


def cold_start_prep():
    """Dismiss dialogs and surface desktop for cold-start goals."""
    import actions
    import server
    _reset_actions()
    trace_file = server.TRACES_FILE
    if trace_file.exists():
        trace_file.write_text("", encoding="utf-8")
    for _ in range(2):
        actions.execute_verb("press", "escape", "")
        time.sleep(0.15)
    actions.execute_verb("hotkey", "win+d", "")
    time.sleep(0.4)
    screen = actions.observe_screen()
    print(f"  cold_start: {screen[:180].replace(chr(10), ' | ')}")


def _run_bounded(goal: str, max_cycles: int = 60):
    import server

    state_backup = server.STATE_FILE.read_text(encoding="utf-8") if server.STATE_FILE.exists() else None
    orig_delay = server.WIRING["runtime"].get("cycle_delay_ms", 300)
    orig_cycles = server.WIRING["limits"].get("max_cycles", 300)
    server.WIRING["runtime"]["cycle_delay_ms"] = 100
    server.WIRING["limits"]["max_cycles"] = max_cycles
    try:
        return server.run(goal, max_cycles=max_cycles)
    finally:
        server.WIRING["runtime"]["cycle_delay_ms"] = orig_delay
        server.WIRING["limits"]["max_cycles"] = orig_cycles
        _reset_actions()
        if state_backup is None:
            if server.STATE_FILE.exists():
                server.STATE_FILE.unlink()
        else:
            server.STATE_FILE.write_text(state_backup, encoding="utf-8")


def test_live_desktop_single_step():
    cold_start_prep()
    state = _run_bounded("open notepad", max_cycles=55)
    assert state.get("history"), state
    ok = state.get("satisfied") or state.get("step", 0) >= 1
    if not ok and "notepad" in (state.get("screen") or "").lower():
        ok = state.get("step", 0) >= 1
    assert ok, state
    print(
        f"PASS live_desktop_single step={state.get('step')} "
        f"satisfied={state.get('satisfied')} history={len(state.get('history', []))}"
    )
    if state.get("last_outcome"):
        print(f"  last_outcome: {state['last_outcome'][:140]}")
    return True


def test_live_desktop_two_step():
    cold_start_prep()
    state = _run_bounded("open notepad and type hello", max_cycles=80)
    assert state.get("history"), state
    assert state.get("satisfied") is True, state
    assert state.get("step", 0) >= 2, state
    assert len(state.get("plan", [])) >= 2, state
    print(
        f"PASS live_desktop_two_step step={state.get('step')} "
        f"satisfied={state.get('satisfied')} history={len(state.get('history', []))}"
    )
    return True


TESTS = [
    ("live_desktop_single", test_live_desktop_single_step),
    ("live_desktop_two_step", test_live_desktop_two_step),
]


if __name__ == "__main__":
    if os.environ.get("ENDGAME_SIM", "").lower() in ("1", "true", "yes"):
        print("SKIP — ENDGAME_SIM set")
        raise SystemExit(0)
    if not llm_reachable():
        print("SKIP — LLM unreachable")
        raise SystemExit(0)
    if not desktop_available():
        print("SKIP — Windows desktop observer unavailable")
        raise SystemExit(0)

    os.environ.pop("ENDGAME_SIM", None)
    print("Live desktop + LLM OK")
    passed = 0
    for name, fn in TESTS:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
    print(f"\n{passed}/{len(TESTS)} desktop live tests passed")
    raise SystemExit(0 if passed == len(TESTS) else 1)