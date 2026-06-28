"""mind: the organism's decision-maker. Looks at goal+screen+memory and decides the
next move. Routes to other nodes by emitting their name as the signal."""

# Gather the current situation.
screen = ctx.hands.observe()
ctx.state["screen"] = screen
goal = ctx.goal
catalog = ctx.catalog()
mem = json.dumps(ctx.memory, ensure_ascii=False)[:1500]
recent = " | ".join(ctx.narration[-6:])

system = (
    "You are the mind of a living desktop organism that operates a real computer as a "
    "human replacement. You are stateless; your own prior reasoning is fed back to you so "
    "you can continue your train of thought. Decide the SINGLE next move and reply with "
    "exactly one JSON object, no prose, no markdown.\n\n"
    "REPLY SCHEMA:\n"
    '{"move":"act|grow|rest","why":"one sentence","detail":{...}}\n'
    "- act: perform a desktop action now. detail = {\"verb\":\"click|write|press|hotkey|"
    "focus|open_url|scroll|wait|launch\",\"target\":\"visible id/token/window title or empty\","
    "\"value\":\"text/url/key/ms or empty\"}.\n"
    "- grow: you lack a capability and want to write a new node module to gain it. "
    "detail = {\"name\":\"node_name\",\"purpose\":\"what it should do\"}.\n"
    "- rest: the goal is satisfied, or there is genuinely nothing worth doing now.\n\n"
    "RULES: Only use element ids/tokens visible in SCREEN; never invent them. Prefer one "
    "concrete action. If you have no goal, you MAY still choose a small useful or curious "
    "action on your own initiative, or rest. Choose grow only when no existing node/verb "
    "can achieve the next step."
)
user = (
    f"GOAL: {goal or '(none — act on your own initiative or rest)'}\n\n"
    f"AVAILABLE NODES:\n{catalog}\n\n"
    f"MEMORY: {mem}\n\n"
    f"RECENT: {recent}\n\n"
    f"SCREEN:\n{screen[:6000]}"
)

content, parsed = ctx.think(system, user)
if not parsed or "move" not in parsed:
    log("could not parse a decision; resting briefly")
    emit("rest", last_error="mind: unparseable decision: " + content[:200])
else:
    move = str(parsed.get("move", "rest")).lower()
    ctx.state["mind_detail"] = parsed.get("detail", {})
    ctx.state["mind_why"] = parsed.get("why", "")
    log(f"decision: {move} — {parsed.get('why','')}")
    if move in ("act", "grow", "rest"):
        emit(move)
    else:
        emit("rest", last_error=f"mind: unknown move {move}")
