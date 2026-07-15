"""cap_spawn — the fractal capability: a plugin that runs a CHILD organism.

The literal fractal claim: a node can spawn a whole `core_organism` as a child,
let it pursue the explicit `spawn_subgoal` to its own terminus, and fold the
child's final goal-interpretation table back for the parent as `child_testimony`.
Depth is bounded by `wiring["fractal"]["max_recursion_depth"]`, threaded through
`state["_depth"]`.

Child continuity is ISOLATED in memory: the child runs its own `core_organism.run`
with its own in-memory state and returns its final interpretation table, which the
parent folds back as testimony. Nothing is persisted; parent and child read and may
evolve the same canonical body.

Contract: `run(ctx) -> bus.emit(signal, patch)`. Loaded as kind "cap".
"""
from __future__ import annotations

from typing import Any

import core_bus as bus


def run(ctx: dict[str, Any]):
    import core_organism as organism
    state = ctx["state"]
    w = ctx["wiring"]
    depth = int(state["_depth"])
    max_depth = int(w["fractal"]["max_recursion_depth"])
    child_goal = str(state.get("spawn_subgoal") or "").strip()
    if not child_goal:
        raise RuntimeError("spawn requires a non-empty child sub-goal")
    if depth >= max_depth:
        note = f"The line of descent hath reached its utmost depth {max_depth}; no child was begotten for the sub-goal: {child_goal}."
        return bus.emit("spawned", {"child_testimony": note, "_depth": depth})
    child_seed = {"_depth": depth + 1, "goal_interpretations": {}}
    child_state = organism.run(
        child_goal,
        wiring_path=str(w["_source_path"]),
        _seed=child_seed,
    )
    child_table = bus.render_interpretation_table(child_goal, child_state.get("goal_interpretations"))
    note = (
        f"A child organism pursued the sub-goal: {child_goal}. It returned in the phase "
        f"'{child_state['_phase']}' having witnessed {len(child_state.get('witnessed_deeds') or [])} deeds. "
        f"Its final understanding:\n{child_table}"
    )
    return bus.emit("spawned", {"child_testimony": note, "_depth": depth, "_child_phase": child_state["_phase"]})
