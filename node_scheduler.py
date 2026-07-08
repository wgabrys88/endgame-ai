import core_bus as bus


def run(ctx):
    state = ctx.get("state", {})
    plan_obj = state.get("plan", {})
    plan = plan_obj.get("intent", []) if isinstance(plan_obj, dict) else plan_obj
    if not isinstance(plan, list):
        raise RuntimeError(f"scheduler expected plan.intent list, got {type(plan).__name__}")
    idx = int(state.get("step", 0) or 0)
    if idx >= len(plan):
        root, completed = state.get("root_plan_intent") or [], state.get("completed_steps") or []
        if isinstance(root, list) and root and len(completed if isinstance(completed, list) else []) < len(root):
            raise RuntimeError("active plan completed before root goal obligations were complete")
        return bus.emit("plan_complete", {"plan_complete": True, "current_step": None, "action_frame": None})
    step = plan[idx]
    if not isinstance(step, dict) or not isinstance(step.get("description"), str) or not isinstance(step.get("done_when"), str):
        raise RuntimeError(f"scheduler step {idx} must contain string description and done_when")
    effective = state.get("effective_goal", ctx.get("goal", "")) + f"\n\n[SCHEDULER] Current step: {step.get('description', str(step))}. Complete when: {step.get('done_when', '')}."
    return bus.emit("step_ready", {"current_step": step, "step_goal": step.get("description", str(step)), "step": idx, "action_frame": None, "framing_attempted_for_step": None, "effective_goal": effective})
