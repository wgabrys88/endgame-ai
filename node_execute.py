"""[node_execute] — Thou receivest one fresh observation and any [action_frame]."""
import hashlib
import time
import traceback

import core_bus as bus
import core_nodes as nodes
from core_node_base import BaseNode

FACULTY = "exec"


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"

    def build_payload(self, ctx):
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "action_frame": state.get("action_frame"),
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
        }

    def run(self, ctx):
        state = ctx["state"]
        record = self.think(ctx)
        data = record.data
        code = data["code"]
        intent = str(data["intent"]).strip()
        if not intent:
            raise RuntimeError("execution requires non-empty intent")
        ns = nodes.build_capability_runtime(ctx)
        deed_fault = None
        try:
            exec(code, ns)
        except Exception:
            deed_fault = traceback.format_exc()
        turn = {FACULTY: {
            "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
            "code_chars": len(code),
            "deed_fault": deed_fault,
        }}
        interps = bus.with_interpretation(state.get("goal_interpretations"), "execute", str(data.get("goal_interpretation") or ""))
        return bus.emit(
            "deed_denied" if deed_fault else "done",
            {
                "current_deed": {"description": intent},
                "goal_interpretations": interps,
                "turn_executions": turn,
                "last_action_at": time.time(),
                "action_frame": None,
            },
            record=record,
            evidence=self.build_payload(ctx),
        )


def run(ctx):
    return ExecuteNode().run(ctx)
