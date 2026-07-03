"""error: mechanical error recovery node."""
from __future__ import annotations

import bus


DATASHEET = bus.datasheet(
    "error",
    kind="mechanical_recovery_router",
    inputs=["last_node", "last_error", "current_step"],
    signals=["planner", "reflect", "halt"],
    writes=["error_handled", "recovery"],
    record_type=None,
)


def run(ctx):
    state = ctx.get("state", {})
    error_info = {
        "failed_node": state.get("last_node"),
        "error": state.get("last_error"),
        "tick": state.get("tick"),
        "signal": state.get("last_signal"),
    }

    print(f"[ERROR NODE] Failed node: {error_info['failed_node']}, Error: {error_info['error']}")

    recovery = "reflect" if state.get("current_step") else "planner"
    return bus.emit(recovery, {"error_handled": error_info, "recovery": recovery})
