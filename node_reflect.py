import core_bus as bus
from core_node_base import BaseNode

CONTRACT_FAILURE_KINDS = {"topology_contract_violation", "observation_contract_violation", "capability_manifest_contract_violation", "wiring_patch_contract_violation", "node_record_contract_violation"}
TASK_ROUTE_KINDS = {"task_route_exception", "task_route_decision", "empty_execute_result", "duration_guard"}


class ReflectNode(BaseNode):
    prompt_key = "node_reflect"
    expected_record_type = "reflection"

    def _prepare(self, ctx):
        state = ctx.get("state", {})
        self._streak_patch = bus.update_failure_streak(state)
        self._projected_streak = self._streak_patch["failure_streak"]
        self._failure = state.get("last_failure") or {}
        self._evidence_payload = {"last_action": state.get("last_action", {}), "last_result": state.get("last_result", ""), "last_error": state.get("last_error", ""), "last_failure": self._failure, "last_verification": state.get("last_verification", {}), "failure_streak": self._projected_streak, "state": bus.state_brief(state)}

    def evidence(self, ctx):
        if not hasattr(self, "_evidence_payload"):
            self._prepare(ctx)
        return self._evidence_payload

    def build_payload(self, ctx):
        self._prepare(ctx)
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        return {"goal": state["effective_goal"], "step": {"description": step.get("description", ctx.get("goal", "")), "done_when": step.get("done_when", "")}, "evidence": self._evidence_payload, "observation": bus.observation_brief(state), "routing_contract": {"task_route_signals": ["frame", "replan", "retry"], "self_modify_signal": "escalate/topology_patch for consumed organism changes", "contract_failure_kinds": sorted(CONTRACT_FAILURE_KINDS)}}

    def _contract_failure(self) -> bool:
        return self._failure.get("source") != "execute" and bool(self._failure.get("contract_repair_allowed")) and str(self._failure.get("kind") or "") in CONTRACT_FAILURE_KINDS

    def _task_route_failure(self) -> bool:
        kind = str(self._failure.get("kind") or "")
        return kind in TASK_ROUTE_KINDS or (self._failure.get("source") == "execute" and not self._failure.get("contract_repair_allowed"))

    def _task_signal(self, state: dict) -> str:
        step = int(state.get("step", 0) or 0)
        framed = state.get("framing_attempted_for_step") == step or bool(state.get("action_frame"))
        if bool(bus.observation_brief(state).get("llm_node_limit_hit")) and not framed:
            return "frame"
        if not framed:
            return "frame"
        if (state.get("last_verification") or {}).get("signal") == "step_denied" and int(self._projected_streak.get("count", 0) or 0) <= 2:
            return "retry"
        return "replan"

    def signal_from_data(self, data, ctx):
        requested = data.get("next_signal")
        if requested not in {"retry", "replan", "frame", "escalate", "give_up", "topology_patch", "spawn"}:
            raise RuntimeError(f"reflection emitted invalid next_signal: {requested!r}")
        state = ctx.get("state", {})
        signal = requested
        self._routing_override = None
        if signal == "escalate" and not self._contract_failure():
            signal = self._task_signal(state) if self._task_route_failure() else "replan"
        elif self._task_route_failure():
            signal = self._task_signal(state)
        elif self._contract_failure() and signal != "escalate" and int(self._projected_streak.get("count", 0) or 0) >= 2:
            signal = "escalate"
        if signal != requested:
            self._routing_override = {"from": requested, "to": signal, "failure": self._failure, "failure_streak": self._projected_streak}
        self._signal = signal
        return signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx.get("state", {})
        step = state.get("current_step") or {}
        lesson = data.get("lesson", "No lesson provided")
        diagnosis = data.get("diagnosis", "No diagnosis")
        effective = state["effective_goal"] + f"\n\n[REFLECT] Routed to {self._signal}. Lesson: {lesson}. Diagnosis: {diagnosis}."
        reflection = {"lesson": lesson, "diagnosis": diagnosis, "step_goal": step.get("description", ctx.get("goal", "")), "recovery_signal": self._signal, "requested_signal": data.get("next_signal"), "routing_override": self._routing_override, "failure": self._failure}
        patch = {**self._streak_patch, "reflection": reflection, "last_reflection": {"signal": self._signal, "requested_signal": data.get("next_signal"), "lesson": lesson, "diagnosis": diagnosis, "routing_override": self._routing_override, "failure": self._failure}, "effective_goal": effective}
        if self._signal == "topology_patch" and "topology_patch" in data:
            patch["topology_patch"] = data["topology_patch"]
        return patch


def run(ctx):
    return ReflectNode().run(ctx)
