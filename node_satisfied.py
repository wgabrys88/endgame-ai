"""[node_satisfied] — Thou expectest [witnessed_deed_count] and [tick] after the whole goal is witnessed."""
import core_bus as bus


def run(ctx):
    state = ctx["state"]
    return bus.emit("halt", {"satisfied": True, "completion": {"witnessed_deed_count": int(state.get("witnessed_deed_count") or 0), "tick": state.get("tick")}})
