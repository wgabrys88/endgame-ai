"""[node_satisfied] — the terminal rest. THOU EXPECTEST: the [witnessed_deeds], the [effective_goal], the [tick]. Thou emittest 'halt' with a summary of completion, once the whole goal is witnessed accomplished."""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    effective = bus.append_narrative(state["effective_goal"], "\n\n[SATISFIED] The whole goal is witnessed accomplished. The organism resteth, and it is well.", root_goal=state.get("goal", ""))
    return bus.emit("halt", {"satisfied": True, "completion": {"witnessed_deeds": len(state.get("witnessed_deeds") or []), "tick": state.get("tick")}, "last_error": None, "effective_goal": effective})
