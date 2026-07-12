"""node_run — the runner. Executes a code artifact written to disk by node_execute.

The organism's execution model is now two-phase and fractal:
  node_execute  -> authors code (LLM or repair probe) and WRITES it as a script
                   artifact on disk (a volatile node born from the wheel), emits "built".
  node_run      -> LOADS that artifact and runs it inside the capability runtime,
                   emits "done" with the same execution evidence contract as before.

This makes "produce code" and "run code" two wired steps the topology controls,
instead of one monolith. The artifact is the durable, inspectable unit of action.
"""
import contextlib
import hashlib
import io
import pathlib
import time

import core_bus as bus
import core_nodes as nodes


def _failure(kind, **extra):
    return {"source": "execute", "kind": kind, "contract_repair_allowed": False, **extra}


def _turn_entry(code, result, error, failure):
    return {
        "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
        "code_chars": len(code),
        "result": result,
        "error": error,
        "failure": failure,
    }


def run(ctx):
    state = ctx["state"]
    instance = ctx["node_instance"]
    artifact = (state.get("_execute_artifacts") or {}).get(instance)
    if artifact is None:
        return bus.emit("done")

    label = artifact["label"]
    probe = artifact["repair_probe"]
    if artifact.get("not_executed"):
        return bus.emit("done")
    code = pathlib.Path(artifact["path"]).read_text(encoding="utf-8")

    import core_desktop as desktop

    ns = nodes.build_capability_runtime(ctx)
    ns["desktop"] = desktop
    stdout, stderr = io.StringIO(), io.StringIO()
    error = failure = None
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, ns)
        result = {
            "result": ns.get("result"),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "action_events": list(ns["_action_events"]),
        }
        policy = ctx["wiring"]["capabilities"]["faculties"][instance]
        if policy["requires_action_event"] and not result["action_events"]:
            error = f"RuntimeError: {instance} faculty produced no recorded capability action"
            failure = _failure("faculty_evidence_missing", faculty=instance)
        elif result["result"] is None and not result["action_events"] and not result["stdout"] and not result["stderr"] and policy["requires_action_event"]:
            error = "RuntimeError: EXECUTE produced no result, stdout, stderr, or recorded body action"
            failure = _failure("empty_execute_result")
    except Exception as exc:
        result = {
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "action_events": list(ns["_action_events"]),
        }
        error = f"{type(exc).__name__}: {exc}"
        failure = _failure("task_route_exception", exception_type=type(exc).__name__, message=str(exc))

    turn = dict(state.get("turn_executions") or {})
    turn[instance] = _turn_entry(code, result, error, failure)
    failed = {faculty: entry["error"] for faculty, entry in turn.items() if entry["error"] is not None}
    aggregate_error = None if not failed else "faculty failures: " + "; ".join(f"{faculty}={message}" for faculty, message in failed.items())
    aggregate_failure = None if not failed else _failure("faculty_failures", faculties=failed)
    action_names = [str(event.get("action", "action")) for event in result["action_events"]]
    deed = ", ".join(action_names) if action_names else "local computation"
    outcome = "success" if error is None else error
    effective = bus.append_narrative(state["effective_goal"], f"\n\n[{label}] {deed}: {outcome}.", root_goal=state.get("goal", ""))
    return bus.emit(
        "done",
        {
            "turn_executions": turn,
            "last_action": {"code": code, "faculty": instance, "repair_probe": probe},
            "last_action_at": time.time(),
            "last_code": code,
            "last_result": result,
            "last_error": aggregate_error,
            "last_failure": aggregate_failure,
            "action_frame": None if aggregate_error is None else state.get("action_frame"),
            "effective_goal": effective,
        },
    )
