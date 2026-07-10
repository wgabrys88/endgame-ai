import core_bus as bus
from core_node_base import BaseNode


class ReflectNode(BaseNode):
    prompt_key = "node_reflect"
    expected_record_type = "reflection"

    def _prepare(self, ctx):
        state = ctx.get("state", {})
        self._streak_patch = bus.update_failure_streak(state)
        self._failure = state.get("last_failure") or {}
        self._evidence_payload = {
            "last_action": state.get("last_action", {}),
            "last_result": state.get("last_result", ""),
            "last_error": state.get("last_error", ""),
            "last_failure": self._failure,
            "last_verification": state.get("last_verification", {}),
            "failure_streak": self._streak_patch["failure_streak"],
            "state": bus.state_brief(state),
        }

    def evidence(self, ctx):
        if not hasattr(self, "_evidence_payload"):
            self._prepare(ctx)
        return self._evidence_payload

    def build_payload(self, ctx):
        self._prepare(ctx)
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        return {
            "goal": state["effective_goal"],
            "step": {"description": step.get("description", ctx.get("goal", "")), "done_when": step.get("done_when", "")},
            "evidence": self._evidence_payload,
            "observation": bus.observation_brief(state),
        }

    def signal_from_data(self, data, ctx):
        self._signal = data["next_signal"]
        return self._signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx.get("state", {})
        step = state.get("current_step") or {}
        lesson = data["lesson"]
        diagnosis = data["diagnosis"]
        effective = state["effective_goal"] + f"\n\n[REFLECT] Routed to {self._signal}. Lesson: {lesson}. Diagnosis: {diagnosis}."
        reflection = {
            "lesson": lesson,
            "diagnosis": diagnosis,
            "step_goal": step.get("description", ctx.get("goal", "")),
            "recovery_signal": self._signal,
            "failure": self._failure,
        }
        patch = {
            **self._streak_patch,
            "reflection": reflection,
            "last_reflection": {"signal": self._signal, "lesson": lesson, "diagnosis": diagnosis, "failure": self._failure},
            "effective_goal": effective,
        }
        if self._signal == "topology_patch" and "topology_patch" in data:
            patch["topology_patch"] = data["topology_patch"]
        return patch


def run(ctx):
    return ReflectNode().run(ctx)
