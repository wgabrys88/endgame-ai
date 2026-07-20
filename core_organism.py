import argparse
import importlib
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_wiring as wiring


def next_node_for(w: dict[str, Any], current: str, signal_name: str) -> str:
    edges = w.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise bus.TopologyContractError(f"topology has no edges for node '{current}'")
    target = node_edges.get(signal_name)
    if isinstance(target, str) and target:
        return target
    raise bus.TopologyContractError(
        f"node '{current}' emitted signal '{signal_name}' with no valid topology edge"
    )


def run(goal: str | None) -> dict[str, Any]:
    if not str(goal or "").strip():
        raise ValueError("the organism requires a non-empty root goal")
    w = wiring.load_wiring()
    current = str(w["topology"]["cycle_start"])
    st: dict[str, Any] = {
        "_phase": "starting",
        "goal": goal or "",
        "tick": 0,
        "current_node": current,
        "goal_interpretations": {},
        "wiring_transport": w["model"]["transport"],
        "started_at": time.time(),
    }
    try:
        while True:
            nodes_module = importlib.reload(nodes)
            w = wiring.load_wiring()
            st["_phase"] = "executing_node"
            st["current_node"] = current
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = nodes_module.call_node(current, ctx)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "endgame-ai organism kernel. Dumps always under _transmissions/. "
            "Use --breakpoint for one-transmission tune (exit 42 before exec)."
        )
    )
    ap.add_argument(
        "--breakpoint",
        action="store_true",
        help="after the first model dump, exit 42 before any exec (prompt/knob science mode)",
    )
    ap.add_argument("goal", nargs="?", default="", help="one-sentence root goal for this life")
    args = ap.parse_args(argv)
    brain.set_break_after_response(bool(args.breakpoint))
    run(args.goal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
