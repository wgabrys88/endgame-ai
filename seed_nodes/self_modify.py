"""self_modify: rewrite the organism's own wiring (record_type=wiring_patch).

A failed self-modification is itself evidence. The node now counts failed attempts and
can retry its own patch generation before emitting modify_failed. There is no fallback
transport; the same selected brain must repair the patch or fail hard.
"""
count = int(state.get("self_modify_count", 0) or 0)
failures = int(state.get("self_modify_failures", 0) or 0)
max_count = wiring_limit("max_self_modify", 6, wiring)


def _failed(message):
    next_failures = failures + 1
    exhausted = next_failures >= max_count
    return ({
        "self_modify_failures": next_failures,
        "self_modify_exhausted": exhausted,
        "last_error": message,
    }, ["modify_failed" if exhausted else "modify_retry"])


if count >= max_count:
    patch = {"self_modify_exhausted": True, "last_error": f"self_modify: success limit reached ({count}/{max_count})"}
    signals = ["modify_failed"]
else:
    r = call_node()
    parsed = r["parsed"]
    if not r["record_ok"]:
        patch, signals = _failed("self_modify: invalid wiring_patch record: " + preview_text(r["content"]))
    else:
        try:
            op, payload = apply_wiring_patch(wiring, parsed)
            errs = validate_wiring(wiring)
            if errs:
                patch, signals = _failed("self_modify: invalid wiring after patch: " + "; ".join(errs[:5]))
            else:
                save_wiring(wiring)
                patch = {
                    "self_modify_op": op,
                    "self_modify_payload": payload,
                    "self_modify_count": count + 1,
                    "self_modify_failures": 0,
                    "_wiring_changed": True,
                    "retries": 0,
                    "last_error": "",
                }
                signals = ["modified"]
        except Exception as e:
            patch, signals = _failed(f"self_modify: {type(e).__name__}: {e}")
