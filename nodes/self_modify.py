"""Self-modify by applying an LLM-generated wiring/code patch."""
count = int(state.get("self_modify_count", 0) or 0)
max_count = wiring_limit("max_self_modify", 3, wiring)
if count >= max_count:
    patch = {"self_modify_exhausted": True, "last_error": f"self_modify limit exhausted ({count}/{max_count})"}
    signals = ["modify_failed"]
else:
    try:
        current = load_wiring()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        atomic_write_json(runtime.WIRING_PATH.with_name(f"{runtime.WIRING_PATH.stem}.backup.{stamp}.json"), current, indent=2)
        r = call_node(config, state, current)
        parsed = r.get("parsed")
        patch = dict(r.get("patch") or {})
        expected = current.get("reasoning", {}).get("expected_record_type", {}).get("self_modify", "wiring_patch")
        if not parsed or parsed.get("record_type") != expected:
            patch["last_error"] = wiring_error("self_modify_invalid", current)
            signals = ["modify_failed"]
        else:
            op, payload = apply_wiring_patch(current, parsed)
            errs = validate_wiring(current)
            if errs:
                patch["last_error"] = wiring_error("self_modify_invalid", current) + ": " + "; ".join(errs[:5])
                signals = ["modify_failed"]
            else:
                save_wiring(current)
                patch.update({"self_modify_op": op, "self_modify_payload": payload, "self_modify_count": count + 1})
                signals = ["modified"]
    except Exception as e:
        patch = {"last_error": f"self_modify: {type(e).__name__}: {e}"}
        signals = ["modify_failed"]
