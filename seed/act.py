"""act: execute one desktop verb chosen by the mind, then hand back to the mind."""

detail = ctx.state.get("mind_detail", {}) or {}
verb = str(detail.get("verb", "")).strip()
target = str(detail.get("target", "") or "")
value = str(detail.get("value", "") or "")

if not verb:
    log("no verb supplied; back to mind")
    emit("mind", last_error="act: no verb")
else:
    outcome = ctx.hands.act(verb, target, value)
    title = ctx.hands.focused_title()
    ok = not str(outcome).upper().startswith("FAILED")
    hist = ctx.state.setdefault("history", [])
    hist.append({"verb": verb, "target": target, "value": value[:80], "outcome": str(outcome)[:200], "ok": ok})
    ctx.state["history"] = hist[-40:]
    ctx.state["last_outcome"] = str(outcome)
    ctx.state["focused_title"] = title
    log(f"{verb} {target} -> {str(outcome)[:120]}")
    # Always return to the mind: it re-observes and verifies on its own with fresh eyes.
    emit("mind", last_error="" if ok else str(outcome))
