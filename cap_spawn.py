"""cap_spawn — the fractal capability: a plugin that runs a CHILD organism.

The literal fractal claim: a node can spawn a whole `core_organism` as a child,
let it pursue a sub-goal to its own terminus, and fold the child's final
`effective_goal` back into the parent narrative. Depth is bounded by
`wiring["fractal"]["max_recursion_depth"]`, threaded through `state["_depth"]`.

Child state is ISOLATED: the child runs against a deep-copied wiring whose
`paths.state` and `paths.control` are redirected to depth/tick-suffixed files,
written to a temp wiring JSON the child loads. The parent's `runtime_state.json`
is never touched by the child.

Contract: `run(ctx) -> bus.emit(signal, patch)`. Loaded as kind "cap".
"""
from __future__ import annotations

import copy
import json
import tempfile
from typing import Any

import core_bus as bus
import core_wiring as wiring


def _child_wiring_path(w: dict[str, Any], depth: int, tag: str) -> str:
    child = copy.deepcopy(w)
    stem = f"runtime_child_d{depth}_{tag}"
    child["paths"]["state"] = f"{stem}_state.json"
    path = wiring.root_path(f"{stem}_wiring.json")
    path.write_text(json.dumps(child, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def run(ctx: dict[str, Any]):
    import core_organism as organism
    state = ctx["state"]
    w = ctx["wiring"]
    depth = int(state["_depth"])
    max_depth = int(w["fractal"]["max_recursion_depth"])
    child_goal = str(state["effective_goal"])
    parent = state["effective_goal"]
    if depth >= max_depth:
        note = parent + f"\n\n[SPAWN d{depth}] The line of descent has reached its appointed depth of {max_depth}; I beget no further child, and carry the work forward myself."
        return bus.emit("spawned", {"effective_goal": note, "_depth": depth})
    tag = f"t{int(state.get('tick', 0))}"
    child_path = _child_wiring_path(w, depth + 1, tag)
    child_seed = {"_depth": depth + 1, "effective_goal": child_goal}
    child_state = organism.run(child_goal, reset=True, duration_seconds=float(w["fractal"]["child_duration_seconds"]), wiring_path=child_path, _seed=child_seed)
    child_narrative = str(child_state["effective_goal"])
    note = parent + f"\n\n[SPAWN d{depth}->d{depth + 1}] I begot a child organism to pursue the sub-work; it returned having reached '{child_state['_phase']}'. Its testimony:\n{child_narrative}"
    return bus.emit("spawned", {"effective_goal": note, "_depth": depth, "_child_phase": child_state["_phase"]})
