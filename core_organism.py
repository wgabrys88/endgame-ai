import argparse
import pathlib
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_wiring as wiring

_BREAK_ONLY = object()
_ROOT = pathlib.Path(__file__).resolve().parent


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
            st["_phase"] = "executing_node"
            st["current_node"] = current
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = nodes.call_node(current, ctx)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "endgame-ai. Dumps under _transmissions/. "
            "--breakpoint: fuse on next live LLM transmission (exit 42). "
            "--breakpoint FILE: inject that full reply once, body runs, fuse still on for next live LLM."
        )
    )
    ap.add_argument(
        "--breakpoint",
        nargs="?",
        const=_BREAK_ONLY,
        default=None,
        metavar="FILE",
        help=(
            "fuse: stop after next live LLM dump (exit 42). "
            "FILE: inject one content.txt / transmission.json / record as the next think reply; "
            "hands run; next live LLM still hits the fuse."
        ),
    )
    ap.add_argument(
        "goal",
        nargs="?",
        default="",
        help="root goal (or label when injecting)",
    )
    args = ap.parse_args(argv)
    import sys

    goal = str(args.goal or "").strip()

    if args.breakpoint is _BREAK_ONLY:
        brain.set_fuse(True)
    elif args.breakpoint is not None:
        candidate = pathlib.Path(args.breakpoint).expanduser()
        resolved = candidate if candidate.is_absolute() else (_ROOT / candidate)
        if resolved.is_file():
            brain.set_fuse(True)
            brain.set_inject(resolved)
            sys.stderr.write(f"FUSE+INJECT from {str(resolved)!r}\n")
            if not goal:
                goal = "inject"
        else:
            brain.set_fuse(True)
            if goal:
                sys.stderr.write(
                    f"FUSE on; ignored non-file after flag: {args.breakpoint!r}\n"
                )
            else:
                goal = str(args.breakpoint).strip()
                sys.stderr.write("FUSE on (token after flag is goal text)\n")

    if not goal:
        ap.error('goal required (e.g. --breakpoint "THE_GOAL" or a goal positional)')

    run(goal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
