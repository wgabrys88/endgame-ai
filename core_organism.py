import argparse
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_node_base as node_base
import core_nodes as nodes
import core_wiring as wiring


def run(
    goal: str | None,
    *,
    wiring_path: str | None = None,
    _seed: dict[str, Any] | None = None,
    _state_path: str | None = None,
) -> dict[str, Any]:
    if not str(goal or "").strip():
        raise ValueError("the organism requires a non-empty root goal")
    invocation_started_at = time.time()
    def load_live_wiring() -> dict[str, Any]:
        loaded = wiring.load_wiring(wiring_path)
        if _state_path:
            loaded["_state_path_override"] = _state_path
        return loaded

    w = load_live_wiring()
    topo = w["topology"]
    current = str(topo["cycle_start"])
    st: dict[str, Any] = {
        "_phase": "starting",
        "goal": goal or "",
        "tick": 0,
        "current_node": current,
        "last_error": None,
        "last_action": None,
        "wiring_transport": w["model"]["transport"],
    }
    try:
        wiring.reset_runtime(w)
        brain.reset_call_budget()

        st.setdefault("effective_goal", st["goal"])
        st.setdefault("_depth", 0)
        if _seed:
            st.update(_seed)
        st["started_at"] = invocation_started_at
        frontier: list[str] = [current]
        barrier_arrivals: dict[str, int] = {}
        pending_snapshot = None
        wiring.write_state(w, st)
        while frontier:
            current = frontier.pop(0)
            st["frontier"] = list(frontier)
            st["barrier_arrivals"] = dict(barrier_arrivals)
            st["_phase"] = "executing_node"
            st["current_node"] = current
            wiring.write_state(w, st)
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = node_base.call_node(current, ctx)
            reload_after_node = bool(patch.pop("_reload_wiring", False))
            evolution_patch = patch.get("git_evolution_patch")
            if current == "node_self_modify" and evolution_patch:
                applied = None
                try:
                    _, applied = nodes.apply_evolution_patch(w, {"data": evolution_patch})
                    pending_snapshot = applied.pop("_rollback_snapshot")
                    patch.setdefault("self_modify", {})["applied"] = applied
                    committed = nodes.commit_self_evolution(
                        w,
                        applied,
                        evolution_patch,
                        advance_known_good=False,
                    )
                    if not committed["committed"]:
                        raise RuntimeError(f"self_modify produced no candidate commit: {committed}")
                    patch["self_modify"]["status"] = "candidate_committed"
                    patch["self_modify"]["commit"] = committed
                    repair_validation = dict(patch["repair_validation"])
                    repair_validation.update(
                        {
                            "status": "awaiting_probe",
                            "activation": applied["activation"],
                            "applied": applied,
                            "commit": committed,
                            "applied_at": time.time(),
                        }
                    )
                    patch["repair_validation"] = repair_validation
                    patch.pop("git_evolution_patch", None)
                    w = load_live_wiring()
                except Exception:
                    if pending_snapshot is not None:
                        patch.setdefault("self_modify", {})["rollback"] = nodes.restore_evolution_snapshot(pending_snapshot)
                        pending_snapshot = None
                    elif applied is not None and bool(w["self_modify"]["hot_swap_on_failure"]):
                        touched = list(applied.get("changed_files") or [])
                        if applied.get("wiring_patches"):
                            touched.append("wiring.json")
                        swap = nodes.hot_swap_to_known_good(w, paths=touched)
                        patch.setdefault("self_modify", {})["hot_swap"] = swap
                    raise
            if current == "node_repair_validate":
                repair_validation = dict(patch["repair_validation"])
                if signal_name == "repair_resolved":
                    acceptance = nodes.accept_self_evolution(
                        w,
                        repair_validation["commit"]["commit"],
                        source="behavioral_repair_validation",
                    )
                    repair_validation["acceptance"] = acceptance
                    patch["repair_validation"] = repair_validation
                    summary = dict(patch["last_repair_validation"])
                    summary.update(
                        {
                            "accepted": True,
                            "accepted_commit": acceptance["commit"],
                            "known_good": acceptance["known_good"],
                        }
                    )
                    patch["last_repair_validation"] = summary
                    history = list(patch["repair_history"])
                    history[-1] = summary
                    patch["repair_history"] = history
                    self_modify = dict(patch["self_modify"])
                    self_modify["status"] = "behaviorally_accepted"
                    self_modify["behavioral_validation"] = summary
                    patch["self_modify"] = self_modify
                    pending_snapshot = None
                else:
                    self_modify = dict(patch["self_modify"])
                    applied = self_modify.get("applied") or {}
                    touched = list(applied.get("changed_files") or [])
                    if applied.get("wiring_patches"):
                        touched.append("wiring.json")
                    if pending_snapshot is not None:
                        restored = nodes.restore_evolution_snapshot(pending_snapshot)
                        pending_snapshot = None
                    else:
                        restored = nodes.hot_swap_to_known_good(w, paths=touched)
                    if touched and not (restored.get("restored") or restored.get("hot_swapped")):
                        raise RuntimeError(f"rejected candidate could not restore its prior body: {restored}")
                    self_modify["rollback"] = restored
                    w = load_live_wiring()
                    rollback = nodes.commit_self_evolution(
                        w,
                        applied,
                        {"summary": f"revert rejected candidate {repair_validation['commit']['commit'][:12]}"},
                        advance_known_good=False,
                    )
                    if touched and not rollback.get("committed"):
                        raise RuntimeError(f"known-good restoration was not committed: {rollback}")
                    self_modify["rollback_commit"] = rollback
                    patch["self_modify"] = self_modify

            if reload_after_node:
                w = load_live_wiring()

            st.update(patch)
            if signal_name in {"halt", "wait"}:
                st["_phase"] = "halted" if signal_name == "halt" else "waiting"
                st["last_signal"] = signal_name
                st["last_node"] = current
                st["frontier"] = list(frontier)
                wiring.write_state(w, st)
                return st
            successors = next_nodes_for(w, current, signal_name)
            _extend_frontier(w, successors, frontier, barrier_arrivals)
            st["last_signal"] = signal_name
            st["last_node"] = current
            st["frontier"] = list(frontier)
            st["barrier_arrivals"] = dict(barrier_arrivals)
            st["tick"] += 1
            st["_phase"] = "node_complete"
            wiring.write_state(w, st)
        st["_phase"] = "frontier_drained"
        wiring.write_state(w, st)
        raise bus.TopologyContractError(
            f"frontier drained at '{current}' — the fractal wheel dead-ended after signal "
            f"'{st.get('last_signal')}'. Rewire the graph so every non-terminal path continues."
        )
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        wiring.write_state(w, st)
        return st


