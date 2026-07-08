import core_bus as bus


def run(ctx):
    state = ctx.get("state", {})
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
