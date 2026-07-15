"""[node_reflect] — Thou shalt consume a deed denied and its evidence; and thou shalt bring forth a causal lesson and choose retry, frame, or a named child sub-goal."""
import core_bus as bus
from core_node_base import BaseNode


class ReflectNode(BaseNode):
    prompt_key = "node_reflect"
    expected_record_type = "reflection"

    def _prepare(self, ctx):
        state = ctx["state"]
        self._streak_patch = bus.update_failure_streak(state)
        self._failure = state.get("last_failure") or {}
        self._evidence_payload = {
            "executions": bus.execution_evidence(state),
            "last_verification": state.get("last_verification", {}),
            "last_failure": self._failure,
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
        self._signal = data["next_signal"]
        return self._signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx["state"]
        deed = state.get("current_deed") or {}
        lesson, diagnosis = data["lesson"], data["diagnosis"]
        reflection = {
            "lesson": lesson,
            "diagnosis": diagnosis,
            "deed_goal": deed.get("description", state["goal"]),
            "recovery_signal": self._signal,
            "failure": self._failure,
            "action_frame": state.get("action_frame"),
        }
        patch = {
            **self._streak_patch,
            "action_frame": None,
            "reflection": reflection,
            "last_reflection": {
                "signal": self._signal,
                "lesson": lesson,
                "diagnosis": diagnosis,
                "failure": self._failure,
            },
            "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "reflect", str(data.get("goal_interpretation") or "")),
        }
        if self._signal == "spawn":
            subgoal = str(data.get("subgoal") or "").strip()
            if not subgoal:
                raise RuntimeError("reflection routed to spawn without a non-empty subgoal")
            patch["spawn_subgoal"] = subgoal
        return patch


def run(ctx):
    return ReflectNode().run(ctx)
