"""reflect: diagnose a failure and choose retry / replan / escalate / give_up (record_type=diagnosis)."""
retries = int(state.get("retries", 0) or 0) + 1
replans = int(state.get("replan_count", 0) or 0)
max_attempts = wiring_limit("max_attempts", 7, wiring)
max_replans = wiring_limit("max_replans", 3, wiring)

r = call_node()
parsed = r["parsed"]
if not r["record_ok"]:
    patch = {
        "last_diagnosis": "reflector returned invalid diagnosis record",
        "suggestion": preview_text(r["content"]),
        "last_error": "reflect: invalid diagnosis record: " + preview_text(r["content"]),
        "retries": retries,
    }
    signals = ["escalate" if retries >= max_attempts else "retry"]
else:
    data = (parsed or {}).get("data") or {}
    patch = {
        "last_diagnosis": data.get("diagnosis", ""),
        "suggestion": data.get("suggestion", ""),
        "retries": retries,
        "last_error": "",
    }
    if retries >= max_attempts:
        signals = ["escalate"]
    elif data.get("should_replan") and replans < max_replans:
        patch.update({"replan_count": replans + 1, "replanning": True, "planner_retries": 0})
        signals = ["replan"]
    else:
        signals = ["retry"]
