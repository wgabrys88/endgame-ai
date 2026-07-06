from __future__ import annotations

import argparse
import json
import os
import pathlib
import signal
import sys
import time
from typing import Any

import core_brain as brain
import core_nodes as nodes
import core_stop_check as stop_check

ROOT = pathlib.Path(__file__).parent.resolve()


def load_wiring() -> dict[str, Any]:
    return brain.load_json(ROOT / "wiring.json")


def state_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get("state"), "runtime_state.json")


def control_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get("control"), "runtime_control.json")


def runtime_log_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get("runtime_log"), "runtime_log.ndjson")


def write_state(wiring: dict[str, Any], state: dict[str, Any]) -> None:
    brain.atomic_write_json(state_path(wiring), state)


def runtime_event(wiring: dict[str, Any], event: str, **payload: Any) -> None:
    row = {"ts": time.time(), "event": event, **payload}
    brain.append_ndjson(runtime_log_path(wiring), row)


def default_control(wiring: dict[str, Any]) -> dict[str, Any]:
    ctrl = dict(wiring.get("control_default") or {"mode": "run", "step_token": 0, "updated_at": 0})
    ctrl.setdefault("mode", "run")
    ctrl.setdefault("step_token", 0)
    ctrl.setdefault("updated_at", 0)
    return ctrl


