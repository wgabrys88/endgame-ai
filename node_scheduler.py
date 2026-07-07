from __future__ import annotations

import core_bus as bus


DATASHEET = bus.datasheet(
    "node_scheduler",
    kind="mechanical_step_selector",
    inputs=["plan.intent", "state.step"],
    signals=["step_ready", "plan_complete", "error"],
    writes=["current_step", "step_goal", "step", "action_frame"],
    record_type=None,
)


def run(ctx):
    state = ctx.get("state", {})
    plan_obj = state.get("plan", {})

    if isinstance(plan_obj, dict):
        plan = plan_obj.get("intent", [])
    elif isinstance(plan_obj, list):
        plan = plan_obj
    else:
        raise RuntimeError(f"scheduler expected plan object or list, got {type(plan_obj).__name__}")
    if not isinstance(plan, list):
        raise RuntimeError(f"scheduler expected plan.intent list, got {type(plan).__name__}")

    step_idx = int(state.get("step", 0) or 0)

    if step_idx >= len(plan):
        root_plan = state.get("root_plan_intent") or []
        completed_steps = state.get("completed_steps") or []
        if isinstance(root_plan, list) and root_plan:
            completed_count = len(completed_steps) if isinstance(completed_steps, list) else 0
            if completed_count < len(root_plan):
                raise RuntimeError(
                    "active plan completed before root goal obligations were complete: "
                    f"completed={completed_count} root_obligations={len(root_plan)}"
                )
        return bus.emit("plan_complete", {"plan_complete": True, "current_step": None, "action_frame": None})

    step = plan[step_idx]
    if not isinstance(step, dict):
        raise RuntimeError(f"scheduler expected step object at index {step_idx}, got {type(step).__name__}")
    if not isinstance(step.get("description"), str) or not isinstance(step.get("done_when"), str):
        raise RuntimeError(f"scheduler step {step_idx} must contain string description and done_when")
    return bus.emit(
        "step_ready",
        {
            "current_step": step,
            "step_goal": step.get("description", str(step)),
            "step": step_idx,
            "action_frame": None,
            "framing_attempted_for_step": None,
        },
    )
