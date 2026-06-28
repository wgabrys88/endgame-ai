"""self_modify: rewrite the organism's own wiring (record_type=wiring_patch).

This is how an unconstrained organism changes strategy or even how it thinks — e.g. it may
decide to route its own cognition through a different brain by patching model.transport,
after arranging the world for it. The engine reloads wiring + rebinds the brain live when
_wiring_changed is set."""
count = int(state.get("self_modify_count", 0) or 0)
max_count = wiring_limit("max_self_modify", 6, wiring)

if count >= max_count:
    patch = {"self_modify_exhausted": True, "last_error": f"self_modify: limit reached ({count}/{max_count})"}
    signals = ["modify_failed"]
else:
    r = call_node()
    parsed = r["parsed"]
    if not r["record_ok"]:
        patch = {"last_error": "self_modify: invalid wiring_patch record: " + preview_text(r["content"])}
        signals = ["modify_failed"]
    else:
        try:
            op, payload = apply_wiring_patch(wiring, parsed)
            errs = validate_wiring(wiring)
            if errs:
                patch = {"last_error": "self_modify: invalid wiring after patch: " + "; ".join(errs[:5])}
                signals = ["modify_failed"]
            else:
                save_wiring(wiring)
                patch = {"self_modify_op": op, "self_modify_payload": payload,
                         "self_modify_count": count + 1, "_wiring_changed": True,
                         "retries": 0, "last_error": ""}
                signals = ["modified"]
        except Exception as e:
            patch = {"last_error": f"self_modify: {type(e).__name__}: {e}"}
            signals = ["modify_failed"]
