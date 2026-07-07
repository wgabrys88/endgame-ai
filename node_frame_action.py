from __future__ import annotations

import core_bus as bus
from core_node_base import BaseNode


DATASHEET = bus.datasheet(
    "node_frame_action",
    kind="llm_rod_framing_pass",
    inputs=["goal", "current_step", "last_action", "last_result", "last_error", "fresh_observation"],
    signals=["framed", "reflect", "error"],
    writes=["action_frame", "framing_attempted_for_step"],
    record_type="action_frame",
)


class FrameActionNode(BaseNode):

    prompt_key = "node_frame_action"
    expected_record_type = "action_frame"

    def _evidence(self, ctx):
        state = ctx.get("state", {})
        return {
            "state": bus.state_brief(state),
            "last_action": state.get("last_action", {}),
            "last_result": state.get("last_result", ""),
            "last_error": state.get("last_error", ""),
        }

    def evidence(self, ctx):
        return self._evidence(ctx)

    def build_payload(self, ctx):
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        goal = ctx.get("goal", "")
        return {
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": self._evidence(ctx),
            "observation": bus.observation_brief(state),
        }

    def signal_from_data(self, data, ctx):
        signal = data.get("next_signal")
        if signal not in {"framed", "reflect"}:
            raise RuntimeError(f"frame_action emitted invalid next_signal: {signal!r}")
        return signal

    def patch_from_record(self, record, ctx):
        data = record.data
        step_index = int(ctx.get("state", {}).get("step", 0) or 0)
        frame = {
            "screen_summary": data.get("screen_summary", ""),
            "target": data.get("target", ""),
            "strategy": data.get("strategy", ""),
            "risk": data.get("risk", "low"),
            "notes": data.get("notes", ""),
            "step_index": step_index,
        }
        return {"action_frame": frame, "framing_attempted_for_step": step_index}


def run(ctx):
    return FrameActionNode().run(ctx)
