"""planner: decompose the goal into an ordered intent-based plan (record_type=task)."""
r = call_node()
parsed = r["parsed"]
if not r["record_ok"]:
    retries = int(state.get("planner_retries", 0) or 0) + 1
    patch = {"planner_retries": retries, "last_error": "planner: invalid task record: " + preview_text(r["content"])}
    signals = ["plan_failed" if retries >= wiring_limit("planner_retries", 3, wiring) else "retry_plan"]
else:
    steps = (parsed.get("data") or {}).get("steps") or []
    if not steps:
        retries = int(state.get("planner_retries", 0) or 0) + 1
        patch = {"planner_retries": retries, "last_error": "planner: empty plan"}
        signals = ["plan_failed" if retries >= wiring_limit("planner_retries", 3, wiring) else "retry_plan"]
    else:
        patch = {
            "plan": steps, "step": 0, "retries": 0, "planner_retries": 0,
            "replan_count": state.get("replan_count", 0), "last_error": "",
            "history": [] if not state.get("replanning") else list(state.get("history", [])),
            "replanning": False,
        }
        signals = ["plan_ready"]
