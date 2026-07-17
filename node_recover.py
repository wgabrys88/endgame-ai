"""[node_recover] — You receive the denied deed, its evidence and failure_streak, and the fresh observation."""
import core_bus as bus
from core_node_base import BaseNode


class RecoverNode(BaseNode):
    prompt_key = "node_recover"
    expected_record_type = "recovery"

    def _prepare(self, ctx):
        state = ctx["state"]
        self._streak_patch = bus.bump_failure_streak(state)
        self._evidence_payload = {
            "executions": bus.execution_evidence(state),
            "last_verification": state.get("last_verification", {}),
            "failure_streak": self._streak_patch["failure_streak"],
        }

    def evidence(self, ctx):
        if not hasattr(self, "_evidence_payload"):
            self._prepare(ctx)
        return self._evidence_payload

    def build_payload(self, ctx):
        self._prepare(ctx)
        state = ctx["state"]
        deed = state.get("current_deed") or {}
        return {
            "goal": state["goal"],
            "deed": {"description": deed.get("description", state["goal"]), "done_when": deed.get("done_when", "")},
            "focus": bus.state_brief(state),
            "evidence": self._evidence_payload,
            "observation": bus.observation_brief(state),
        }

    def signal_from_data(self, data, ctx):
        return "recovered"

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx["state"]
        deed = state.get("current_deed") or {}
        action_frame = {
            "target": data["target"],
            "strategy": data["strategy"],
            "risk": data["risk"],
            "lesson": data["lesson"],
        }
        return {
            **self._streak_patch,
            "action_frame": action_frame,
            "last_recovery": {"lesson": data["lesson"], "target": data["target"], "strategy": data["strategy"], "deed_goal": deed.get("description", state["goal"])},
            "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "recover", str(data.get("goal_interpretation") or "")),
        }


def run(ctx):
    return RecoverNode().run(ctx)
