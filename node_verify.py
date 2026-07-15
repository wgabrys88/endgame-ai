"""[node_verify] — Thou judgest, by the effect beheld, both whether the last deed's [done_when] is fulfilled and whether the whole goal standeth accomplished. THOU EXPECTEST: the [current_deed] (description and done_when), the observation after the deed, the [turn_executions] and evidence of the deed, the [tick], and [observed_at] with [last_action_at] for freshness. Thou emittest 'goal_satisfied', 'deed_confirmed', or 'deed_denied' with a verification record."""
import core_bus as bus
from core_node_base import BaseNode


class VerifyNode(BaseNode):
    prompt_key = "node_verify"
    expected_record_type = "verification"

    def _deed(self, ctx):
        state = ctx["state"]
        deed = state.get("current_deed") or {}
        return deed.get("description", state["goal"]), deed.get("done_when", "")

    def evidence(self, ctx):
        return bus.execution_evidence(ctx["state"])

    def build_payload(self, ctx):
        state = ctx["state"]
        desc, done_when = self._deed(ctx)
        observation = bus.observation_brief(state)
        observed_at = state.get("observed_at")
        last_action_at = state.get("last_action_at")
        observation["observation_fresh"] = bool(
            observed_at is not None and (last_action_at is None or float(observed_at) > float(last_action_at))
        )
        return {
            "goal": state["goal"],
            "deed": {"description": desc, "done_when": done_when},
            "focus": bus.state_brief(state),
            "evidence": self.evidence(ctx),
            "observation": observation,
        }

    def signal_from_data(self, data, ctx):
        self._goal_satisfied = bool(data["goal_satisfied"])
        self._deed_confirmed = bool(data["deed_confirmed"])
        if self._goal_satisfied:
            self._signal = "goal_satisfied"
        elif self._deed_confirmed:
            self._signal = "deed_confirmed"
        else:
            self._signal = "deed_denied"
        return self._signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx["state"]
        desc, done_when = self._deed(ctx)
        reason = data["reason"]
        confirmed = self._goal_satisfied or self._deed_confirmed
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[VERIFY] {'Confirmed' if confirmed else 'Denied'}: {desc}. {reason}", root_goal=state.get("goal", ""))
        patch = {
            "verification": {"goal_satisfied": self._goal_satisfied, "deed_confirmed": self._deed_confirmed, "reasoning": reason, "deed_goal": desc, "done_when": done_when},
            "last_verification": {"success": confirmed, "signal": self._signal, "reasoning": reason},
            "effective_goal": effective,
        }
        if confirmed:
            witnessed = list(state.get("witnessed_deeds") or [])
            witnessed.append({"description": desc, "done_when": done_when, "confirmed_at_tick": state.get("tick")})
            patch.update({"witnessed_deeds": witnessed, "failure_streak": {"signature": None, "count": 0}, "action_frame": None, "current_deed": None, "last_error": None, "last_failure": None})
        return patch


def run(ctx):
    return VerifyNode().run(ctx)
