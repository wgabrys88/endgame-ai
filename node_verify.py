from __future__ import annotations

import core_bus as bus
from core_nodes import BaseNode


DATASHEET = bus.datasheet(
    "node_verify",
    kind="llm_reality_comparator",
    inputs=["goal", "current_step", "last_action", "last_result", "last_error", "fresh_observation"],
    signals=["step_confirmed", "step_denied", "error"],
    writes=["verification", "last_verification", "step"],
    record_type="verification",
)


class VerifyNode(BaseNode):

    prompt_key = "node_verify"
    expected_record_type = "verification"

    def _step_goal(self, ctx):
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        return step.get("description", ctx.get("goal", "")), step.get("done_when", "")

    def _evidence(self, ctx):
        state = ctx.get("state", {})
        return {
            "last_action": state.get("last_action", {}),
            "last_result": state.get("last_result", ""),
            "last_error": state.get("last_error", ""),
            "state": bus.state_brief(state),
        }

    def evidence(self, ctx):
        return self._evidence(ctx)

    def build_payload(self, ctx):
        step_goal, done_when = self._step_goal(ctx)
        return {
            "goal": ctx.get("goal", ""),
            "step": {"description": step_goal, "done_when": done_when},
            "evidence": self._evidence(ctx),
            "observation": bus.observation_brief(ctx.get("state", {})),
        }

    def signal_from_data(self, data, ctx):
        signal = data.get("next_signal", "step_denied")
        success = bool(data.get("success", False))
        if signal not in ("step_confirmed", "step_denied"):
            signal, success = "step_denied", False
        if signal == "step_confirmed" and not success:
            signal = "step_denied"
        if success and signal != "step_confirmed":
            success = False
        self._success = success
        self._signal = signal
        return signal

    def patch_from_record(self, record, ctx):
        data = record.get("data", {})
        state = ctx.get("state", {})
        step_goal, done_when = self._step_goal(ctx)
        patch = {
            "verification": {
                "success": self._success,
                "reasoning": data.get("reasoning", record.get("reasoning", "")),
                "step_goal": step_goal,
                "done_when": done_when,
            },
            "last_verification": {"success": self._success, "signal": self._signal},
        }
        if self._success:
            patch["step"] = int(state.get("step", 0) or 0) + 1
            patch["failure_streak"] = {"signature": None, "count": 0}
            patch["action_frame"] = None
        return patch


def run(ctx):
    return VerifyNode().run(ctx)
