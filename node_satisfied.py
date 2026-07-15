"""[node_satisfied] — the terminal rest. THOU EXPECTEST: the [witnessed_deeds], the [tick]. Thou emittest 'halt' with a summary of completion, once the whole goal is witnessed accomplished."""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    return bus.emit("halt", {"satisfied": True, "completion": {"witnessed_deeds": len(state.get("witnessed_deeds") or []), "tick": state.get("tick")}, "last_error": None})
