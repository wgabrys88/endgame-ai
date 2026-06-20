"""Smoke + mocked ROD graph tests — no LLM endpoint required."""
import contextlib
import json
import os
import server

PLAN_JSON = json.dumps({
    "record_type": "task",
    "data": {
        "steps": [
            {"description": "open notepad", "done_when": "Notepad is open"},
            {"description": "type hello", "done_when": "hello is typed"},
        ]
    },
})

PLAN_SINGLE_JSON = json.dumps({
    "record_type": "task",
    "data": {
        "steps": [
            {"description": "open notepad", "done_when": "Notepad is open"},
        ]
    },
})

ACT_OPEN_JSON = json.dumps({
    "record_type": "action",
    "data": {
        "conclusion": "EXECUTE",
        "actions": [{"verb": "hotkey", "target": "win+r", "value": ""}],
    },
})

ACT_WRITE_JSON = json.dumps({
    "record_type": "action",
    "data": {
        "conclusion": "EXECUTE",
        "actions": [{"verb": "write", "target": "notepad", "value": "hello"}],
    },
})

VERIFY_OK_JSON = json.dumps({
    "record_type": "verdict",
    "data": {
        "confirmed": True,
        "evidence": "OK: hotkey win+r",
        "reason": "launch action succeeded",
    },
})

VERIFY_DENY_JSON = json.dumps({
    "record_type": "verdict",
    "data": {
        "confirmed": False,
        "evidence": "BLOCKED or no OK in outcome",
        "reason": "step not satisfied yet",
    },
})

REFLECT_RETRY_JSON = json.dumps({
    "record_type": "diagnosis",
    "data": {
        "diagnosis": "Run dialog did not open",
        "suggestion": "try focus desktop first",
        "should_replan": False,
    },
})


def _act_json_for_subtask(user):
    subtask = ""
    for line in user.splitlines():
        if line.startswith("SUBTASK:"):
            subtask = line.split(":", 1)[1].strip().lower()
            break
    if "hello" in subtask or "type" in subtask:
        return ACT_WRITE_JSON
    return ACT_OPEN_JSON


def _make_mock_llm(plan_json=PLAN_JSON):
    def mock_llm(system, user, temperature=None):
        if "Planner" in system:
            return plan_json, "", 0.01
        if "Act (executor)" in system:
            return _act_json_for_subtask(user), "", 0.01
        if "Verifier" in system:
            return VERIFY_OK_JSON, "", 0.01
        if "Reflector" in system:
            return REFLECT_RETRY_JSON, "", 0.01
        return "{}", "", 0.01
    return mock_llm


_route_mock_llm = _make_mock_llm(PLAN_JSON)


@contextlib.contextmanager
def mocked_run_env(plan_json=PLAN_JSON):
    original_llm = server.llm
    original_fresh = server.fresh_state
    original_delay = server.WIRING["runtime"].get("cycle_delay_ms", 300)
    state_backup = server.STATE_FILE.read_text(encoding="utf-8") if server.STATE_FILE.exists() else None

    server.llm = _make_mock_llm(plan_json)
    server.WIRING["runtime"]["cycle_delay_ms"] = 0

    def fresh(goal):
        s = original_fresh(goal)
        s["no_desktop"] = True
        s["screen"] = "[1] Run dialog | [2] Open: field"
        return s

    server.fresh_state = fresh
    try:
        yield
    finally:
        server.llm = original_llm
        server.fresh_state = original_fresh
        server.WIRING["runtime"]["cycle_delay_ms"] = original_delay
        if state_backup is None:
            if server.STATE_FILE.exists():
                server.STATE_FILE.unlink()
        else:
            server.STATE_FILE.write_text(state_backup, encoding="utf-8")


def _step_state():
    state = server.fresh_state("open notepad and type hello")
    state.update({
        "no_desktop": True,
        "screen": "[1] Run dialog | [2] Open: field",
        "plan": [{"description": "open notepad", "done_when": "Notepad is open"}],
        "step": 0,
        "step_goal": "open notepad",
        "current_step": {"description": "open notepad", "done_when": "Notepad is open"},
        "history": [],
        "retries": 0,
    })
    return state


def test_validate_wiring():
    errs = server.validate_wiring(server.WIRING)
    assert not errs, errs
    print("PASS validate_wiring")


