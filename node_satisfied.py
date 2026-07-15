"""[node_satisfied] — the terminal rest. THOU EXPECTEST: the [witnessed_deed_count], the [tick]. Thou emittest 'halt' with a summary of completion, once the whole goal is witnessed accomplished."""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    return bus.emit("halt", {"satisfied": True, "completion": {"witnessed_deed_count": int(state.get("witnessed_deed_count") or 0), "tick": state.get("tick")}})
