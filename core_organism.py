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
    brain_call_budget: int | None = None,
    start_node: str | None = None,
    wiring_path: str | None = None,
    _seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not str(goal or "").strip():
        raise ValueError("the organism requires a non-empty root goal")
    invocation_started_at = time.time()
    w = wiring.load_wiring(wiring_path)
    topo = w["topology"]
    current = str(start_node or topo["cycle_start"])
    st: dict[str, Any] = {
        "_phase": "starting",
        "goal": goal or "",
        "tick": 0,
        "current_node": current,
        "last_error": None,
        "last_action": None,
        "wiring_transport": w["model"]["transport"],
        "start_node": current,
    }
    try:
        if brain_call_budget is not None:
            w.setdefault("model", {})["brain_call_budget"] = brain_call_budget
        wiring.reset_runtime(w)
        brain.reset_call_budget()

        if current not in set(topo["nodes"]):
            raise RuntimeError(f"start node '{current}' is not in topology.nodes")
        st.setdefault("effective_goal", st["goal"])
        st.setdefault("_depth", 0)
        if _seed:
            st.update(_seed)
        st["started_at"] = invocation_started_at
        wiring.write_state(w, st)
        while True:
            st["_phase"] = "executing_node"
            st["current_node"] = current
            wiring.write_state(w, st)
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = node_base.call_node(current, ctx)
            evolution_patch = patch.get("git_evolution_patch")
            if current == "node_self_modify" and evolution_patch:
                applied = None
                try:
                    _, applied = nodes.apply_evolution_patch(w, {"data": evolution_patch})
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
                    w = wiring.load_wiring(wiring_path)
                except Exception:
                    if applied is not None and bool(w["self_modify"]["hot_swap_on_failure"]):
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
                else:
                    self_modify = dict(patch["self_modify"])
                    applied = self_modify.get("applied") or {}
                    touched = list(applied.get("changed_files") or [])
                    if applied.get("wiring_patches"):
                        touched.append("wiring.json")
                    swap = nodes.hot_swap_to_known_good(w, paths=touched)
                    if touched and not swap.get("hot_swapped"):
                        raise RuntimeError(f"rejected candidate could not return to known-good: {swap}")
                    self_modify["hot_swap"] = swap
                    w = wiring.load_wiring(wiring_path)
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

            st.update(patch)
            if signal_name in {"halt", "wait"}:
                st["_phase"] = "halted" if signal_name == "halt" else "waiting"
                st["last_signal"] = signal_name
                st["last_node"] = current
                wiring.write_state(w, st)
                return st
            current = next_node_for(w, current, signal_name)
            st["last_signal"] = signal_name
            st["last_node"] = st["current_node"]
            st["tick"] += 1
            st["_phase"] = "node_complete"
            wiring.write_state(w, st)
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        wiring.write_state(w, st)
        return st


def next_node_for(w: dict[str, Any], current: str, signal_name: str) -> str:
    """Resolve the sole next node in the wheel for (node, signal)."""
    edges = w.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise bus.TopologyContractError(f"topology has no edges for node '{current}'")
    target = node_edges.get(signal_name)
    if isinstance(target, str) and target:
        return target
    raise bus.TopologyContractError(f"node '{current}' emitted signal '{signal_name}' with no valid topology edge")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("goal", nargs="?", default="")
    ap.add_argument("--brain-call-budget", type=int, default=None)
    ap.add_argument("--start-node", default=None)
    ap.add_argument("--wiring", default="wiring.json")
    args = ap.parse_args(argv)
    run(
        args.goal,
        brain_call_budget=args.brain_call_budget,
        start_node=args.start_node,
        wiring_path=args.wiring,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
