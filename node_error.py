import core_bus as bus
import core_loader as loader


def run(ctx):
    state = ctx.get("state", {})
    info = {"failed_node": state.get("last_node"), "error": state.get("last_error"), "tick": state.get("tick"), "signal": state.get("last_signal"), "failure": state.get("last_failure", {})}
    print(f"[ERROR NODE] Failed node: {info['failed_node']}, Error: {info['error']}")
    error = str(state.get("last_error") or "")
    effective = state["effective_goal"]
    failed_base, _ = loader.split_instance(str(state["last_node"]))
    if not bool((state.get("observation") or {}).get("desktop_tree_text")) and (failed_base in {"node_observe", "node_planner"} or "observation missing" in error):
        return bus.emit("guidance", {"error_handled": info, "recovery": "guidance", "plan_failed": True, "last_error": error, "last_failure": state.get("last_failure", {}), "effective_goal": effective + f"\n\n[ERROR] No observation data for {info['failed_node']}. Re-entering the wheel through guidance and observation."})
    recovery = "reflect" if state.get("current_step") else "planner"
    return bus.emit(recovery, {"error_handled": info, "recovery": recovery, "last_failure": state.get("last_failure", {}), "effective_goal": effective + f"\n\n[ERROR] Recovered from {info['failed_node']} error: {error}. Routing to {recovery}."})
