"""node_run — the runner. Loads the script artifact node_execute wrote to disk and
executes it in the capability namespace, emitting "done" with execution evidence.

One runner, no faculty distinction. It runs whatever script the executor authored.
The script has access to the capability namespace (desktop, subprocess, tools, etc.)
and sets `result` / prints / records action_events as it sees fit — there is no
per-faculty policy gating what counts as success.
"""
import contextlib
import hashlib
import io
import pathlib
import time

import core_bus as bus
import core_nodes as nodes

FACULTY = "exec"
MAX_RESULT_CHARS = 12000


def _bound(value):
    """Cap any captured execution output so a single script's stdout cannot flood the shared
    narrative and inflate every subsequent prompt. Keeps head + tail; a bounded slice is evidence
    enough, and the runner can page or slice large output deliberately when a step needs it."""
    text = value if isinstance(value, str) else repr(value) if value is not None else None
    if text is None:
        return None
    if len(text) <= MAX_RESULT_CHARS:
        return text
    half = MAX_RESULT_CHARS // 2
    return f"{text[:half]}\n...[{len(text) - MAX_RESULT_CHARS} chars truncated by runner bound]...\n{text[-half:]}"


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
            "result": _bound(ns.get("result")),
            "stdout": _bound(stdout.getvalue()),
            "stderr": _bound(stderr.getvalue()),
            "action_events": list(ns["_action_events"]),
        }
    except Exception as exc:
        result = {
            "stdout": _bound(stdout.getvalue()),
            "stderr": _bound(stderr.getvalue()),
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
            "_execute_artifact": None,
            "effective_goal": effective,
        },
    )
