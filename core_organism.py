from __future__ import annotations

import argparse
import os
import pathlib
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_stop_check as stop_check

ROOT = pathlib.Path(__file__).parent.resolve()


def load_wiring(path: str | None = None) -> dict[str, Any]:
    return brain.load_json(brain.root_path(path, "wiring.json"))


def state_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get("state"), "runtime_state.json")


def control_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get("control"), "runtime_control.json")


def event_log_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get("event_log"), "runtime_events.jsonl")


def write_state(wiring: dict[str, Any], state: dict[str, Any]) -> None:
    brain.atomic_write_json(state_path(wiring), state)


def runtime_event(wiring: dict[str, Any], event: str, **payload: Any) -> None:
    brain.log_runtime_event({"event_log_path": str(event_log_path(wiring))}, event, **payload)


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
    for key, default in [("state", "runtime_state.json"), ("control", "runtime_control.json")]:
        p = brain.root_path(wiring.get("paths", {}).get(key), default)
        if p.exists():
            p.unlink()
    for key, default in [("request", "runtime_request.json"), ("response", "runtime_response.json")]:
        p = brain.root_path(wiring.get("paths", {}).get(key), default)
        if p.exists():
            p.unlink()
    stop_check.clear_stop()
    stop_check.ensure_self_evolution_enabled(source="reset")


def duration_expired(deadline_at: float | None) -> bool:
    return deadline_at is not None and time.time() >= deadline_at


def expire_duration(
    wiring: dict[str, Any],
    state: dict[str, Any],
    duration_seconds: float | None,
    node_name: str,
) -> dict[str, Any]:
    reason = f"duration_seconds expired after {duration_seconds:g}s" if duration_seconds is not None else "duration expired"
    state["_phase"] = "duration_expired"
    state["current_node"] = node_name
    state["stop_reason"] = reason
    write_state(wiring, state)
    stop_check.request_stop(reason, source="duration")
    runtime_event(
        wiring,
        "duration_expired",
        node=node_name,
        tick=state.get("tick"),
        duration_seconds=duration_seconds,
        stop_file=str(stop_check.STOP_FILE),
    )
    return state


def stop_file_detected(wiring: dict[str, Any], state: dict[str, Any], node_name: str) -> dict[str, Any]:
    state["_phase"] = "stop_requested"
    state["current_node"] = node_name
    state["stop_reason"] = f"stop file detected: {stop_check.STOP_FILE.name}"
    write_state(wiring, state)
    runtime_event(
        wiring,
        "stop_file_detected",
        node=node_name,
        tick=state.get("tick"),
        stop_file=str(stop_check.STOP_FILE),
    )
    return state


