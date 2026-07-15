"""cap_spawn — the fractal capability: a plugin that runs a CHILD organism.

The literal fractal claim: a node can spawn a whole `core_organism` as a child,
let it pursue the explicit `spawn_subgoal` to its own terminus, and fold the
child's final `effective_goal` back into the parent narrative. Depth is bounded by
`wiring["fractal"]["max_recursion_depth"]`, threaded through `state["_depth"]`.

Child narrative is ISOLATED in memory: the child runs its own `core_organism.run`
with its own in-memory state and returns its final narrative, which the parent
folds back as testimony. Nothing is persisted; parent and child read and may
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
    parent = state["effective_goal"]
    if depth >= max_depth:
        note = bus.append_narrative(parent, f"\n\n[SPAWN d{depth}] The line of descent hath reached its utmost depth {max_depth}; no child was begotten for: {child_goal}.", root_goal=state.get("goal", ""))
        return bus.emit("spawned", {"effective_goal": note, "_depth": depth})
    child_seed = {"_depth": depth + 1, "effective_goal": child_goal}
    child_state = organism.run(
        child_goal,
        wiring_path=str(w["_source_path"]),
        _seed=child_seed,
    )
    child_narrative = str(child_state["effective_goal"])
    note = bus.append_narrative(parent, f"\n\n[SPAWN d{depth}->d{depth + 1}] The child's sub-goal: {child_goal}. It returned in the phase '{child_state['_phase']}'. Its testimony:\n{child_narrative}", root_goal=state.get("goal", ""))
    return bus.emit("spawned", {"effective_goal": note, "_depth": depth, "_child_phase": child_state["_phase"]})
