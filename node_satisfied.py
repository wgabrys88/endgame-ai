import core_bus as bus


def run(ctx):
    state = ctx.get("state", {})
    ok = not bool(state.get("plan_failed")) and not bool(state.get("last_error"))
    effective = state.get("effective_goal", ctx.get("goal", "")) + f"\n\n[SATISFIED] Goal complete. Final assessment: {'Success' if ok else 'Failed'}."
    return bus.emit("halt", {"satisfied": ok, "last_error": state.get("last_error"), "effective_goal": effective})
