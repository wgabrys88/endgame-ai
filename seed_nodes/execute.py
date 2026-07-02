from __future__ import annotations

import brain
import contextlib
import desktop
import io
import nodes


def run(ctx):
    """Ask the brain for executable Python, then run it in the desktop namespace."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("execute", ""),
        payload={
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "observation": {
                "screen": state.get("screen", {}),
                "focused_title": state.get("focused_title", ""),
                "windows": state.get("windows", []),
                "elements": state.get("elements", {}),
                "screen_text": state.get("screen_text", ""),
                "snapshot": state.get("snapshot", {}),
            },
            "last": {
                "error": state.get("last_error"),
                "result": state.get("last_result", ""),
                "action": state.get("last_action", {}),
            },
            "namespace": {
                "values": ["state", "wiring", "goal", "screen", "elements", "windows", "screen_text", "focused_title"],
                "observation": ["observe_screen()", "last_observation_snapshot()", "get_focused_title()"],
                "actions": ["click(x,y,hwnd)", "type_text(text)", "press_key(key)", "hotkey(keys)", "scroll(x,y,amount,hwnd)", "focus_window(target)", "open_url(browser,url)"],
                "modules": ["subprocess", "ctypes", "os", "sys", "json", "re", "time", "pathlib", "math", "random"],
                "self_modify": ["apply_evolution_patch(wiring, parsed)", "apply_wiring_patch(wiring, parsed)", "save_wiring(wiring)", "wiring_limit(name, default, wiring)", "repo_root", "python_executable"],
            },
        },
        wiring=wiring,
    )
    if record.get("record_type") != "execution":
        raise RuntimeError(f"execute expected record_type=execution, got {record.get('record_type')}")

    data = record.get("data", {})
    code = data.get("code", "")
    conclusion = data.get("conclusion", "CANNOT")
    if conclusion != "EXECUTE" or not code.strip():
        return "reflect", {"last_action": {"code": "", "conclusion": "CANNOT"}, "last_error": "execute returned CANNOT"}

    ns = nodes.build_execute_namespace(ctx)
    ns["desktop"] = desktop
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, ns)
        explicit_result = ns.get("result")
        output = stdout.getvalue()
        errors = stderr.getvalue()
        result = {
            "result": explicit_result,
            "stdout": output,
            "stderr": errors,
        }
        error = None
    except Exception as exc:
        result = {"stdout": stdout.getvalue(), "stderr": stderr.getvalue()}
        error = f"{type(exc).__name__}: {exc}"

    return ("reflect" if error else "verify"), {
        "last_action": {"code": code, "conclusion": conclusion},
        "last_code": code,
        "last_result": result,
        "last_error": error,
    }
