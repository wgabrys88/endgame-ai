from __future__ import annotations

import core_bus as bus
from core_node_base import BaseNode


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
        effective_goal = ctx.get("state", {}).get("effective_goal", ctx.get("goal", ""))
        return {
            "goal": effective_goal,
            "step": {"description": step_goal, "done_when": done_when},
            "evidence": self._evidence(ctx),
            "observation": bus.observation_brief(ctx.get("state", {})),
        }

    def signal_from_data(self, data, ctx):
        signal = data.get("next_signal")
        if signal not in ("step_confirmed", "step_denied"):
            raise RuntimeError(f"verification emitted invalid next_signal: {signal!r}")
        success = bool(data.get("success", False))
        if signal == "step_confirmed" and not success:
            raise RuntimeError("verification emitted step_confirmed with success=false")
        if success and signal != "step_confirmed":
            raise RuntimeError("verification emitted success=true without step_confirmed")
        self._success = success
        self._signal = signal
        return signal

    def patch_from_record(self, record, ctx):
        data = record.data
        state = ctx.get("state", {})
        step_goal, done_when = self._step_goal(ctx)
        patch: dict[str, object] = {
            "verification": {
                "success": self._success,
                "reasoning": data.get("reasoning", record.reasoning),
                "step_goal": step_goal,
                "done_when": done_when,
            },
            "last_verification": {"success": self._success, "signal": self._signal},
        }
        effective_goal = state.get("effective_goal", ctx.get("goal", ""))
        if self._success:
            completed_steps = list(state.get("completed_steps") or [])
            completed_steps.append({
                "description": step_goal,
                "done_when": done_when,
                "confirmed_at_tick": state.get("tick"),
            })
            effective_goal = f"{effective_goal}\n\n[VERIFY] Step confirmed: {step_goal[:100]}. Moving to next step."
        else:
            effective_goal = f"{effective_goal}\n\n[VERIFY] Step denied: {step_goal[:100]}. Evidence missing: {data.get('reasoning', '')[:100]}."
        patch["effective_goal"] = effective_goal
        if self._success:
            patch["step"] = int(state.get("step", 0) or 0) + 1
            patch["completed_steps"] = completed_steps
            patch["failure_streak"] = {"signature": None, "count": 0}
            patch["action_frame"] = None
        return patch


def run(ctx):
    return VerifyNode().run(ctx)
