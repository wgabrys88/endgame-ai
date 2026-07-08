import core_bus as bus


def run(ctx):
    state = ctx.get("state", {})
    info = {"failed_node": state.get("last_node"), "error": state.get("last_error"), "tick": state.get("tick"), "signal": state.get("last_signal"), "failure": state.get("last_failure", {})}
    print(f"[ERROR NODE] Failed node: {info['failed_node']}, Error: {info['error']}")
    error = str(state.get("last_error") or "")
    effective = bus.current_goal(state, ctx)
    if not bool((state.get("fresh_observation") or {}).get("desktop_tree_text")) and (state.get("last_node") in {"node_observe", "node_planner"} or "fresh_observation missing" in error):
        return bus.emit("halt", {"error_handled": info, "recovery": "halt", "plan_failed": True, "last_error": error, "last_failure": state.get("last_failure", {}), "effective_goal": effective + f"\n\n[ERROR] Fatal: No observation data for {info['failed_node']}. Halting."})
    recovery = "reflect" if state.get("current_step") else "planner"
    return bus.emit(recovery, {"error_handled": info, "recovery": recovery, "last_failure": state.get("last_failure", {}), "effective_goal": effective + f"\n\n[ERROR] Recovered from {info['failed_node']} error: {error[:100]}. Routing to {recovery}."})
