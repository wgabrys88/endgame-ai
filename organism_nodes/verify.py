from __future__ import annotations

import brain


def run(ctx):
    """Verify node: LLM judges if step intent was satisfied based on evidence."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    
    # Get current step
    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    done_when = step.get("done_when", "")
    
    # Evidence from state
    screen_text = state.get("screen_text", "")
    elements = state.get("elements", {})
    windows = state.get("windows", [])
    focused_title = state.get("focused_title", "")
    last_action = state.get("last_action", {})
    last_result = state.get("last_result", "")
    last_error = state.get("last_error", "")

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("verify", ""),
        payload={
            "goal": goal,
            "step": {"description": step_goal, "done_when": done_when},
            "evidence": {
                "focused_title": focused_title,
                "screen_text": screen_text,
                "elements": elements,
                "windows": windows,
                "last_action": last_action,
                "last_result": last_result,
                "last_error": last_error,
            },
        },
        wiring=wiring,
        expected_record_type="verification",
    )
    
    if record.get("record_type") != "verification":
        raise RuntimeError(f"verify expected record_type=verification, got {record.get('record_type')}")
    
    data = record.get("data", {})
    signal = data.get("next_signal", "step_denied")
    success = data.get("success", False)
    
    # Ensure valid signal
    if signal not in ("step_confirmed", "step_denied"):
        signal = "step_denied"
        success = False
    
    patch = {
        "verification": {
            "success": success,
            "reasoning": data.get("reasoning", ""),
            "step_goal": step_goal,
            "done_when": done_when,
        },
        "last_verification": {"success": success, "signal": signal},
    }
    if success:
        patch["step"] = int(state.get("step", 0) or 0) + 1
    return signal, patch
