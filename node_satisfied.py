from __future__ import annotations

import core_bus as bus


def run(ctx):
    state = ctx.get("state", {})
    effective_goal = state.get("effective_goal", ctx.get("goal", ""))
    effective_goal = f"{effective_goal}\n\n[SATISFIED] Goal complete. Final assessment: {'Success' if not bool(state.get('plan_failed')) and not bool(state.get('last_error')) else 'Failed'}."
    return bus.emit(
        "halt",
        {
            "satisfied": not bool(state.get("plan_failed")) and not bool(state.get("last_error")),
            "last_error": state.get("last_error"),
            "effective_goal": effective_goal,
        },
    )
