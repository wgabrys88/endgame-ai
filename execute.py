from __future__ import annotations

import brain
import bus
import contextlib
import desktop
import io
import nodes


DATASHEET = bus.datasheet(
    "execute",
    kind="llm_code_actuator",
    inputs=["goal", "current_step", "fresh_observation", "action_frame", "capability_runtime"],
    signals=["verify", "frame", "reflect", "self_modify", "error"],
    writes=["last_action", "last_code", "last_result", "last_error", "action_frame"],
    record_type="execution",
)


def _should_frame(state: dict, conclusion: str) -> bool:
    step_index = int(state.get("step", 0) or 0)
    if state.get("action_frame") and (state.get("action_frame") or {}).get("step_index") == step_index:
        return False
    if state.get("framing_attempted_for_step") == step_index:
        return False
    if conclusion in {"CANNOT", "FRAME"}:
        return True
    last_error = str(state.get("last_error") or "")
    return bool(last_error) and state.get("framing_attempted_for_step") != step_index


def run(ctx):
    """Ask the brain for executable Python, then run it in the desktop namespace."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}

    payload = {
        "goal": goal,
        "step": {
            "description": step.get("description", goal),
            "done_when": step.get("done_when", ""),
        },
        "state": bus.state_brief(state),
        "observation": bus.observation_brief(state),
        "action_frame": state.get("action_frame"),
        "last": {
            "error": state.get("last_error"),
            "result": state.get("last_result", ""),
            "action": state.get("last_action", {}),
        },
        "capability_contract": {
            "body_truth": "Code runs locally in the organism capability runtime. The listed helpers are conveniences, not the full limit of Python.",
            "pyautogui_compat": "Use pyautogui.click/write/press/hotkey/scroll naturally; it is a dependency-free facade backed by the organism body.",
            "helpers": [
                "click_node(id)", "scroll_node(id, amount)", "node_by_id(id)", "action_nodes(action=None)",
                "click(x,y,hwnd=0)", "type_text(text)", "press_key(key)", "hotkey(keys)",
                "scroll(x,y,amount,hwnd=0)", "focus_window(target)", "open_url(browser,url)",
            ],
            "modules": ["subprocess", "ctypes", "os", "sys", "json", "re", "time", "pathlib", "math", "random"],
            "result_rule": "Set result to a small JSON-serializable value describing what happened.",
        },
    }

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("execute", ""),
        payload=payload,
        wiring=wiring,
        expected_record_type="execution",
    )
    if record.get("record_type") != "execution":
        raise RuntimeError(f"execute expected record_type=execution, got {record.get('record_type')}")

    data = record.get("data", {})
    code = str(data.get("code", "") or "")
    conclusion = str(data.get("conclusion", "CANNOT") or "CANNOT").upper()

    if conclusion not in {"EXECUTE", "CANNOT", "FRAME", "SELF_MODIFY"}:
        conclusion = "CANNOT"

    if conclusion == "SELF_MODIFY":
        return bus.emit(
            "self_modify",
            {"last_action": {"code": "", "conclusion": conclusion}, "last_error": "execute requested self modification"},
            record=record,
            evidence=payload,
        )

    if conclusion != "EXECUTE" or not code.strip():
        signal = "frame" if _should_frame(state, conclusion) else "reflect"
        return bus.emit(
            signal,
            {
                "last_action": {"code": "", "conclusion": conclusion},
                "last_error": f"execute returned {conclusion}",
            },
            record=record,
            evidence=payload,
        )

    ns = nodes.build_capability_runtime(ctx)
    ns["desktop"] = desktop
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, ns)
        explicit_result = ns.get("result")
        result = {
            "result": explicit_result,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }
        error = None
    except Exception as exc:
        result = {"stdout": stdout.getvalue(), "stderr": stderr.getvalue()}
        error = f"{type(exc).__name__}: {exc}"

    signal = "reflect" if error else "verify"
    return bus.emit(
        signal,
        {
            "last_action": {"code": code, "conclusion": conclusion},
            "last_code": code,
            "last_result": result,
            "last_error": error,
            "action_frame": None if not error else state.get("action_frame"),
        },
        record=record,
        evidence=payload,
    )
