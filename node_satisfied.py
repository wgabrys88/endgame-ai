"""node_satisfied — terminal rest. EXPECTS: completed_steps, effective_goal, tick. Emits 'halt' with a completion summary once every step is verified."""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    effective = bus.append_narrative(state["effective_goal"], "\n\n[SATISFIED] Every step in the current complete plan was verified. The organism rests successfully.", root_goal=state.get("goal", ""))
    return bus.emit("halt", {"satisfied": True, "completion": {"verified_steps": len(state.get("completed_steps") or []), "tick": state.get("tick")}, "last_error": None, "effective_goal": effective})
