"""[node_scheduler] — Thou choosest the step at hand out of the plan. THOU EXPECTEST: the plan (with its [intent] list), the [step] index, and the [effective_goal]. Thou emittest 'step_ready' with the chosen [current_step], or 'goal_complete' when the plan is spent."""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    plan_obj = state.get("plan", {})
    plan = plan_obj.get("intent", []) if isinstance(plan_obj, dict) else plan_obj
    if not isinstance(plan, list):
        raise RuntimeError(f"scheduler expected plan.intent list, got {type(plan).__name__}")
    idx = int(state.get("step", 0) or 0)
    if idx >= len(plan):
        return bus.emit("goal_complete", {"plan_complete": True, "current_step": None, "action_frame": None})
    step = plan[idx]
    if not isinstance(step, dict) or not isinstance(step.get("description"), str) or not isinstance(step.get("done_when"), str):
        raise RuntimeError(f"scheduler step {idx} must contain string description and done_when")
    effective = bus.append_narrative(state["effective_goal"], f"\n\n[SCHEDULER] Current step: {step['description']}. Complete when: {step['done_when']}.", root_goal=state.get("goal", ""))
    return bus.emit("step_ready", {"current_step": step, "step_goal": step["description"], "step": idx, "action_frame": None, "effective_goal": effective})
