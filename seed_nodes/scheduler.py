"""scheduler: pick the next plan step, or finish when the plan is exhausted."""
steps = state.get("plan", []) or []
idx = int(state.get("step", 0) or 0)
if idx >= len(steps):
    patch = {"plan_complete": True}
    signals = ["plan_complete"]
else:
    step = steps[idx]
    patch = {"current_step": step, "step_goal": step.get("description", str(step))}
    signals = ["step_ready"]
