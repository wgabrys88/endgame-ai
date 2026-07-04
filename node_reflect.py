from __future__ import annotations

import core_brain as brain
import core_bus as bus


DATASHEET = bus.datasheet(
    "node_reflect",
    kind="llm_diagnostic_router",
    inputs=["goal", "current_step", "last_action", "last_result", "last_error", "last_verification", "failure_streak"],
    signals=["retry", "replan", "frame", "escalate", "give_up", "error"],
    writes=["reflection", "last_reflection", "failure_streak"],
    record_type="reflection",
)


MECHANICAL_ESCALATE_MARKERS = (
    "NameError",
    "AttributeError",
    "SyntaxError",
    "ImportError",
    "no topology edge",
    "missing helper",
)


def run(ctx):
    """Diagnose a failed step and choose retry, replan, escalate, or give_up."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}

    streak_patch = bus.update_failure_streak(state)
    projected_streak = streak_patch["failure_streak"]
    evidence = {
        "last_action": state.get("last_action", {}),
        "last_result": state.get("last_result", ""),
        "last_error": state.get("last_error", ""),
        "last_verification": state.get("last_verification", {}),
        "failure_streak": projected_streak,
        "state": bus.state_brief(state),
    }

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("node_reflect", ""),
        payload={
            "goal": goal,
            "observation": bus.observation_brief(state),
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": evidence,
            "routing_rule": {
                "retry": "same plan can work with a better concrete action or better target",
                "replan": "plan step is wrong or too coarse",
                "escalate": "organism wiring, prompt, code, observation, or transport contract is broken",
                "give_up": "goal is impossible or unsafe with current body",
            },
        },
        wiring=wiring,
        expected_record_type="reflection",
    )
    if record.get("record_type") != "reflection":
        raise RuntimeError(f"reflect expected record_type=reflection, got {record.get('record_type')}")

    data = record.get("data", {})
    signal = data.get("next_signal", "replan")
    if signal not in {"retry", "replan", "frame", "escalate", "give_up"}:
        signal = "replan"

    step_index = int(state.get("step", 0) or 0)
    last_verification = state.get("last_verification") or {}
    diagnostic_text = " ".join(str(x) for x in [
        state.get("last_error", ""),
        data.get("diagnosis", ""),
        data.get("lesson", ""),
        state.get("last_action", {}),
    ])
    if (
        last_verification.get("signal") == "step_denied"
        and projected_streak["count"] >= 2
        and state.get("framing_attempted_for_step") != step_index
        and signal in {"retry", "replan"}
    ):
        signal = "frame"
    elif state.get("last_error") and any(
        marker.lower() in diagnostic_text.lower() for marker in MECHANICAL_ESCALATE_MARKERS
    ):
        signal = "escalate"

    lesson = data.get("lesson", "No lesson provided")
    diagnosis = data.get("diagnosis", "No diagnosis")

    patch = {
        **streak_patch,
        "reflection": {
            "lesson": lesson,
            "diagnosis": diagnosis,
            "step_goal": step.get("description", goal),
            "recovery_signal": signal,
        },
        "last_reflection": {"signal": signal, "lesson": lesson, "diagnosis": diagnosis},
    }
    return bus.emit(signal, patch, record=record, evidence=evidence)
