import argparse
import time
from typing import Any

import core_bus as bus
import core_node_base as node_base
import core_wiring as wiring


def run(goal: str | None) -> dict[str, Any]:
    if not str(goal or "").strip():
        raise ValueError("the organism requires a non-empty root goal")
    invocation_started_at = time.time()

    w = wiring.load_wiring()
    topo = w["topology"]
    current = str(topo["cycle_start"])
    st: dict[str, Any] = {
        "_phase": "starting",
        "goal": goal or "",
        "tick": 0,
        "current_node": current,
        "goal_interpretations": {},
        "wiring_transport": w["model"]["transport"],
    }
    try:
        st["started_at"] = invocation_started_at
        frontier: list[str] = [current]
        barrier_arrivals: dict[str, int] = {}
        while frontier:
            current = frontier.pop(0)
            st["frontier"] = list(frontier)
            st["barrier_arrivals"] = dict(barrier_arrivals)
            st["_phase"] = "executing_node"
            st["current_node"] = current
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = node_base.call_node(current, ctx)
            reload_after_node = bool(patch.pop("_reload_wiring", False))

            if reload_after_node:
                w = wiring.load_wiring()

            st.update(patch)
            if signal_name in {"halt", "wait"}:
                st["_phase"] = "halted" if signal_name == "halt" else "waiting"
                st["last_signal"] = signal_name
                st["last_node"] = current
                st["frontier"] = list(frontier)
                return st
            successors = next_nodes_for(w, current, signal_name)
            _extend_frontier(w, successors, frontier, barrier_arrivals)
            st["last_signal"] = signal_name
            st["last_node"] = current
            st["frontier"] = list(frontier)
            st["barrier_arrivals"] = dict(barrier_arrivals)
            st["tick"] += 1
            st["_phase"] = "node_complete"
        st["_phase"] = "frontier_drained"
        raise bus.TopologyContractError(
            f"frontier drained at '{current}' — the fractal wheel dead-ended after signal "
            f"'{st.get('last_signal')}'. Rewire the graph so every non-terminal path continues."
        )
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
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
    args = ap.parse_args(argv)
    run(args.goal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
