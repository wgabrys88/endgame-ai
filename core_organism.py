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
        while True:
            st["_phase"] = "executing_node"
            st["current_node"] = current
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = node_base.call_node(current, ctx)
            if patch.pop("_reload_wiring", False):
                w = wiring.load_wiring()
            st.update(patch)
            st["last_signal"] = signal_name
            st["last_node"] = current
            st["tick"] += 1
            if signal_name == "halt":
                st["_phase"] = "halted"
                return st
            current = next_node_for(w, current, signal_name)
            st["_phase"] = "node_complete"
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        return st


def next_node_for(w: dict[str, Any], current: str, signal_name: str) -> str:
    """Resolve the one successor for a signal from the live topology."""
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
    args = ap.parse_args(argv)
    run(args.goal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
