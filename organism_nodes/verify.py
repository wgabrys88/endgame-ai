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

    last_action = state.get("last_action", {})
    last_result = state.get("last_result", "")
    last_error = state.get("last_error", "")

    fresh_obs = state.get("fresh_observation", {})
    evidence_payload = {
        "last_action": last_action,
        "last_result": last_result,
        "last_error": last_error,
    }
    if fresh_obs:
        evidence_payload["fresh_observation"] = fresh_obs

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("verify", ""),
        payload={
            "goal": goal,
            "step": {"description": step_goal, "done_when": done_when},
            "evidence": evidence_payload,
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
