import argparse
import pathlib
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_wiring as wiring

# Sentinel: --breakpoint with no path → brain-only (exit 42 after first dump).
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
            # Body-only: after inject queue is empty, stop before next faculty calls live LLM.
            if brain.inject_mode() and brain.inject_remaining() == 0:
                st["_phase"] = "inject_exhausted"
                st["halt_reason"] = "breakpoint inject queue exhausted after faculty use"
                return st
            current = next_node_for(w, current, signal_name)
            st["_phase"] = "node_complete"
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        return st


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "endgame-ai organism kernel. Dumps flat under _transmissions/ "
            "({timestamp}_{uid}_*.txt|json). "
            "--breakpoint: brain-only (exit 42 before exec). "
            "--breakpoint PATH: body-only inject from content file or directory walk."
        )
    )
    ap.add_argument(
        "--breakpoint",
        nargs="?",
        const=_BREAK_ONLY,
        default=None,
        metavar="PATH",
        help=(
            "science mode. No PATH: after first live LLM dump, exit 42 before exec. "
            "PATH file: inject that content as the brain commit and run the body. "
            "PATH directory: feed every content.txt / *_content.txt (sorted, recursive) "
            "one-by-one as successive brain commits (no LLM)."
        ),
    )
    ap.add_argument(
        "goal",
        nargs="?",
        default="",
        help="one-sentence root goal for this life (use any label in body-only inject)",
    )
    args = ap.parse_args(argv)
    import sys

    goal = str(args.goal or "").strip()

    if args.breakpoint is _BREAK_ONLY:
        # Bare --breakpoint → brain-only; goal is the positional (or missing → error later).
        brain.set_break_after_response(True)
    elif args.breakpoint is not None:
        # Optional PATH after --breakpoint. If that string is not an existing file/dir,
        # treat it as the goal (common: --breakpoint "click once...") → still brain-only.
        candidate = pathlib.Path(args.breakpoint).expanduser()
        resolved = candidate if candidate.is_absolute() else (_ROOT / candidate)
        if resolved.exists():
            n = brain.set_inject_path(resolved)
            sys.stderr.write(
                f"BREAKPOINT body-only inject: {n} content file(s) queued from {str(resolved)!r}\n"
            )
            if not goal:
                goal = "body-only inject replay"
        else:
            brain.set_break_after_response(True)
            if goal:
                # Both a positional goal and a non-path token — prefer positional goal.
                sys.stderr.write(
                    f"BREAKPOINT brain-only; ignored non-path token after flag: {args.breakpoint!r}\n"
                )
            else:
                goal = str(args.breakpoint).strip()
                sys.stderr.write(
                    "BREAKPOINT brain-only (argument after flag is goal text, not a path)\n"
                )

    if not goal:
        ap.error("goal is required for brain-only runs (e.g. --breakpoint \"THE_GOAL\")")

    st = run(goal)
    if st.get("_phase") == "inject_exhausted":
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
