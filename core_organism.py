import argparse
import os
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_node_base as node_base
import core_nodes as nodes
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
    _seed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invocation_started_at = time.time()
    registered_here = False
    if not _pid_registered:
        stop_check.register_pid("organism")
        registered_here = True
    w = wiring.load_wiring(wiring_path)
    topo = w["topology"]
    current = str(start_node or topo["cycle_start"])
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
            deadline_at = invocation_started_at + float(duration_seconds)

        sp = wiring.state_path(w)
        resumed = False
        if not reset and sp.exists():
            st = wiring.load_json(sp)
            goal = goal or str(st.get("goal") or "")
            current = str(start_node or st.get("next_node") or topo["cycle_start"])
            resumed = True
        else:
            current = str(start_node or topo["cycle_start"])
            st = {
                "_phase": "starting",
                "goal": goal or "",
                "tick": 0,
                "current_node": current,
                "last_error": None,
                "last_action": None,
                "wiring_transport": w["model"]["transport"],
                "start_node": current,
            }
        if current not in set(topo["nodes"]):
            raise RuntimeError(f"start node '{current}' is not in topology.nodes")
        st["_phase"] = "resuming" if resumed else st.get("_phase", "starting")
        st["goal"] = goal or str(st.get("goal") or "")
        st.setdefault("effective_goal", st["goal"])
        st.setdefault("_depth", 0)
        st.setdefault("_barrier_release_signal", "join")
        if _seed:
            st.update(_seed)
        st["current_node"] = current
        st["started_at"] = invocation_started_at
        st["duration_seconds"] = duration_seconds
        st["deadline_at"] = deadline_at
        st.setdefault("wiring_transport", w["model"]["transport"])
        frontier: list[str] = [str(n) for n in st.get("frontier") or [current]]
        wiring.write_state(w, st)
        state.runtime_event(
            w,
            "organism_resume" if resumed else "organism_start",
            goal=goal or "",
            transport=st["wiring_transport"],
            tick=st.get("tick", 0),
            node=current,
            frontier=list(frontier),
            duration_seconds=duration_seconds,
            deadline_at=deadline_at,
            pid=os.getpid(),
        )
        while frontier:
            current = frontier.pop(0)
            st["frontier"] = list(frontier)
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
                frontier=list(frontier),
                state=bus.event_state_brief(st),
            )
            try:
                ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
                signal_name, patch = node_base.call_node(current, ctx)
                evolution_patch = patch.get("git_evolution_patch")
                if current == "node_self_modify" and evolution_patch:
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
                        w = wiring.load_wiring(wiring_path)
                        state.runtime_event(
                            w,
                            "self_modify_candidate_committed",
                            repair_id=repair_validation["repair_id"],
                            expected_validation=repair_validation["expected_validation"],
                            **applied,
                            commit=committed,
                        )
                    except Exception as exc:
                        if bool(w["self_modify"]["hot_swap_on_failure"]):
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
                        state.runtime_event(
                            w,
                            "self_modify_behaviorally_accepted",
                            repair_id=repair_validation["repair_id"],
                            comparison=repair_validation["comparison"],
                            conclusion=repair_validation["conclusion"],
                            acceptance=acceptance,
                        )
                    elif signal_name == "repair_unresolved":
                        state.runtime_event(
                            w,
                            "self_modify_behaviorally_rejected",
                            repair_id=repair_validation["repair_id"],
                            candidate_commit=repair_validation["commit"]["commit"],
                            comparison=repair_validation["comparison"],
                            conclusion=repair_validation["conclusion"],
                        )

                st.update(patch)
                if signal_name == "halt":
                    st["_phase"] = "halted"
                    st["frontier"] = []
                    wiring.write_state(w, st)
                    state.runtime_event(w, "halted", node=current, reason=st.get("error_handled", {}))
                    return st
                if signal_name == "wait":
                    st["error_streak"] = 0
                    st["last_signal"] = "wait"
                    st["last_node"] = current
                    st["frontier"] = list(frontier)
                    st["_phase"] = "barrier_wait"
                    wiring.write_state(w, st)
                    state.runtime_event(w, "barrier_wait", node=current, frontier=list(frontier), tick=st["tick"])
                    continue
                successors = next_nodes_for(w, current, signal_name)
                st["error_streak"] = 0
            except Exception as exc:
                st["_phase"] = "error"
                st["last_error"] = f"{type(exc).__name__}: {exc}"
                st["last_failure"] = state.classify_node_exception(current, exc)
                st["error_streak"] = int(st.get("error_streak", 0)) + 1
                wiring.write_state(w, st)
                state.runtime_event(w, "error", node=current, error=st["last_error"], error_streak=st["error_streak"])
                successors = next_nodes_for(w, current, "error")
                signal_name = "error"
            frontier.extend(successors)
            st["last_signal"] = signal_name
            st["last_node"] = current
            st["next_node"] = successors[0]
            st["frontier"] = list(frontier)
            st["tick"] += 1
            st["_phase"] = "node_complete"
            wiring.write_state(w, st)
            state.runtime_event(
                w,
                "node_complete",
                node=current,
                signal=signal_name,
                next_node=successors[0],
                successors=list(successors),
                frontier=list(frontier),
                tick=st["tick"],
                state=bus.event_state_brief(st),
                bus_frame=st.get("_last_bus_frame"),
            )
        st["_phase"] = "frontier_drained"
        wiring.write_state(w, st)
        state.runtime_event(w, "frontier_drained", node=current, tick=st["tick"])
        raise bus.TopologyContractError(
            f"frontier drained at '{current}' — the wheel dead-ended; a fractal topology must always turn. "
            f"last signal '{st.get('last_signal')}' led nowhere. Fix the edges so every path returns to the wheel."
        )
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        wiring.write_state(w, st)
        state.runtime_event(w, "interrupted", node=current)
        return st
    finally:
        if registered_here:
            stop_check.unregister_pid("organism")


def next_nodes_for(w: dict[str, Any], current: str, signal_name: str) -> list[str]:
    """Resolve the successor frontier for (node, signal).

    Edge value may be a single node name (linear) or a list of node names
    (fractal one-to-many). Always returns a non-empty list of node-name strings.
    Fail hard on missing edge or malformed value.
    """
    edges = w.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise bus.TopologyContractError(f"topology has no edges for node '{current}'")
    target = node_edges.get(signal_name)
    if isinstance(target, str) and target:
        return [target]
    if isinstance(target, list) and target and all(isinstance(t, str) and t for t in target):
        return list(target)
    raise bus.TopologyContractError(f"node '{current}' emitted signal '{signal_name}' with no valid topology edge")


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
