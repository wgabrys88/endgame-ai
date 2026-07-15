"""[node_spawn] — Thou shalt consume a named [spawn_subgoal]; run one child bounded in depth, and fold its final testimony back for reflection as [child_testimony]."""
import core_bus as bus
import core_loader as loader


def run(ctx):
    """Beget a child organism where recursion pays. Wires cap_spawn into the wheel.

    node_reflect routes here when it judges the goal warrants a sub-organism. This
    node invokes the cap_spawn capability (which runs a depth-gated child organism
    and folds the child's final interpretation table back as child_testimony), then
    forwards the child's counsel into the wheel as "spawned".
    """
    cap = loader.load("cap", "cap_spawn", ctx["wiring"])
    out = cap.run(ctx)
    return bus.emit("spawned", {**dict(out.patch), "spawn_subgoal": None, "_reload_wiring": True})
