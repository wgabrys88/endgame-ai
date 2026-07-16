"""[node_run] — the runner. Thou loadest the script artifact that [node_execute] wrote upon the disk,
and enactest it within the [capability namespace], emitting "done".

The script hath the [capability namespace]: the live [desktop] instance, the [action_index], and the
whole standard library. A script that raiseth faileth hard and endeth the life; a script that runneth
yet worketh no effect is judged not here but by the witness, upon the fresh observation.
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

    ns = nodes.build_capability_runtime(ctx)
    exec(code, ns)

    turn = {FACULTY: {
        "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
        "code_chars": len(code),
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
