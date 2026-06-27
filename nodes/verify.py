"""Verify current step."""
probe_state = dict(state)
rule = evaluate_rules("verify", probe_state, wiring)
if rule:
    verdict = rule.get("verdict")
    if verdict == "confirm":
        step = int(state.get("step", 0) or 0) + 1
        patch = {"step": step, "retries": 0, "last_error": "", "verified_by_rule": rule.get("id"), "history": list(state.get("history", [])) + [{"attempt": len(state.get("history", [])) + 1, "action": "verify", "outcome": "confirmed:" + str(rule.get("id"))}]}
        for k in wiring.get("reasoning", {}).get("clear_on_step_confirm", []):
            if isinstance(patch.get("reasoning"), dict):
                patch["reasoning"].pop(k, None)
        signals = ["step_confirmed"]
    else:
        patch = {"last_error": rule.get("description") or "verify denied", "verified_by_rule": rule.get("id")}
        signals = ["step_denied"]
else:
    try:
        r = call_node(config, state, wiring)
        parsed = r.get("parsed")
        patch = dict(r.get("patch") or {})
        data = (parsed or {}).get("data") or {}
        confirmed = bool(data.get("confirmed"))
        patch.update({"verify_evidence": data.get("evidence", ""), "verify_reason": data.get("reason", "")})
        if confirmed:
            patch.update({"step": int(state.get("step", 0) or 0) + 1, "retries": 0, "last_error": ""})
            signals = ["step_confirmed"]
        else:
            patch["last_error"] = data.get("reason") or "verify denied"
            signals = ["step_denied"]
    except Exception as e:
        patch = {"last_error": f"verify: {e}"}
        signals = ["step_denied"]
