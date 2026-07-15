"""[node_run] — the runner. Thou loadest the script artifact that [node_execute] wrote upon the disk,
and enactest it within the [capability namespace], emitting "done" with the [action_events] of the deed.

The script hath the [capability namespace] (desktop, subprocess, stdlib, and the rest) and recordeth
[action_events] as it acteth. A script that raiseth faileth hard and endeth the life; a script that
runneth yet worketh no effect is judged not here but by the witness, upon the fresh observation.
"""
import hashlib
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

    code = pathlib.Path(artifact["path"]).read_text(encoding="utf-8")

    import core_desktop as desktop

    ns = nodes.build_capability_runtime(ctx)
    ns["desktop"] = desktop
    exec(code, ns)

    turn = {FACULTY: {
        "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
        "code_chars": len(code),
        "action_events": list(ns["_action_events"]),
    }}
    return bus.emit(
        "done",
        {
            "turn_executions": turn,
            "last_action_at": time.time(),
            "action_frame": None,
            "_execute_artifact": None,
        },
    )