def read_control(wiring: dict[str, Any]) -> dict[str, Any]:
    path = control_path(wiring)
    if not path.exists():
        ctrl = default_control(wiring)
        ctrl["updated_at"] = time.time()
        brain.atomic_write_json(path, ctrl)
        return ctrl
    ctrl = brain.load_json(path)
    mode = ctrl.get("mode")
    if mode not in {"run", "pause", "step"}:
        raise RuntimeError(f"invalid control mode in {path}: {mode!r}")
    try:
        ctrl["step_token"] = int(ctrl.get("step_token", 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid step_token in {path}: {ctrl.get('step_token')!r}") from exc
    return ctrl


def reset_runtime(wiring: dict[str, Any]) -> None:
    for key, default in [("state", "runtime_state.json"), ("runtime_log", "runtime_log.ndjson")]:
        p = brain.root_path(wiring.get("paths", {}).get(key), default)
        if p.exists():
            p.unlink()


def wait_before_node(wiring: dict[str, Any], state: dict[str, Any], node_name: str) -> None:
    entered_pause = False
    while True:
        stop_check.check_stop(f"organism wait_before_node:{node_name}")
        ctrl = read_control(wiring)
        mode = ctrl["mode"]
        token = int(ctrl.get("step_token", 0))
        if mode == "run":
            return
        consumed = int(state.get("_last_step_token_consumed", -1))
        if mode == "step" and token > consumed:
            state["_last_step_token_consumed"] = token
            state["_phase"] = "stepping_node"
            state["current_node"] = node_name
            write_state(wiring, state)
            runtime_event(wiring, "step_consumed", node=node_name, step_token=token)
            return
        if not entered_pause:
            state["_phase"] = "paused_before_node"
            state["current_node"] = node_name
            state["control_mode"] = mode
            write_state(wiring, state)
            runtime_event(wiring, "paused_before_node", node=node_name, mode=mode, step_token=token)
            entered_pause = True
        time.sleep(0.1)


def next_node_for(wiring: dict[str, Any], current: str, signal_name: str) -> str:
    edges = wiring.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise RuntimeError(f"topology has no edges for node '{current}'")
    nxt = node_edges.get(signal_name)
    if not isinstance(nxt, str) or not nxt:
        raise RuntimeError(f"node '{current}' emitted signal '{signal_name}' with no topology edge")
    return nxt


def run(
    goal: str | None,
    *,
    reset: bool = False,
    max_ticks: int | None = None,
    max_brain_calls: int | None = None,
    start_node: str | None = None,
) -> dict[str, Any]:
    stop_check.register_pid("organism")
    wiring = load_wiring()
    if max_brain_calls is not None:
        wiring.setdefault("model", {})["max_brain_calls"] = max_brain_calls
    if reset:
        reset_runtime(wiring)
    brain.reset_call_budget()
    topo = wiring.get("topology", {})
    sp = state_path(wiring)
    resumed = False
    if not reset and sp.exists():
        state = brain.load_json(sp)
        goal = goal or str(state.get("goal") or "")
        current = str(start_node or state.get("next_node") or topo.get("cycle_start") or "node_planner")
        resumed = True
        if max_ticks is not None:
            max_ticks = int(state.get("tick", 0)) + max_ticks
    else:
        current = str(start_node or topo.get("cycle_start") or "node_planner")
        state = {
            "_phase": "starting",
            "goal": goal or "",
            "tick": 0,
            "current_node": current,
            "last_error": None,
            "last_action": None,
            "wiring_transport": wiring.get("model", {}).get("transport"),
            "start_node": current,
        }
    if current not in set(topo.get("nodes", [])):
        raise RuntimeError(f"start node '{current}' is not in topology.nodes")
    state["_phase"] = "resuming" if resumed else state.get("_phase", "starting")
    state["current_node"] = current
    state.setdefault("wiring_transport", wiring.get("model", {}).get("transport"))
    write_state(wiring, state)
    runtime_event(
        wiring,
        "organism_resume" if resumed else "organism_start",
        goal=goal or "",
        transport=state["wiring_transport"],
        tick=state.get("tick", 0),
        node=current,
    )
    try:
        while True:
            stop_check.check_stop("organism main loop")
            if max_ticks is not None and state["tick"] >= max_ticks:
                state["_phase"] = "max_ticks"
                write_state(wiring, state)
                runtime_event(wiring, "max_ticks", tick=state["tick"])
                return state
            wait_before_node(wiring, state, current)
            state["_phase"] = "executing_node"
            state["current_node"] = current
            write_state(wiring, state)
            runtime_event(wiring, "node_start", node=current, tick=state["tick"])
            ctx = {"wiring": wiring, "state": dict(state), "goal": goal or "", "node": current}
            signal_name, patch = nodes.call_node(current, ctx)
            evolution_patch = patch.get("git_evolution_patch")
            if current == "node_self_modify" and evolution_patch:
                try:
                    _, applied = nodes.apply_evolution_patch(wiring, {"data": evolution_patch})
                    patch.setdefault("self_modify", {})["applied"] = applied
                    committed = nodes.commit_self_evolution(wiring, applied, evolution_patch)
                    patch["self_modify"]["commit"] = committed
                    wiring = load_wiring()
                    runtime_event(wiring, "self_modify_applied", **applied, commit=committed)
                except Exception as exc:
                    swap_cfg = wiring.get("self_modify", {})
                    if bool(swap_cfg.get("hot_swap_on_failure", True)):
                        touched = [
                            str(item.get("path")).replace("\\", "/")
                            for item in (evolution_patch.get("file_writes") or [])
                            if isinstance(item, dict) and item.get("path")
                        ]
                        swap = nodes.hot_swap_to_known_good(wiring, paths=touched or None)
                        if not swap.get("hot_swapped") and swap_cfg.get("known_good_commit"):
                            swap = nodes.hot_swap_to_known_good(wiring)
                        patch.setdefault("self_modify", {})["hot_swap"] = swap
                        runtime_event(wiring, "self_modify_hot_swap", error=str(exc), **swap)
                    raise
            state.update(patch)
            if signal_name == "halt":
                state["_phase"] = "halted"
                write_state(wiring, state)
                runtime_event(wiring, "halted", node=current, reason=state.get("error_handled", {}))
                return state
            nxt = next_node_for(wiring, current, signal_name)
            state["last_signal"] = signal_name
            state["last_node"] = current
            state["next_node"] = nxt
            state["tick"] += 1
            state["_phase"] = "node_complete"
            write_state(wiring, state)
            runtime_event(wiring, "node_complete", node=current, signal=signal_name, next_node=nxt, tick=state["tick"])
            current = nxt
    except KeyboardInterrupt:
        state["_phase"] = "interrupted"
        write_state(wiring, state)
        runtime_event(wiring, "interrupted", node=current)
        return state
    except Exception as exc:
        state["_phase"] = "error"
        state["last_error"] = f"{type(exc).__name__}: {exc}"
        write_state(wiring, state)
        runtime_event(wiring, "error", node=current, error=state["last_error"])
        try:
            nxt = next_node_for(wiring, current, "error")
            state["last_signal"] = "error"
            state["last_node"] = current
            state["next_node"] = nxt
            state["tick"] += 1
            state["_phase"] = "node_complete"
            write_state(wiring, state)
            runtime_event(wiring, "node_complete", node=current, signal="error", next_node=nxt, tick=state["tick"])
            current = nxt
            remaining_ticks = None if max_ticks is None else max(0, int(max_ticks) - int(state.get("tick", 0)))
            return run(
                goal,
                reset=False,
                max_ticks=remaining_ticks,
                max_brain_calls=max_brain_calls,
                start_node=current,
            )
        except RuntimeError as route_exc:
            state["_phase"] = "halted"
            state["last_error"] = f"Error routing failed: {route_exc}"
            write_state(wiring, state)
            runtime_event(wiring, "halted", node=current, error=state["last_error"])
            return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("goal", nargs="?", default="")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument("--max-brain-calls", type=int, default=None)
    ap.add_argument("--start-node", default=None)
    args = ap.parse_args(argv)
    run(args.goal, reset=args.reset, max_ticks=args.max_ticks, max_brain_calls=args.max_brain_calls, start_node=args.start_node)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