def next_nodes_for(w: dict[str, Any], current: str, signal_name: str) -> list[str]:
    """Resolve one or many successors from the live fractal topology."""
    edges = w.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise bus.TopologyContractError(f"topology has no edges for node '{current}'")
    target = node_edges.get(signal_name)
    if isinstance(target, str) and target:
        return [target]
    if isinstance(target, list) and target and all(isinstance(item, str) and item for item in target):
        return list(target)
    raise bus.TopologyContractError(f"node '{current}' emitted signal '{signal_name}' with no valid topology edge")


def _extend_frontier(
    w: dict[str, Any],
    successors: list[str],
    frontier: list[str],
    arrivals: dict[str, int],
) -> None:
    """Queue fan-out branches; configured barriers release once per full arrival set."""
    barriers = w["topology"].get("barriers", {})
    for successor in successors:
        if successor not in barriers:
            frontier.append(successor)
            continue
        arity = int(barriers[successor])
        count = arrivals.get(successor, 0) + 1
        if count == arity:
            arrivals[successor] = 0
            frontier.append(successor)
        elif count < arity:
            arrivals[successor] = count
        else:
            raise bus.TopologyContractError(
                f"barrier '{successor}' received {count} arrivals for arity {arity}"
            )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("goal", nargs="?", default="")
    ap.add_argument("--wiring", default="wiring.json")
    args = ap.parse_args(argv)
    run(
        args.goal,
        wiring_path=args.wiring,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
