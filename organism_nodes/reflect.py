from __future__ import annotations

import brain


def run(ctx):
    """Diagnose a failed step and choose retry, replan, escalate, or give_up."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}

    fresh_obs = state.get("fresh_observation", {})
    evidence = {
        "last_action": state.get("last_action", {}),
        "last_result": state.get("last_result", ""),
        "last_error": state.get("last_error", ""),
        "last_verification": state.get("last_verification", {}),
    }
    if fresh_obs:
        evidence["fresh_observation"] = fresh_obs

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("reflect", ""),
        payload={
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": evidence,
        },
        wiring=wiring,
        expected_record_type="reflection",
    )
    if record.get("record_type") != "reflection":
        raise RuntimeError(f"reflect expected record_type=reflection, got {record.get('record_type')}")

    data = record.get("data", {})
    signal = data.get("next_signal", "replan")
    if signal not in {"retry", "replan", "escalate", "give_up"}:
        signal = "replan"
    lesson = data.get("lesson", "No lesson provided")
    diagnosis = data.get("diagnosis", "No diagnosis")

    return signal, {
        "reflection": {
            "lesson": lesson,
            "diagnosis": diagnosis,
            "step_goal": step.get("description", goal),
            "recovery_signal": signal,
        },
        "last_reflection": {"signal": signal, "lesson": lesson},
    }
