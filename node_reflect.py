import core_bus as bus
from core_node_base import BaseNode


class ReflectNode(BaseNode):
    prompt_key = "node_reflect"
    expected_record_type = "reflection"

    def _prepare(self, ctx):
        state = ctx["state"]
        self._streak_patch = bus.update_failure_streak(state)
        self._failure = state.get("last_failure") or {}
        self._repair_validation = bus.repair_validation_brief(state)
        self._evidence_payload = {
            "executions": bus.execution_evidence(state),
            "last_verification": state.get("last_verification", {}),
            "last_failure": self._failure,
            "failure_streak": self._streak_patch["failure_streak"],
            "repair_validation": self._repair_validation,
            "last_repair_validation": state.get("last_repair_validation", {}),
        }

    def evidence(self, ctx):
        if not hasattr(self, "_evidence_payload"):
            self._prepare(ctx)
        return self._evidence_payload

    def build_payload(self, ctx):
        self._prepare(ctx)
        state = ctx["state"]
        step = state.get("current_step") or {}
        return {
            "goal": state["goal"],
            "step": {"description": step.get("description", state["goal"]), "done_when": step.get("done_when", "")},
            "focus": bus.state_brief(state),
            "evidence": self._evidence_payload,
            "observation": bus.observation_brief(state),
        }

    def signal_from_data(self, data, ctx):
        self._signal = data["next_signal"]
        return self._signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx["state"]
        step = state.get("current_step") or {}
        lesson, diagnosis = data["lesson"], data["diagnosis"]
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[REFLECT] {self._signal}. Lesson: {lesson}. Diagnosis: {diagnosis}.", root_goal=state.get("goal", ""))
        reflection = {
            "lesson": lesson,
            "diagnosis": diagnosis,
            "step_goal": step.get("description", state["goal"]),
            "recovery_signal": self._signal,
            "failure": self._failure,
            "repair_validation": self._repair_validation,
        }
        patch = {
            **self._streak_patch,
            "reflection": reflection,
            "last_reflection": {
                "signal": self._signal,
                "lesson": lesson,
                "diagnosis": diagnosis,
                "failure": self._failure,
                "repair_validation_status": self._repair_validation.get("status"),
            },
            "effective_goal": effective,
        }
        if self._signal == "topology_patch" and "topology_patch" in data:
            patch["topology_patch"] = data["topology_patch"]
        return patch


def run(ctx):
    return ReflectNode().run(ctx)
