"""act: the only role that emits actions. Ask the actor for an intent record
(conclusion EXECUTE/CANNOT + verb actions), validate the contract, then execute."""
history = list(state.get("history", []) or [])
act_cfg = wiring.get("act", {}) or {}
valid = set(act_cfg.get("valid_conclusions", ["EXECUTE", "CANNOT"]))
reject = set(act_cfg.get("reject_conclusions", ["DONE", "FINISHED", "SUCCESS", "VERIFY"]))
allowed_verbs = set((wiring.get("verbs") or {}).keys())

r = call_node()
parsed = r["parsed"]
patch = {}

if not r["record_ok"]:
    patch["last_error"] = "act: invalid action record: " + preview_text(r["content"])
    signals = ["act_failed"]
else:
    data = parsed.get("data") or {}
    conclusion = data.get("conclusion", "")
    act_list = data.get("actions") or []
    unknown = next((str(a.get("verb", "")).strip() for a in act_list
                    if isinstance(a, dict) and str(a.get("verb", "")).strip() not in allowed_verbs), "")
    bad_shape = next((a for a in act_list if not isinstance(a, dict) or not str(a.get("verb", "")).strip()), None)

    if conclusion in reject:
        patch.update({"last_error": "act: executor cannot emit completion verdicts",
                      "history": history + [{"attempt": len(history) + 1, "action": f"{conclusion} rejected", "outcome": "verifier decides completion"}]})
        signals = ["act_failed"]
    elif conclusion == "CANNOT":
        patch.update({"last_error": "act: actor reports CANNOT proceed",
                      "history": history + [{"attempt": len(history) + 1, "action": "CANNOT", "outcome": "actor cannot proceed"}]})
        signals = ["act_failed"]
    elif conclusion not in valid or not act_list:
        patch["last_error"] = f"act: bad conclusion '{conclusion}' or empty actions"
        signals = ["act_failed"]
    elif bad_shape is not None:
        patch["last_error"] = "act: malformed action (missing verb)"
        signals = ["act_failed"]
    elif unknown:
        patch["last_error"] = f"act: unknown verb '{unknown}'"
        signals = ["act_failed"]
    else:
        memory = dict(state.get("memory", {}) or {})
        outcomes = []
        ok_all = True
        for a in act_list:
            verb = str(a.get("verb", "")).strip()
            target = str(a.get("target", "") or "")
            value = str(a.get("value", "") or "")
            if verb == "remember":
                ok, memory, out = apply_memory_action(memory, target, value)
            else:
                out = execute_verb(verb, target, value)
                ok = not str(out).upper().startswith("FAILED")
            outcomes.append(out)
            ok_all = ok_all and ok
            time.sleep(int(wiring.get("limits", {}).get("action_chain_delay_ms", 120) or 0) / 1000.0)
        label = "; ".join(f"{a.get('verb','')} {a.get('target','')}".strip() for a in act_list)
        outcome_text = " | ".join(str(o) for o in outcomes)
        patch.update({
            "last_actions": act_list, "last_outcome": outcome_text,
            "history": (history + [{"attempt": len(history) + 1, "action": label, "outcome": outcome_text}])[-wiring_limit("history_depth", 40, wiring):],
            "memory": memory, "post_action_title": get_focused_title(),
            "last_error": "" if ok_all else outcome_text,
        })
        signals = ["acted" if ok_all else "act_failed"]
