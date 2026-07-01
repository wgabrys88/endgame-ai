from __future__ import annotations


def run(ctx):
    """Scheduler: pick the next plan step by index, or finish when plan is exhausted."""
    state = ctx.get("state", {})
    plan = state.get("plan", [])
    step_idx = int(state.get("step", 0) or 0)
    
    if step_idx >= len(plan):
        return "plan_complete", {"plan_complete": True, "current_step": None}
    
    step = plan[step_idx]
    return "step_ready", {"current_step": step, "step_goal": step.get("description", str(step)), "step": step_idx}