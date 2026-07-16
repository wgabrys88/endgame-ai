"""[node_execute] — the author-enactor. Thou discernest the single next deed toward
the goal, authorest [code] as one [Python] script, and straightway enactest it within
the [capability namespace]. There is no menu of tools; the [Python] language itself is
thy tool. A script that raiseth faileth hard and endeth the life; a script that runneth
yet worketh no effect is judged not here but by the witness, upon the fresh observation.

Whatsoever the script hath need of — desktop, files, shell, web, or the rewriting of the
body — it importeth and calleth of itself; and it may author a long, multi-chained script,
for decomposition liveth in the deed.
"""
import hashlib
import time

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
        done_when = str(data["done_when"]).strip()
        if not intent or not done_when:
            raise RuntimeError("execution requires non-empty intent and done_when")
        ns = nodes.build_capability_runtime(ctx)
        exec(code, ns)
        turn = {FACULTY: {
            "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
            "code_chars": len(code),
        }}
        interps = bus.with_interpretation(state.get("goal_interpretations"), "execute", str(data.get("goal_interpretation") or ""))
        return bus.emit(
            "done",
            {
                "current_deed": {"description": intent, "done_when": done_when},
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
