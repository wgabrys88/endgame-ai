"""grow: write a brand-new node module to gain a capability the organism lacks.

This is where self-evolution happens. The mind asked for a node by name+purpose; here
the brain authors the actual Python, then ctx.write_node() — the single safety point —
either writes it (autonomous) or refuses (guarded). On success the new node exists for
the rest of the run and the mind can route to it immediately."""

detail = ctx.state.get("mind_detail", {}) or {}
name = str(detail.get("name", "")).strip()
purpose = str(detail.get("purpose", "")).strip()

if not name:
    emit("mind", last_error="grow: no node name")
else:
    system = (
        "You write a single Python node module for a living desktop organism. The module is "
        "executed directly in a namespace containing: ctx (organism context), emit(signal, **patch), "
        "log(msg), and the stdlib modules time, json, re, os, pathlib. It must call emit() with a "
        "signal string; emit('mind', ...) hands control back to the decision-maker. Through ctx you "
        "can use: ctx.hands.observe(), ctx.hands.act(verb,target,value), ctx.hands.focused_title(), "
        "ctx.think(system,user)->(content,parsed), ctx.memory (dict), ctx.state (dict), ctx.goal. "
        "Reply with exactly one JSON object: {\"code\":\"<the full python module source>\"}. No prose."
    )
    user = f"NODE NAME: {name}\nPURPOSE: {purpose}\nGOAL CONTEXT: {ctx.goal}\n\nWrite the module now."
    content, parsed = ctx.think(system, user)
    code = (parsed or {}).get("code") if parsed else None
    if not code:
        emit("mind", last_error="grow: brain did not return code: " + content[:200])
    else:
        ok, msg = ctx.write_node(name, code)
        if ok:
            emit("mind", last_error="", grew_node=name)
        else:
            # Guarded mode (or invalid): the proposal is surfaced; rest so a human can decide.
            emit("rest", last_error=msg)
