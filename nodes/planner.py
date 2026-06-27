"""LLM planner node."""
try:
    r = call_node(config, state, wiring)
    parsed = r.get("parsed")
    patch = dict(r.get("patch") or {})
    if not parsed or parsed.get("record_type") not in (None, wiring.get("reasoning", {}).get("expected_record_type", {}).get("planner", "task")):
        raise ValueError("planner parse failed")
    steps = (parsed.get("data") or {}).get("steps") or []
    if not steps:
        retries = int(state.get("planner_retries", 0) or 0) + 1
        patch.update({"planner_retries": retries, "last_error": wiring_error("planner_empty", wiring)})
        signals = ["plan_failed" if retries >= wiring_limit("planner_retries", 3, wiring) else "retry_plan"]
    else:
        patch.update({
            "plan": steps,
            "step": 0,
            "retries": 0,
            "history": [] if not state.get("replanning") else list(state.get("history", [])),
            "planner_retries": 0,
            "last_error": "",
            "plan_failed": False,
            "replanning": False,
            "_planned_goal": state.get("goal", ""),
        })
        signals = ["plan_ready"]
except Exception as e:
    retries = int(state.get("planner_retries", 0) or 0) + 1
    patch = {"planner_retries": retries, "last_error": f"planner: {e}"}
    signals = ["plan_failed" if retries >= wiring_limit("planner_retries", 3, wiring) else "retry_plan"]
