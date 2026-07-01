from __future__ import annotations

import brain
import nodes
import desktop
import json


def run(ctx):
    """Execute node: Grok writes Python code, exec() runs it with full desktop namespace."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")

    # Get current step from scheduler
    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    done_when = step.get("done_when", "")

    # Get observation data
    screen = state.get("screen", {})
    elements = state.get("elements", {})
    snapshot = state.get("snapshot", {})
    last_error = state.get("last_error")
    last_result = state.get("last_result", "")
    last_action = state.get("last_action", {})

    # Format elements for prompt
    elements_summary = {}
    if isinstance(elements, list):
        for i, el in enumerate(elements):
            elements_summary[str(i)] = el
    elif isinstance(elements, dict):
        elements_summary = elements

    # Build the execute prompt
    prompt = f"""You are the EXECUTE node. Write Python code to achieve the step goal.

STEP GOAL: {step_goal}
DONE WHEN: {done_when}
GOAL: {goal}

SCREEN:
{json.dumps(screen, indent=2)}

ELEMENTS (dict[id] -> {{name, control_type, px, py, hwnd, rect, ...}}):
{json.dumps(elements_summary, indent=2)[:5000]}

LAST_ERROR: {last_error or "none"}
LAST_RESULT: {str(last_result)[:1000] if last_result else "none"}
LAST_ACTION: {json.dumps(last_action)[:1000] if last_action else "none"}

NAMESPACE AVAILABLE:
# Observation
observe_screen() -> dict
last_observation_snapshot() -> dict
get_focused_title() -> str

# Raw desktop actions (from Desktop class)
# Note: You have access to the global desktop module via 'desktop' import

# System modules
subprocess, ctypes, os, sys, json, re, time, pathlib, math, random

# Self-modification
apply_wiring_patch(wiring, parsed) -> (op, patch)
save_wiring(wiring)
wiring_limit(name, default, wiring) -> int

# Context
state, wiring, goal

RETURN ONLY JSON:
{{"record_type": "execution", "data": {{"code": "...", "conclusion": "EXECUTE|CANNOT"}}}}

RULES:
- conclusion=EXECUTE when code non-empty, CANNOT when impossible
- Code runs in exec() with above namespace
- Use elements dict for targeting: elements["12"]["px"], elements["12"]["py"]
- LAST_ERROR is critical — adapt, don't repeat
- Available desktop actions: click(x, y, hwnd), type_text(text), press_key(key), hotkey(keys), scroll(x, y, amount, hwnd), focus_window(target), open_url(browser, url)
"""

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("execute", ""),
        payload={"prompt": prompt, "goal": goal, "state": state},
        wiring=wiring
    )

    if record.get("record_type") != "execution":
        raise RuntimeError(f"execute expected record_type=execution, got {record.get('record_type')}")

    data = record.get("data", {})
    code = data.get("code", "")
    conclusion = data.get("conclusion", "CANNOT")

    if conclusion == "EXECUTE" and code.strip():
        ns = nodes.build_execute_namespace(ctx)
        # Add desktop module to namespace
        ns["desktop"] = desktop
        try:
            exec(code, ns)
            result = ns.get("result", "executed (no result variable)")
            error = None
        except Exception as e:
            result = ""
            error = f"{type(e).__name__}: {e}"
        patch = {
            "last_action": {"code": code, "conclusion": conclusion},
            "last_code": code,
            "last_result": str(result)[:5000],
            "last_error": error,
        }
        signal = "reflect" if error else "verify"
    else:
        patch = {"last_action": {"code": "", "conclusion": "CANNOT"}, "last_error": "execute returned CANNOT"}
        signal = "reflect"

    return signal, patch