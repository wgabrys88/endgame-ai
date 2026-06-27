"""Reflect on failure and choose retry/replan/escalate/give_up."""
retries = int(state.get("retries", 0) or 0) + 1
replans = int(state.get("replan_count", 0) or 0)
max_attempts = wiring_limit("max_attempts", 7, wiring)
max_replans = wiring_limit("max_replans", 3, wiring)
try:
    r = call_node(config, state, wiring)
    parsed = r.get("parsed")
    patch = dict(r.get("patch") or {})
    data = (parsed or {}).get("data") or {}
    patch.update({"last_diagnosis": data.get("diagnosis", ""), "suggestion": data.get("suggestion", ""), "retries": retries})
    if retries >= max_attempts:
        signals = ["escalate"]
    elif data.get("should_replan") and replans < max_replans:
        patch.update({"replan_count": replans + 1, "replanning": True, "planner_retries": 0})
        signals = ["replan"]
    else:
        signals = ["retry"]
except Exception as e:
    patch = {"last_error": f"reflect: {e}", "retries": retries}
    if retries >= max_attempts:
        signals = ["give_up"]
    else:
        signals = ["retry"]
