from __future__ import annotations

import brain
import desktop


def run(ctx):
    """Verify node: LLM judges if step intent was satisfied based on evidence."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    
    # Get current step
    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    done_when = step.get("done_when", "")
    
    obs = desktop.observe(wiring.get("observe_config", {}))
    screen_text = obs.get("screen_text", "")
    desktop_tree = obs.get("desktop_tree", {})
    observation_artifact = obs.get("observation_artifact", {})
    focused_title = obs.get("focused_title", "")
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
                "fresh_scan": obs.get("fresh_scan", False),
                "observed_at": obs.get("observed_at"),
                "screen_text": screen_text,
                "desktop_tree": desktop_tree,
                "observation_artifact": observation_artifact,
                "observation_delta": obs.get("observation_delta", {}),
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
        "observed_at": obs.get("observed_at"),
        "fresh_scan": obs.get("fresh_scan"),
        "desktop_tree": desktop_tree,
        "action_index": obs.get("action_index", {}),
        "observation_artifact": observation_artifact,
        "observation_delta": obs.get("observation_delta", {}),
        "screen_text": screen_text,
        "focused_title": focused_title,
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