def test_entry_node():
    r = server.NODES["entry"]({"goal": "test"}, {})
    assert r["signals"] == ["ready"]
    print("PASS entry_node")


def test_find_targets():
    topo = server.WIRING["topology"]
    t = server.find_targets("goal_inbox", ["ready"], topo)
    assert t == ["moe_route"]
    t2 = server.find_targets("moe_route", ["self"], topo)
    assert t2 == ["planner"]
    print("PASS find_targets")


def test_planner_to_scheduler_mock():
    original_llm = server.llm

    def mock_llm(system, user, temperature=None):
        return PLAN_JSON, "", 0.01

    server.llm = mock_llm
    try:
        state = server.fresh_state("open notepad and type hello")
        r = server.NODES["entry"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["ready"]

        r = server.NODES["planner"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["plan_ready"], r
        assert len(state["plan"]) == 2

        r = server.NODES["scheduler"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["step_ready"]
        assert state["current_step"]["description"] == "open notepad"
        print("PASS planner_to_scheduler_mock")
    finally:
        server.llm = original_llm


def test_observe_stub():
    r = server.NODES["observe"]({}, {})
    assert r["signals"] == ["screen_ready"]
    assert "screen" in r["patch"]
    print("PASS observe_stub")


def test_step_cycle_confirmed():
    original_llm = server.llm
    server.llm = _route_mock_llm
    try:
        state = _step_state()
        r = server.NODES["observe"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["screen_ready"]

        r = server.NODES["act"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["acted"], state.get("last_error")
        assert "hotkey" in state.get("last_outcome", "").lower()

        r = server.NODES["verify"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["step_confirmed"], state.get("last_error")
        assert state["step"] == 1

        r = server.NODES["scheduler"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["plan_complete"]
        print("PASS step_cycle_confirmed")
    finally:
        server.llm = original_llm


def test_step_cycle_denied_reflect_retry():
    calls = {"verify": 0}

    def mock_llm(system, user, temperature=None):
        if "Verifier" in system:
            calls["verify"] += 1
            body = VERIFY_DENY_JSON if calls["verify"] == 1 else VERIFY_OK_JSON
            return body, "", 0.01
        return _route_mock_llm(system, user)

    original_llm = server.llm
    server.llm = mock_llm
    try:
        state = _step_state()
        for node in ("observe", "act", "verify"):
            r = server.NODES[node](state, {})
            state.update(r["patch"])
        assert r["signals"] == ["step_denied"]

        r = server.NODES["reflect"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["retry"]
        assert state["retries"] == 1

        for node in ("observe", "act", "verify"):
            r = server.NODES[node](state, {})
            state.update(r["patch"])
        assert r["signals"] == ["step_confirmed"]
        assert state["step"] == 1
        print("PASS step_cycle_denied_reflect_retry")
    finally:
        server.llm = original_llm


def test_run_graph_single_step():
    with mocked_run_env(PLAN_SINGLE_JSON):
        state = server.run("open notepad")
    assert state.get("satisfied") is True, state
    assert state.get("step") == 1
    assert len(state.get("history", [])) == 1
    assert "OK:" in state.get("last_outcome", "")
    print("PASS run_graph_single_step")


def test_run_graph_two_steps():
    with mocked_run_env(PLAN_JSON):
        state = server.run("open notepad and type hello")
    assert state.get("satisfied") is True, state
    assert state.get("step") == 2
    assert len(state.get("history", [])) == 2
    print("PASS run_graph_two_steps")


def test_plan_failed_terminal():
    original_llm = server.llm
    original_delay = server.WIRING["runtime"].get("cycle_delay_ms", 300)
    state_backup = server.STATE_FILE.read_text(encoding="utf-8") if server.STATE_FILE.exists() else None
    server.llm = lambda system, user, temperature=None: ("not-json", "", 0.01)
    server.WIRING["runtime"]["cycle_delay_ms"] = 0
    try:
        state = server.run("unplannable goal")
        assert state.get("plan_failed") is True, state
        assert state.get("satisfied") is False, state
    finally:
        server.llm = original_llm
        server.WIRING["runtime"]["cycle_delay_ms"] = original_delay
        if state_backup is None:
            if server.STATE_FILE.exists():
                server.STATE_FILE.unlink()
        else:
            server.STATE_FILE.write_text(state_backup, encoding="utf-8")
    print("PASS plan_failed_terminal")


SELF_MODIFY_BAD = json.dumps({
    "record_type": "wiring_patch",
    "data": {
        "op": "add_edge",
        "payload": {"from": "missing_node", "to": "planner", "on": "bad"},
    },
})


def test_self_modify_rejects_invalid_wiring():
    original_llm = server.llm
    backup = (server.PROMPTS / "wiring.json").read_text(encoding="utf-8")
    server.llm = lambda system, user, temperature=None: (SELF_MODIFY_BAD, "", 0.01)
    try:
        state = {"goal": "stuck", "history": [], "last_error": "blocked"}
        r = server.NODES["self_modify"](state, {})
        assert r["signals"] == ["modify_failed"], r
        err = r["patch"].get("last_error", "")
        assert "missing_node" in err or "unknown" in err.lower()
        current = (server.PROMPTS / "wiring.json").read_text(encoding="utf-8")
        assert current == backup
    finally:
        server.llm = original_llm
        server.WIRING = json.loads(backup)
    print("PASS self_modify_rejects_invalid_wiring")


def test_bus_interrupt_replans():
    original_llm = server.llm
    bus_backup = server.BUS_FILE.read_text(encoding="utf-8") if server.BUS_FILE.exists() else None
    calls = {"planner": 0}

    def mock_llm(system, user, temperature=None):
        if "Planner" in system:
            calls["planner"] += 1
            if calls["planner"] == 1:
                return PLAN_SINGLE_JSON, "", 0.01
            return PLAN_JSON, "", 0.01
        return _route_mock_llm(system, user)

    server.WIRING["runtime"]["cycle_delay_ms"] = 0
    state_backup = server.STATE_FILE.read_text(encoding="utf-8") if server.STATE_FILE.exists() else None
    try:
        slot = server.WIRING.get("instance", {}).get("slot", 1)
        server.bus_write([{
            "ts": server.time.time() + 1,
            "from_slot": 0,
            "to_slot": slot,
            "type": "goal",
            "payload": {"goal": "open notepad and type hello"},
        }])
        with mocked_run_env(PLAN_SINGLE_JSON):
            server.llm = mock_llm
            state = server.run("open notepad")
        assert calls["planner"] >= 2, calls
        assert state.get("goal") == "open notepad and type hello"
    finally:
        server.llm = original_llm
        if bus_backup is None:
            if server.BUS_FILE.exists():
                server.BUS_FILE.unlink()
        else:
            server.BUS_FILE.write_text(bus_backup, encoding="utf-8")
        if state_backup is None:
            if server.STATE_FILE.exists():
                server.STATE_FILE.unlink()
        else:
            server.STATE_FILE.write_text(state_backup, encoding="utf-8")
    print("PASS bus_interrupt_replans")


def test_llm_parse_retry():
    calls = {"n": 0}
    original_llm = server.llm

    def flaky_llm(system, user, temperature=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json", "", 0.01
        return PLAN_SINGLE_JSON, "", 0.01

    server.llm = flaky_llm
    try:
        state = server.fresh_state("open notepad")
        r = server.NODES["planner"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["plan_ready"], r
        assert calls["n"] == 2
        print("PASS llm_parse_retry")
    finally:
        server.llm = original_llm


def test_simulation_run_integration():
    import actions
    prev = os.environ.get("ENDGAME_SIM")
    os.environ["ENDGAME_SIM"] = "1"
    actions._desktop = None
    actions._executor = None
    original_llm = server.llm
    original_delay = server.WIRING["runtime"].get("cycle_delay_ms", 300)
    state_backup = server.STATE_FILE.read_text(encoding="utf-8") if server.STATE_FILE.exists() else None

    server.WIRING["runtime"]["cycle_delay_ms"] = 0
    server.llm = _make_mock_llm(PLAN_SINGLE_JSON)
    try:
        state = server.run("open notepad")
        assert state.get("satisfied") is True, state
        assert "hotkey" in state.get("last_outcome", "").lower()
        assert len(state.get("history", [])) == 1
        assert "Open" in state.get("screen", ""), state.get("screen", "")[:200]
    finally:
        server.llm = original_llm
        server.WIRING["runtime"]["cycle_delay_ms"] = original_delay
        actions._desktop = None
        actions._executor = None
        if prev is None:
            os.environ.pop("ENDGAME_SIM", None)
        else:
            os.environ["ENDGAME_SIM"] = prev
        if state_backup is None:
            if server.STATE_FILE.exists():
                server.STATE_FILE.unlink()
        else:
            server.STATE_FILE.write_text(state_backup, encoding="utf-8")
    print("PASS simulation_run_integration")


def test_resolve_notepad_not_recycle_bin():
    from actions import ActionExecutor
    from desktop import Desktop, Element

    elements = {
        "1": Element("1", "ListItem", "Recycle Bin", "", 1, 10, 10, 40, 40, "click"),
        "3": Element("3", "Button", "Notepad - 1 running window", "", 1, 100, 10, 80, 24, "click"),
    }
    ex = ActionExecutor(Desktop(), {"verbs": {}})
    el = ex._resolve("Notepad - 1 running window", elements)
    assert el and el.name.startswith("Notepad"), el
    print("PASS resolve_notepad_not_recycle_bin")


def test_verify_preflight_denies_failed_outcome():
    state = {
        "last_outcome": "FAILED: write Open:: element missing",
        "current_step": {"description": "open notepad", "done_when": "Notepad is open"},
    }
    r = server.NODES["verify"](state, {})
    assert r["signals"] == ["step_denied"]
    print("PASS verify_preflight_denies_failed_outcome")


def test_act_outcome_prefix_on_failure():
    original_llm = server.llm

    def mock_llm(system, user, temperature=None):
        return ACT_OPEN_JSON, "", 0.01

    original_execute = server.execute_verb
    server.llm = mock_llm
    server.execute_verb = lambda verb, target, value="": f"FAILED: element {target} not found"
    try:
        state = _step_state()
        r = server.NODES["act"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["acted"]
        assert state["last_outcome"].startswith("FAILED:")
        print("PASS act_outcome_prefix_on_failure")
    finally:
        server.llm = original_llm
        server.execute_verb = original_execute


def test_replan_preserves_progress():
    original_llm = server.llm
    server.llm = _make_mock_llm(PLAN_JSON)
    try:
        state = server.fresh_state("open notepad and type hello")
        state.update({
            "replanning": True,
            "step": 1,
            "history": [{"attempt": 1, "action": "hotkey win+r", "outcome": "OK"}],
            "plan": [{"description": "open notepad", "done_when": "Notepad is open"}],
        })
        r = server.NODES["planner"](state, {})
        state.update(r["patch"])
        assert r["signals"] == ["plan_ready"], r
        assert state["step"] == 1
        assert len(state["history"]) == 1
        assert state.get("replanning") is False
        print("PASS replan_preserves_progress")
    finally:
        server.llm = original_llm


def test_moe_route_self():
    state = server.fresh_state("open notepad")
    r = server.NODES["moe_route"](state, {})
    assert r["signals"] == ["self"], r
    print("PASS moe_route_self")


def test_colony_boot_sim():
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request

    root = server.ROOT
    proc = subprocess.Popen(
        [sys.executable, str(root / "colony.py"), "--sim", "1"],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ok = False
        for _ in range(40):
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen("http://127.0.0.1:9078/health", timeout=2) as r:
                    if json.loads(r.read()).get("ok"):
                        ok = True
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        assert ok, "colony slot 1 health timeout"
        print("PASS colony_boot_sim")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_rod_trigger_port_mapping():
    assert server.http_port(1) == 9078
    assert server.colony_port(1) == 9077
    assert server.http_port(1) != server.colony_port(1)
    print("PASS rod_trigger_port_mapping")


def test_apply_instance_env_slot():
    backup = json.loads(json.dumps(server.WIRING))
    os.environ["ENDGAME_SLOT"] = "2"
    os.environ["ENDGAME_PERMISSIONS"] = "desktop_exec,plan"
    try:
        server.apply_instance_env()
        assert server.WIRING["instance"]["slot"] == 2
        assert "desktop_exec" in server.WIRING["instance"]["permissions"]
        assert server.http_port() == 9079
        print("PASS apply_instance_env_slot")
    finally:
        os.environ.pop("ENDGAME_SLOT", None)
        os.environ.pop("ENDGAME_PERMISSIONS", None)
        server.WIRING = backup


def test_traces_hidden_on_fresh_plan():
    server.TRACES_FILE.write_text(
        json.dumps({"goal": "open notepad", "plan": [{"description": "open notepad"}]}) + "\n",
        encoding="utf-8",
    )
    try:
        val = server._resolve_value({"replan_count": 0, "replanning": False}, "traces.recent")
        assert val == ""
        val2 = server._resolve_value({"replan_count": 1, "replanning": True}, "traces.recent")
        assert "open notepad" in val2
        print("PASS traces_hidden_on_fresh_plan")
    finally:
        if server.TRACES_FILE.exists():
            server.TRACES_FILE.unlink()


def test_trace_persisted_on_success():
    trace_backup = server.TRACES_FILE.read_text(encoding="utf-8") if server.TRACES_FILE.exists() else None
    try:
        with mocked_run_env(PLAN_SINGLE_JSON):
            server.run("trace test goal")
        assert server.TRACES_FILE.exists()
        traces = server.recent_traces(1)
        assert traces and traces[-1].get("goal") == "trace test goal"
        print("PASS trace_persisted_on_success")
    finally:
        if trace_backup is None:
            if server.TRACES_FILE.exists():
                server.TRACES_FILE.unlink()
        else:
            server.TRACES_FILE.write_text(trace_backup, encoding="utf-8")


def test_moe_route_delegate():
    original_wiring = server.WIRING
    wiring = json.loads(json.dumps(original_wiring))
    wiring["instance"]["permissions"] = []
    server.WIRING = wiring
    try:
        state = server.fresh_state("open chrome and go to youtube")
        r = server.NODES["moe_route"](state, {})
        assert r["signals"] == ["delegated"], r
        assert "delegated_to" in r["patch"]
    finally:
        server.WIRING = original_wiring
    print("PASS moe_route_delegate")


def test_simulation_desktop_flow():
    import actions
    prev = os.environ.get("ENDGAME_SIM")
    os.environ["ENDGAME_SIM"] = "1"
    actions._desktop = None
    actions._executor = None
    try:
        screen = actions.observe_screen()
        assert "Desktop" in screen
        result = actions.execute_verb("hotkey", "win+r", "")
        assert "pressed" in result.lower()
        screen2 = actions.observe_screen()
        assert "Open" in screen2
        result2 = actions.execute_verb("write", "Open", "notepad")
        assert "typed" in result2.lower()
        result3 = actions.execute_verb("press", "enter", "")
        assert "pressed" in result3.lower()
        screen3 = actions.observe_screen()
        assert "Notepad" in screen3
        result4 = actions.execute_verb("write", "Text Editor", "hello")
        assert "typed" in result4.lower()
        screen4 = actions.observe_screen()
        assert "hello" in screen4
    finally:
        actions._desktop = None
        actions._executor = None
        if prev is None:
            os.environ.pop("ENDGAME_SIM", None)
        else:
            os.environ["ENDGAME_SIM"] = prev
    print("PASS simulation_desktop_flow")


if __name__ == "__main__":
    tests = [
        test_validate_wiring,
        test_entry_node,
        test_find_targets,
        test_planner_to_scheduler_mock,
        test_observe_stub,
        test_step_cycle_confirmed,
        test_step_cycle_denied_reflect_retry,
        test_run_graph_single_step,
        test_run_graph_two_steps,
        test_plan_failed_terminal,
        test_self_modify_rejects_invalid_wiring,
        test_bus_interrupt_replans,
        test_llm_parse_retry,
        test_simulation_run_integration,
        test_simulation_desktop_flow,
        test_resolve_notepad_not_recycle_bin,
        test_verify_preflight_denies_failed_outcome,
        test_act_outcome_prefix_on_failure,
        test_replan_preserves_progress,
        test_moe_route_self,
        test_moe_route_delegate,
        test_traces_hidden_on_fresh_plan,
        test_trace_persisted_on_success,
        test_colony_boot_sim,
        test_rod_trigger_port_mapping,
        test_apply_instance_env_slot,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)