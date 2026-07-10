import core_bus as bus


def run(ctx):
    """Gather the full dispatch fan-out, then release the wired continuation signal."""
    state = ctx["state"]
    node = ctx["node"]
    arity = int(ctx["wiring"]["topology"]["barriers"][node])
    arrivals = dict(state.get("_barriers") or {})
    count = int(arrivals.get(node, 0)) + 1
    arrivals[node] = count if count < arity else 0
    signal = "wait" if count < arity else state["_barrier_release_signal"]
    return bus.emit(signal, {"_barriers": arrivals})
