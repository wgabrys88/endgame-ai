"""[node_verify] — Thou judgest whether the step's [done_when] is fulfilled by the effect beheld. THOU EXPECTEST: the [current_step] (description and done_when), the observation after the deed, the [turn_executions] and evidence of the deed, the [completed_steps], the [step] index, the [tick], and [observed_at] with [last_action_at] for freshness. Thou emittest 'step_confirmed' (success true) or 'step_denied' (success false) with a verification record."""
import core_bus as bus
from core_node_base import BaseNode


class VerifyNode(BaseNode):
    prompt_key = "node_verify"
    expected_record_type = "verification"

    def _step(self, ctx):
        state = ctx["state"]
        step = state.get("current_step") or {}
        return step.get("description", state["goal"]), step.get("done_when", "")

    def evidence(self, ctx):
        return bus.execution_evidence(ctx["state"])

    def build_payload(self, ctx):
        state = ctx["state"]
        desc, done_when = self._step(ctx)
        observation = bus.observation_brief(state)
        observed_at = state.get("observed_at")
        last_action_at = state.get("last_action_at")
        observation["observation_fresh"] = bool(
            observed_at is not None and (last_action_at is None or float(observed_at) > float(last_action_at))
        )
        return {
            "goal": state["goal"],
            "step": {"description": desc, "done_when": done_when},
            "focus": bus.state_brief(state),
            "evidence": self.evidence(ctx),
            "observation": observation,
        }

    def signal_from_data(self, data, ctx):
        self._success = data["success"]
        self._signal = "step_confirmed" if self._success else "step_denied"
        return self._signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx["state"]
        desc, done_when = self._step(ctx)
        reason = data["reason"]
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[VERIFY] {'Confirmed' if self._success else 'Denied'}: {desc}. {reason}", root_goal=state.get("goal", ""))
        patch = {
            "verification": {"success": self._success, "reasoning": reason, "step_goal": desc, "done_when": done_when},
            "last_verification": {"success": self._success, "signal": self._signal, "reasoning": reason},
            "effective_goal": effective,
        }
        if self._success:
            completed = list(state.get("completed_steps") or [])
            completed.append({"description": desc, "done_when": done_when, "confirmed_at_tick": state.get("tick")})
            patch.update({"step": int(state.get("step", 0) or 0) + 1, "completed_steps": completed, "failure_streak": {"signature": None, "count": 0}, "action_frame": None, "last_error": None, "last_failure": None})
        return patch


def run(ctx):
    return VerifyNode().run(ctx)
