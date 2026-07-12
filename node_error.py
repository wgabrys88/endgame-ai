import time

import core_bus as bus
import core_loader as loader


def _repair_interruption_patch(state, info):
    repair = dict(state["repair_validation"])
    validated_at = time.time()
    conclusion = f"Behavioral validation was interrupted in {info['failed_node']}: {info['error']}"
    comparison = "No complete fresh before/after proof was produced, so the candidate repair remains unproven."
    repair.update(
        {
            "status": "unresolved",
            "resolved": False,
            "comparison": comparison,
            "conclusion": conclusion,
            "validated_at": validated_at,
        }
    )
    summary = {
        "repair_id": repair["repair_id"],
        "status": "unresolved",
        "resolved": False,
        "failure_signature": repair["baseline"]["failure_signature"],
        "candidate_commit": repair["commit"]["commit"],
        "summary": repair["summary"],
        "expected_validation": repair["expected_validation"],
        "probe_description": (repair.get("probe") or {}).get("description"),
        "comparison": comparison,
        "conclusion": conclusion,
        "validated_at": validated_at,
    }
    history = list(state.get("repair_history") or [])
    history.append(summary)
    self_modify = dict(state["self_modify"])
    self_modify["status"] = "behaviorally_rejected"
    self_modify["behavioral_validation"] = summary
    original_step = repair["baseline"]["step"]
    failure = {
        "source": "repair_validation",
        "kind": "repair_probe_interrupted",
        "repair_id": repair["repair_id"],
        "failure_signature": repair["baseline"]["failure_signature"],
        "candidate_commit": repair["commit"]["commit"],
        "failed_node": info["failed_node"],
        "error": info["error"],
    }
    effective = (
        state["effective_goal"]
        + f"\n\n[REPAIR VALIDATION] UNRESOLVED: {comparison} Conclusion: {conclusion}."
    )
    return {
        "error_handled": info,
        "recovery": "reflect",
        "repair_validation": repair,
        "last_repair_validation": summary,
        "repair_history": history,
        "self_modify": self_modify,
        "current_step": original_step,
        "step_goal": original_step["description"],
        "action_frame": None,
        "turn_executions": {},
        "_dispatch_targets": [],
        "_barrier_release_signal": "join",
        "last_error": conclusion,
        "last_failure": failure,
        "effective_goal": effective,
    }


def run(ctx):
    state = ctx.get("state", {})
    info = {
        "failed_node": state.get("last_node"),
        "error": state.get("last_error"),
        "tick": state.get("tick"),
        "signal": state.get("last_signal"),
        "failure": state.get("last_failure", {}),
    }
    print(f"[ERROR NODE] Failed node: {info['failed_node']}, Error: {info['error']}")
    repair = state.get("repair_validation") or {}
    if repair.get("status") in {"awaiting_probe", "probing"}:
        return bus.emit("reflect", _repair_interruption_patch(state, info))
    error = str(state.get("last_error") or "")
    effective = state["effective_goal"]
    failed_base, _ = loader.split_instance(str(state["last_node"]))
    if not bool((state.get("observation") or {}).get("desktop_tree_text")) and (
        failed_base in {"node_observe", "node_planner"} or "observation missing" in error
    ):
        return bus.emit(
            "guidance",
            {
                "error_handled": info,
                "recovery": "guidance",
                "plan_failed": True,
                "last_error": error,
                "last_failure": state.get("last_failure", {}),
                "effective_goal": effective
                + f"\n\n[ERROR] No observation data for {info['failed_node']}. Re-entering the wheel through guidance and observation.",
            },
        )
    recovery = "reflect" if state.get("current_step") else "planner"
    return bus.emit(
        recovery,
        {
            "error_handled": info,
            "recovery": recovery,
            "last_failure": state.get("last_failure", {}),
            "effective_goal": effective
            + f"\n\n[ERROR] Recovered from {info['failed_node']} error: {error}. Routing to {recovery}.",
        },
    )