def wait_before_node(
    wiring: dict[str, Any],
    state: dict[str, Any],
    node_name: str,
    deadline_at: float | None = None,
) -> bool:
    entered_pause = False
    while True:
        if duration_expired(deadline_at):
            return False
        if stop_check.stop_requested():
            return False
        ctrl = read_control(wiring)
        mode = ctrl["mode"]
        token = int(ctrl.get("step_token", 0))
        if mode == "run":
            return True
        consumed = int(state.get("_last_step_token_consumed", -1))
        if mode == "step" and token > consumed:
            state["_last_step_token_consumed"] = token
            state["_phase"] = "stepping_node"
            state["current_node"] = node_name
            write_state(wiring, state)
            runtime_event(wiring, "step_consumed", node=node_name, step_token=token)
            return True
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
    duration_seconds: float | None = None,
    brain_call_budget: int | None = None,
    start_node: str | None = None,
    wiring_path: str | None = None,
    _pid_registered: bool = False,
    _deadline_at: float | None = None,
) -> dict[str, Any]:
    registered_here = False
    if not _pid_registered:
        stop_check.register_pid("organism")
        registered_here = True
    wiring = load_wiring(wiring_path)
    current = str(start_node or "node_observe")
    deadline_at = _deadline_at
    state: dict[str, Any] = {"_phase": "starting", "tick": 0, "current_node": current}
    try:
        if brain_call_budget is not None:
            wiring.setdefault("model", {})["brain_call_budget"] = brain_call_budget
        if reset:
            reset_runtime(wiring)
        if not _pid_registered:
            brain.reset_call_budget()

        if deadline_at is None and duration_seconds is not None:
            deadline_at = time.time() + float(duration_seconds)

        topo = wiring.get("topology", {})
        sp = state_path(wiring)
        resumed = False
        if not reset and sp.exists():
            state = brain.load_json(sp)
            goal = goal or str(state.get("goal") or "")
            current = str(start_node or state.get("next_node") or topo.get("cycle_start") or "node_planner")
            resumed = True
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
        state["goal"] = goal or str(state.get("goal") or "")
        state["current_node"] = current
        state["duration_seconds"] = duration_seconds
        state["deadline_at"] = deadline_at
        state.setdefault("wiring_transport", wiring.get("model", {}).get("transport"))
        write_state(wiring, state)
        runtime_event(
            wiring,
            "organism_resume" if resumed else "organism_start",
            goal=goal or "",
            transport=state["wiring_transport"],
            tick=state.get("tick", 0),
            node=current,
            duration_seconds=duration_seconds,
            deadline_at=deadline_at,
            pid=os.getpid(),
            self_evolution_enabled=stop_check.self_evolution_enabled(),
            self_evolution_file=str(stop_check.SELF_EVOLUTION_FILE),
        )
        while True:
            if duration_expired(deadline_at):
                return expire_duration(wiring, state, duration_seconds, current)
            if stop_check.stop_requested():
                return stop_file_detected(wiring, state, current)
            if not wait_before_node(wiring, state, current, deadline_at):
                if duration_expired(deadline_at):
                    return expire_duration(wiring, state, duration_seconds, current)
                return stop_file_detected(wiring, state, current)
            state["_phase"] = "executing_node"
            state["current_node"] = current
            write_state(wiring, state)
            runtime_event(
                wiring,
                "node_start",
                node=current,
                tick=state["tick"],
                state=bus.state_brief(state),
                last_bus_frame=state.get("_last_bus_frame"),
            )
            ctx = {"wiring": wiring, "state": dict(state), "goal": goal or "", "node": current}
            signal_name, patch = nodes.call_node(current, ctx)
            evolution_patch = patch.get("git_evolution_patch")
            if current == "node_self_modify" and evolution_patch:
                if not stop_check.self_evolution_enabled():
                    patch.setdefault("self_modify", {})["status"] = "disabled"
                    patch["self_modify"]["enabled_file"] = str(stop_check.SELF_EVOLUTION_FILE)
                    patch["last_error"] = "self evolution disabled by missing runtime_self_evolution_enabled.json"
                    patch.pop("git_evolution_patch", None)
                    signal_name = "modify_failed"
                    runtime_event(
                        wiring,
                        "self_modify_disabled",
                        node=current,
                        tick=state.get("tick"),
                        enabled_file=str(stop_check.SELF_EVOLUTION_FILE),
                        proposed_patch_summary=evolution_patch.get("summary") if isinstance(evolution_patch, dict) else None,
                    )
                    evolution_patch = None
                else:
                    try:
                        _, applied = nodes.apply_evolution_patch(wiring, {"data": evolution_patch})
                        patch.setdefault("self_modify", {})["applied"] = applied
                        committed = nodes.commit_self_evolution(wiring, applied, evolution_patch)
                        patch["self_modify"]["commit"] = committed
                        wiring = load_wiring(wiring_path)
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
            runtime_event(
                wiring,
                "node_complete",
                node=current,
                signal=signal_name,
                next_node=nxt,
                tick=state["tick"],
                state=bus.state_brief(state),
                bus_frame=patch.get("_last_bus_frame"),
            )
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
            return run(
                goal,
                reset=False,
                duration_seconds=duration_seconds,
                brain_call_budget=brain_call_budget,
                start_node=current,
                wiring_path=wiring_path,
                _pid_registered=True,
                _deadline_at=deadline_at,
            )
        except RuntimeError as route_exc:
            state["_phase"] = "halted"
            state["last_error"] = f"Error routing failed: {route_exc}"
            write_state(wiring, state)
            runtime_event(wiring, "halted", node=current, error=state["last_error"])
            return state
    finally:
        if registered_here:
            stop_check.unregister_pid("organism")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("goal", nargs="?", default="")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--duration-seconds", type=float, default=120.0)
    ap.add_argument("--brain-call-budget", type=int, default=None)
    ap.add_argument("--start-node", default=None)
    ap.add_argument("--wiring", default="wiring.json")
    args = ap.parse_args(argv)
    run(
        args.goal,
        reset=args.reset,
        duration_seconds=args.duration_seconds,
        brain_call_budget=args.brain_call_budget,
        start_node=args.start_node,
        wiring_path=args.wiring,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
