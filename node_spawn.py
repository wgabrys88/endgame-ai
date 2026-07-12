"""node_spawn — begets a bounded child organism for a sub-goal. EXPECTS: effective_goal (the inherited narrative). Runs the child via cap_spawn and emits 'spawned', folding the child's final narrative back."""
import core_bus as bus
import core_loader as loader


def run(ctx):
    """Beget a child organism where recursion pays. Wires cap_spawn into the wheel.

    node_reflect routes here when it judges the goal warrants a sub-organism. This
    node invokes the cap_spawn capability (which runs a depth-gated child organism
    on the inherited narrative and folds the child's final narrative back), then
    forwards the child's counsel into the wheel as "spawned".
    """
    cap = loader.load("cap", "cap_spawn", ctx["wiring"])
    out = cap.run(ctx)
    return bus.emit("spawned", dict(out.patch))
