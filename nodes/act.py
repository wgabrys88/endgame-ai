"""Act node: ask LLM for actions, validate contracts, guard, execute verbs."""
history = list(state.get("history", []) or [])
act_cfg = wiring.get("act", {}) or {}
valid = set(act_cfg.get("valid_conclusions", ["EXECUTE", "CANNOT"]))
reject = set(act_cfg.get("reject_conclusions", ["DONE", "FINISHED", "SUCCESS", "VERIFY"]))
try:
    r = call_node(config, state, wiring)
    parsed = r.get("parsed")
    patch = dict(r.get("patch") or {})
    if not parsed:
        patch["last_error"] = wiring_error("parse_failed", wiring) + ": " + preview_text(r.get("content", ""))
        signals = ["act_failed"]
    else:
        data = parsed.get("data") or {}
        conclusion = data.get("conclusion", "")
        actions = data.get("actions") or []
        if conclusion in reject:
            entry = {"attempt": len(history) + 1, "action": f"{conclusion} rejected", "outcome": "executor cannot emit completion verdicts"}
            patch.update({"last_error": wiring_error("act_done_rejected", wiring), "history": history + [entry]})
            signals = ["act_failed"]
        elif conclusion == "CANNOT":
            entry = {"attempt": len(history) + 1, "action": "CANNOT", "outcome": "LLM cannot proceed"}
            patch.update({"last_error": wiring_error("act_cannot", wiring), "history": history + [entry]})
            signals = ["act_failed"]
        elif conclusion not in valid or not actions:
            patch["last_error"] = wiring_error("act_bad_conclusion", wiring, conclusion=conclusion)
            signals = ["act_failed"]
        else:
            actions = normalize_actions_from_wiring(state, actions, act_cfg)
            allowed_verbs = set((wiring.get("verbs") or {}).keys()) | {"remember", "llm_request", "llm_wait_response", "copy_codebase", "browser_ai_handoff"}
            bad_shape = next((a for a in actions if not isinstance(a, dict) or not str(a.get("verb", "")).strip()), None)
            unknown = next((str(a.get("verb", "")).strip() for a in actions if isinstance(a, dict) and str(a.get("verb", "")).strip() not in allowed_verbs), "")
            if bad_shape is not None:
                patch["last_error"] = wiring_error("act_bad_action_shape", wiring)
                signals = ["act_failed"]
            elif unknown:
                patch["last_error"] = wiring_error("act_unknown_verb", wiring, verb=unknown)
                signals = ["act_failed"]
            else:
                rule = evaluate_rules("act", {**state, "last_actions_raw": actions}, wiring)
                if rule and rule.get("verdict") == "reject":
                    reason = rule.get("description") or "action chain rejected"
                    entry = {"attempt": len(history) + 1, "action": "; ".join(f"{a.get('verb','')} {a.get('target','')}" for a in actions), "outcome": f"BLOCKED: {reason}"}
                    patch.update({"last_error": reason, "history": history + [entry]})
                    signals = ["act_failed"]
                else:
                    memory = dict(state.get("memory", {}) or {})
                    outcomes = []
                    ok_all = True
                    for a in actions:
                        verb = str(a.get("verb", "")).strip()
                        target = str(a.get("target", "") or "")
                        value = str(a.get("value", "") or "")
                        if verb == "remember":
                            ok, memory, out = apply_memory_action(memory, target, value)
                        elif verb == "llm_wait_response":
                            ok, text = wait_llm_response()
                            out = text if ok else "FAILED: " + text
                            if ok:
                                memory[wiring.get("runtime", {}).get("llm_response_memory_key", "llm_response")] = text
                        elif verb == "copy_codebase":
                            ok, info = copy_codebase_to_clipboard()
                            out = info.get("message", "copied")
                            memory["codebase_snapshot"] = info
                        elif verb == "browser_ai_handoff":
                            out = execute_verb(verb, target, value)
                            ok = not str(out).upper().startswith("FAILED")
                            if ok:
                                memory["grok_response"] = str(out).replace("browser_ai_response:", "", 1).strip()
                                memory[wiring.get("runtime", {}).get("llm_response_memory_key", "llm_response")] = memory["grok_response"]
                        else:
                            out = execute_verb(verb, target, value)
                            ok = not str(out).upper().startswith("FAILED")
                        outcomes.append(out)
                        ok_all = ok_all and ok
                        time.sleep(int(wiring.get("runtime", {}).get("action_chain_delay_ms", 120) or 0) / 1000.0)
                    action_label = "; ".join(f"{a.get('verb','')} {a.get('target','')}".strip() for a in actions)
                    outcome_text = " | ".join(outcomes)
                    entry = {"attempt": len(history) + 1, "action": action_label, "outcome": outcome_text}
                    patch.update({
                        "last_actions": actions,
                        "last_actions_raw": actions,
                        "last_outcome": outcome_text,
                        "history": (history + [entry])[-wiring_limit("history_depth", 40, wiring):],
                        "memory": memory,
                        "post_action_title": get_focused_title(),
                        "last_error": "" if ok_all else outcome_text,
                    })
                    signals = ["acted" if ok_all else "act_failed"]
except Exception as e:
    patch = {"last_error": f"act: {type(e).__name__}: {e}"}
    signals = ["act_failed"]
