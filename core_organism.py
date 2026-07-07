from __future__ import annotations

import argparse
import os
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_node_base as nodes
import core_state as state
import core_stop_check as stop_check
import core_wiring as wiring


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
    w = wiring.load_wiring(wiring_path)
    current = str(start_node or "node_observe")
    deadline_at = _deadline_at
    st: dict[str, Any] = {"_phase": "starting", "tick": 0, "current_node": current}
    try:
        if brain_call_budget is not None:
            w.setdefault("model", {})["brain_call_budget"] = brain_call_budget
        if reset:
            wiring.reset_runtime(w)
        if not _pid_registered:
            brain.reset_call_budget()

        if deadline_at is None and duration_seconds is not None:
            deadline_at = time.time() + float(duration_seconds)

        topo = w.get("topology", {})
        sp = wiring.state_path(w)
        resumed = False
        if not reset and sp.exists():
            st = brain.load_json(sp)
            goal = goal or str(st.get("goal") or "")
            current = str(start_node or st.get("next_node") or topo.get("cycle_start") or "node_planner")
            resumed = True
        else:
            current = str(start_node or topo.get("cycle_start") or "node_planner")
            st = {
                "_phase": "starting",
                "goal": goal or "",
                "tick": 0,
                "current_node": current,
                "last_error": None,
                "last_action": None,
                "wiring_transport": w.get("model", {}).get("transport"),
                "start_node": current,
            }
        if current not in set(topo.get("nodes", [])):
            raise RuntimeError(f"start node '{current}' is not in topology.nodes")
        st["_phase"] = "resuming" if resumed else st.get("_phase", "starting")
        st["goal"] = goal or str(st.get("goal") or "")
        st["current_node"] = current
        st["duration_seconds"] = duration_seconds
        st["deadline_at"] = deadline_at
        st.setdefault("wiring_transport", w.get("model", {}).get("transport"))
        wiring.write_state(w, st)
        state.runtime_event(
            w,
            "organism_resume" if resumed else "organism_start",
            goal=goal or "",
            transport=st["wiring_transport"],
            tick=st.get("tick", 0),
            node=current,
            duration_seconds=duration_seconds,
            deadline_at=deadline_at,
            pid=os.getpid(),
            self_evolution_enabled=stop_check.self_evolution_enabled(),
            self_evolution_file=str(stop_check.SELF_EVOLUTION_FILE),
        )
        while True:
            if state.duration_expired(deadline_at):
                return state.expire_duration(w, st, duration_seconds, current)
            if stop_check.stop_requested():
                return state.stop_file_detected(w, st, current)
            if not state.wait_before_node(w, st, current, deadline_at):
                if state.duration_expired(deadline_at):
                    return state.expire_duration(w, st, duration_seconds, current)
                return state.stop_file_detected(w, st, current)
            st["_phase"] = "executing_node"
            st["current_node"] = current
            wiring.write_state(w, st)
            state.runtime_event(
                w,
                "node_start",
                node=current,
                tick=st["tick"],
                state=bus.state_brief(st),
                last_bus_frame=st.get("_last_bus_frame"),
            )
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = nodes.call_node(current, ctx)
            evolution_patch = patch.get("git_evolution_patch")
            if current == "node_self_modify" and evolution_patch:
                if not stop_check.self_evolution_enabled():
                    patch.setdefault("self_modify", {})["status"] = "disabled"
                    patch["self_modify"]["enabled_file"] = str(stop_check.SELF_EVOLUTION_FILE)
                    patch["last_error"] = "self evolution disabled by missing runtime_self_evolution_enabled.json"
                    patch.pop("git_evolution_patch", None)
                    signal_name = "modify_failed"
                    state.runtime_event(
                        w,
                        "self_modify_disabled",
                        node=current,
                        tick=st.get("tick"),
                        enabled_file=str(stop_check.SELF_EVOLUTION_FILE),
                        proposed_patch_summary=evolution_patch.get("summary") if isinstance(evolution_patch, dict) else None,
                    )
                    evolution_patch = None
                else:
                    try:
                        _, applied = nodes.apply_evolution_patch(w, {"data": evolution_patch})
                        patch.setdefault("self_modify", {})["applied"] = applied
                        committed = nodes.commit_self_evolution(w, applied, evolution_patch)
                        patch["self_modify"]["commit"] = committed
                        w = wiring.load_wiring(wiring_path)
                        state.runtime_event(w, "self_modify_applied", **applied, commit=committed)
                    except Exception as exc:
                        swap_cfg = w.get("self_modify", {})
                        if bool(swap_cfg.get("hot_swap_on_failure", True)):
                            touched = [
                                str(item.get("path")).replace("\\", "/")
                                for item in (evolution_patch.get("file_writes") or [])
                                if isinstance(item, dict) and item.get("path")
                            ]
                            touched.extend(
                                str(path).replace("\\", "/")
                                for path in (evolution_patch.get("file_deletes") or [])
                                if str(path).strip()
                            )
                            if evolution_patch.get("wiring_patches"):
                                touched.append("wiring.json")
                            swap = nodes.hot_swap_to_known_good(w, paths=touched or None)
                            patch.setdefault("self_modify", {})["hot_swap"] = swap
                            state.runtime_event(w, "self_modify_hot_swap", error=str(exc), **swap)
                        raise
            st.update(patch)
            if signal_name == "halt":
                st["_phase"] = "halted"
                wiring.write_state(w, st)
                state.runtime_event(w, "halted", node=current, reason=st.get("error_handled", {}))
                return st
            nxt = next_node_for(w, current, signal_name)
            st["last_signal"] = signal_name
            st["last_node"] = current
            st["next_node"] = nxt
            st["tick"] += 1
            st["_phase"] = "node_complete"
            wiring.write_state(w, st)
            state.runtime_event(
                w,
                "node_complete",
                node=current,
                signal=signal_name,
                next_node=nxt,
                tick=st["tick"],
                state=bus.state_brief(st),
                bus_frame=patch.get("_last_bus_frame"),
            )
            current = nxt
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        wiring.write_state(w, st)
        state.runtime_event(w, "interrupted", node=current)
        return st
    except Exception as exc:
        st["_phase"] = "error"
        st["last_error"] = f"{type(exc).__name__}: {exc}"
        st["last_failure"] = state.classify_node_exception(current, exc)
        wiring.write_state(w, st)
        state.runtime_event(w, "error", node=current, error=st["last_error"])
        try:
            nxt = next_node_for(w, current, "error")
            st["last_signal"] = "error"
            st["last_node"] = current
            st["next_node"] = nxt
            st["tick"] += 1
            st["_phase"] = "node_complete"
            wiring.write_state(w, st)
            state.runtime_event(w, "node_complete", node=current, signal="error", next_node=nxt, tick=st["tick"])
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
            st["_phase"] = "halted"
            st["last_error"] = f"Error routing failed: {route_exc}"
            wiring.write_state(w, st)
            state.runtime_event(w, "halted", node=current, error=st["last_error"])
            return st
    finally:
        if registered_here:
            stop_check.unregister_pid("organism")


def next_node_for(w: dict[str, Any], current: str, signal_name: str) -> str:
    edges = w.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise bus.TopologyContractError(f"topology has no edges for node '{current}'")
    nxt = node_edges.get(signal_name)
    if not isinstance(nxt, str) or not nxt:
        raise bus.TopologyContractError(f"node '{current}' emitted signal '{signal_name}' with no topology edge")
    return nxt


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