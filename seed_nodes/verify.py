"""verify: judge whether the current step's DONE_WHEN INTENT is satisfied (record_type=verdict)."""
r = call_node()
parsed = r["parsed"]
if not r["record_ok"]:
    patch = {"last_error": "verify: invalid verdict record: " + preview_text(r["content"])}
    signals = ["step_denied"]
else:
    data = parsed.get("data") or {}
    confirmed = bool(data.get("confirmed"))
    patch = {"verify_evidence": data.get("evidence", ""), "verify_reason": data.get("reason", "")}
    if confirmed:
        patch.update({"step": int(state.get("step", 0) or 0) + 1, "retries": 0, "last_error": ""})
        signals = ["step_confirmed"]
    else:
        patch["last_error"] = data.get("reason") or "verify: intent not satisfied"
        signals = ["step_denied"]
