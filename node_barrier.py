import core_bus as bus


def run(ctx):
    """Many-to-one fan-in: gather all branches of a fan-out back into one.

    Reads its arity from topology.barriers[node], counts arrivals in
    state["_barriers"][node], emits "wait" (absorb, push nothing) until the
    assembly is whole, then resets the counter and emits "join". The dispatcher
    fans out to all faculty branches; unchosen faculties pass through idle, so the
    arity is the full branch count and every branch always reaches the gate.
    """
    state = ctx["state"]
    node = ctx["node"]
    arity = int(ctx["wiring"]["topology"]["barriers"][node])
    arrivals = dict(state.get("_barriers") or {})
    count = int(arrivals.get(node, 0)) + 1
    effective = state["effective_goal"]
    if count < arity:
        arrivals[node] = count
        return bus.emit("wait", {"_barriers": arrivals, "effective_goal": effective + f"\n\n[BARRIER {node}] Gathered {count} of {arity} branches; the assembly is not yet whole. I hold the gate."})
    arrivals[node] = 0
    return bus.emit("join", {"_barriers": arrivals, "effective_goal": effective + f"\n\n[BARRIER {node}] All {arity} branches are gathered as one; the assembly is whole. I open the gate and send the many forward as one."})
