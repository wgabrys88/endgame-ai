from __future__ import annotations

import core_bus as bus


DATASHEET = bus.datasheet(
    "node_error",
    kind="mechanical_recovery_router",
    inputs=["last_node", "last_error", "current_step", "effective_goal"],
    signals=["planner", "reflect", "halt"],
    writes=["error_handled", "recovery", "effective_goal"],
    record_type=None,
)


def run(ctx):
    state = ctx.get("state", {})
    error_info = {
        "failed_node": state.get("last_node"),
        "error": state.get("last_error"),
        "tick": state.get("tick"),
        "signal": state.get("last_signal"),
        "failure": state.get("last_failure", {}),
    }

    print(f"[ERROR NODE] Failed node: {error_info['failed_node']}, Error: {error_info['error']}")

    error_text = str(state.get("last_error") or "")
    has_observation = bool((state.get("fresh_observation") or {}).get("desktop_tree_text"))
    effective_goal = state.get("effective_goal", ctx.get("goal", ""))
    
    if not has_observation and (
        state.get("last_node") in {"node_observe", "node_planner"}
        or "fresh_observation missing" in error_text
    ):
        recovery = "halt"
        effective_goal = f"{effective_goal}\n\n[ERROR] Fatal: No observation data for {error_info['failed_node']}. Halting."
        return bus.emit(
            recovery,
            {
                "error_handled": error_info,
                "recovery": recovery,
                "plan_failed": True,
                "last_error": error_text,
                "last_failure": state.get("last_failure", {}),
                "effective_goal": effective_goal,
            },
        )

    recovery = "reflect" if state.get("current_step") else "planner"
    effective_goal = f"{effective_goal}\n\n[ERROR] Recovered from {error_info['failed_node']} error: {error_text[:100]}. Routing to {recovery}."
    return bus.emit(recovery, {"error_handled": error_info, "recovery": recovery, "last_failure": state.get("last_failure", {}), "effective_goal": effective_goal})
