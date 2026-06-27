"""Select the next plan step."""
steps = state.get("plan", []) or []
idx = int(state.get("step", 0) or 0)
if idx >= len(steps):
    patch = {}
    signals = ["plan_complete"]
else:
    step = steps[idx]
    patch = {"current_step": step, "step_goal": step.get("description", str(step))}
    signals = ["step_ready"]
