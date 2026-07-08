from __future__ import annotations

import core_bus as bus
from core_node_base import BaseNode


class VerifyNode(BaseNode):
    prompt_key = "node_verify"
    expected_record_type = "verification"

    def _step(self, ctx):
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        return step.get("description", ctx.get("goal", "")), step.get("done_when", "")

    def evidence(self, ctx):
        state = ctx.get("state", {})
        return {"last_action": state.get("last_action", {}), "last_result": state.get("last_result", ""), "last_error": state.get("last_error", ""), "state": bus.state_brief(state)}

    def build_payload(self, ctx):
        desc, done_when = self._step(ctx)
        return {"goal": ctx.get("state", {}).get("effective_goal", ctx.get("goal", "")), "step": {"description": desc, "done_when": done_when}, "evidence": self.evidence(ctx), "observation": bus.observation_brief(ctx.get("state", {}))}

    def signal_from_data(self, data, ctx):
        self._signal = data.get("next_signal")
        self._success = bool(data.get("success", False))
        if self._signal not in {"step_confirmed", "step_denied"} or (self._signal == "step_confirmed") != self._success:
            raise RuntimeError(f"verification invalid success/signal: {self._success!r}/{self._signal!r}")
        return self._signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx.get("state", {})
        desc, done_when = self._step(ctx)
        effective = state.get("effective_goal", ctx.get("goal", "")) + (f"\n\n[VERIFY] Step confirmed: {desc[:100]}. Moving to next step." if self._success else f"\n\n[VERIFY] Step denied: {desc[:100]}. Evidence missing: {data.get('reasoning', '')[:100]}.")
        patch: dict[str, object] = {"verification": {"success": self._success, "reasoning": data.get("reasoning", record.reasoning), "step_goal": desc, "done_when": done_when}, "last_verification": {"success": self._success, "signal": self._signal}, "effective_goal": effective}
        if self._success:
            completed = list(state.get("completed_steps") or [])
            completed.append({"description": desc, "done_when": done_when, "confirmed_at_tick": state.get("tick")})
            patch.update({"step": int(state.get("step", 0) or 0) + 1, "completed_steps": completed, "failure_streak": {"signature": None, "count": 0}, "action_frame": None})
        return patch


def run(ctx):
    return VerifyNode().run(ctx)
