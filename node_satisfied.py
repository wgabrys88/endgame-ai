from __future__ import annotations

import core_bus as bus


DATASHEET = bus.datasheet(
    "node_satisfied",
    kind="halt_gate",
    inputs=["plan_complete", "last_reflection", "last_error", "effective_goal"],
    signals=["halt"],
    writes=["satisfied", "last_error", "effective_goal"],
    record_type=None,
)


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
