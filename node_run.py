"""[node_run] — the runner. Thou loadest the script artifact that [node_execute] wrote upon the disk,
and enactest it within the [capability namespace], emitting "done" with the evidence of the deed.

One [runner], no division of faculty. It runneth whatsoever script the executor authored.
The script hath the [capability namespace] (desktop, subprocess, tools, and the rest)
and setteth `result`, or printeth, or recordeth [action_events] as it seeth fit — there is
no per-faculty policy that gateth what shall count as success.
"""
import contextlib
import hashlib
import io
import pathlib
import time

import core_bus as bus
import core_nodes as nodes

FACULTY = "exec"


def run(ctx):
    state = ctx["state"]
    artifact = state.get("_execute_artifact")
    if not artifact:
        return bus.emit("done")

    label = artifact["label"]
    probe = artifact["repair_probe"]
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
    except Exception as exc:
        result = {
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "action_events": list(ns["_action_events"]),
        }
        error = f"{type(exc).__name__}: {exc}"
        failure = {"source": "execute", "kind": "task_route_exception", "contract_repair_allowed": False, "exception_type": type(exc).__name__, "message": str(exc)}

    turn = {FACULTY: {
        "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
        "code_chars": len(code),
        "result": result,
        "error": error,
        "failure": failure,
    }}
    action_names = [str(event.get("action", "action")) for event in result["action_events"]]
    deed = ", ".join(action_names) if action_names else "local computation"
    outcome = "success" if error is None else error
    effective = bus.append_narrative(state["effective_goal"], f"\n\n[{label}] {deed}: {outcome}.", root_goal=state.get("goal", ""))
    signal = "repair_done" if probe else "done"
    return bus.emit(
        signal,
        {
            "turn_executions": turn,
            "last_action": {"code_sha256": turn[FACULTY]["code_sha256"], "artifact": pathlib.Path(artifact["path"]).name, "repair_probe": probe},
            "last_action_at": time.time(),
            "last_code": code,
            "last_result": result,
            "last_error": error,
            "last_failure": failure,
            "action_frame": None if error is None else state.get("action_frame"),
            "_execute_artifact": None,
            "effective_goal": effective,
        },
    )
