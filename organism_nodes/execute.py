from __future__ import annotations

import brain
import contextlib
import desktop
import io
import nodes


def _compiled_execution(code: str):
    try:
        return compile(code, "<brain_execution>", "exec"), code, None
    except SyntaxError as original:
        candidate = code.rstrip()
        removed = 0
        while candidate.endswith("}"):
            candidate = candidate[:-1].rstrip()
            removed += 1
            try:
                return compile(candidate, "<brain_execution>", "exec"), candidate, {
                    "kind": "trimmed_trailing_json_brace",
                    "removed_chars": removed,
                    "original_error": f"{original.msg} line {original.lineno}",
                }
            except SyntaxError:
                continue
        raise original


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
                "focused_title": state.get("focused_title", ""),
                "fresh_scan": state.get("fresh_scan", False),
                "observed_at": state.get("observed_at"),
                "desktop_tree": state.get("desktop_tree", {}),
                "observation_artifact": state.get("observation_artifact", {}),
                "screen_text": state.get("screen_text", ""),
            },
            "last": {
                "error": state.get("last_error"),
                "result": state.get("last_result", ""),
                "action": state.get("last_action", {}),
            },
            "namespace": {
                "values": ["state", "wiring", "goal", "last", "fresh_observation", "desktop_tree", "screen_text", "focused_title", "observed_at", "fresh_scan", "observation_artifact", "observation_delta"],
                "observation": ["observe_screen()", "last_desktop_tree()", "get_focused_title()", "node_by_id(id)", "action_nodes(action=None)"],
                "actions": ["click_node(id)", "scroll_node(id,amount)", "click(x,y,hwnd)", "type_text(text)", "press_key(key)", "hotkey(keys)", "scroll(x,y,amount,hwnd)", "focus_window(target)", "open_url(browser,url)"],
                "modules": ["subprocess", "ctypes", "os", "sys", "json", "re", "time", "pathlib", "math", "random"],
                "repo": ["wiring_limit(name, default, wiring)", "repo_root", "python_executable"],
            },
        },
        wiring=wiring,
        expected_record_type="execution",
    )
    if record.get("record_type") != "execution":
        raise RuntimeError(f"execute expected record_type=execution, got {record.get('record_type')}")

    data = record.get("data", {})
    code = data.get("code", "")
    conclusion = data.get("conclusion", "CANNOT")
    if conclusion != "EXECUTE" or not code.strip():
        return "reflect", {"last_action": {"code": "", "conclusion": "CANNOT"}, "last_error": "execute returned CANNOT"}

    try:
        compiled, code, code_repair = _compiled_execution(code)
    except SyntaxError as exc:
        return "reflect", {
            "last_action": {"code": code, "conclusion": conclusion},
            "last_code": code,
            "last_result": {"stdout": "", "stderr": ""},
            "last_error": f"SyntaxError: {exc.msg} ({exc.filename}, line {exc.lineno})",
        }

    ns = nodes.build_capability_runtime(ctx)
    ns["desktop"] = desktop
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compiled, ns)
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
        "last_action": {"code": code, "conclusion": conclusion, "code_repair": code_repair},
        "last_code": code,
        "last_result": result,
        "last_error": error,
    }
