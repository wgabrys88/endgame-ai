from __future__ import annotations

import core_brain as brain
import core_bus as bus


DATASHEET = bus.datasheet(
    "node_verify",
    kind="llm_reality_comparator",
    inputs=["goal", "current_step", "last_action", "last_result", "last_error", "fresh_observation"],
    signals=["step_confirmed", "step_denied", "error"],
    writes=["verification", "last_verification", "step"],
    record_type="verification",
)


def run(ctx):
    """Verify node: LLM judges if step intent was satisfied based on evidence."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")

    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    done_when = step.get("done_when", "")

    evidence_payload = {
        "last_action": state.get("last_action", {}),
        "last_result": state.get("last_result", ""),
        "last_error": state.get("last_error", ""),
        "state": bus.state_brief(state),
    }

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("node_verify", ""),
        payload={
            "goal": goal,
            "observation": bus.observation_brief(state),
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
    success = bool(data.get("success", False))

    if signal not in ("step_confirmed", "step_denied"):
        signal = "step_denied"
        success = False
    if signal == "step_confirmed" and not success:
        signal = "step_denied"
    if success and signal != "step_confirmed":
        success = False

    patch = {
        "verification": {
            "success": success,
            "reasoning": data.get("reasoning", record.get("reasoning", "")),
            "step_goal": step_goal,
            "done_when": done_when,
        },
        "last_verification": {"success": success, "signal": signal},
    }
    if success:
        patch["step"] = int(state.get("step", 0) or 0) + 1
        patch["failure_streak"] = {"signature": None, "count": 0}
        patch["action_frame"] = None
    return bus.emit(signal, patch, record=record, evidence=evidence_payload)
