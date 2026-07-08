from __future__ import annotations

import core_bus as bus
from core_node_base import BaseNode


CONTRACT_FAILURE_KINDS = {
    "topology_contract_violation",
    "observation_contract_violation",
    "capability_manifest_contract_violation",
    "wiring_patch_contract_violation",
    "node_record_contract_violation",
}

TASK_ROUTE_KINDS = {
    "task_route_exception",
    "task_route_decision",
    "empty_execute_result",
    "duration_guard",
}


class ReflectNode(BaseNode):

    prompt_key = "node_reflect"
    expected_record_type = "reflection"

    def _prepare(self, ctx):
        state = ctx.get("state", {})
        self._streak_patch = bus.update_failure_streak(state)
        self._projected_streak = self._streak_patch["failure_streak"]
        self._failure = state.get("last_failure") or {}
        self._evidence_payload = {
            "last_action": state.get("last_action", {}),
            "last_result": state.get("last_result", ""),
            "last_error": state.get("last_error", ""),
            "last_failure": self._failure,
            "last_verification": state.get("last_verification", {}),
            "failure_streak": self._projected_streak,
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
        goal = state.get("effective_goal", ctx.get("goal", ""))
        return {
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": self._evidence_payload,
            "observation": bus.observation_brief(state),
            "routing_contract": {
                "ordinary_execute_exceptions_are_task_route": True,
                "task_route_signals": ["frame", "replan", "retry"],
                "self_modify_signal": "escalate only for structured consumed organism-contract failure",
                "contract_failure_kinds": sorted(CONTRACT_FAILURE_KINDS),
            },
        }

    def _is_contract_failure(self) -> bool:
        if self._failure.get("source") == "execute":
            return False
        kind = str(self._failure.get("kind") or "")
        return bool(self._failure.get("contract_repair_allowed")) and kind in CONTRACT_FAILURE_KINDS

    def _is_task_route_failure(self) -> bool:
        kind = str(self._failure.get("kind") or "")
        if kind in TASK_ROUTE_KINDS:
            return True
        return self._failure.get("source") == "execute" and not self._failure.get("contract_repair_allowed")

    def _task_route_signal(self, state: dict) -> str:
        step_index = int(state.get("step", 0) or 0)
        framed_already = state.get("framing_attempted_for_step") == step_index or bool(state.get("action_frame"))
        last_verification = state.get("last_verification") or {}
        limit_hit = bool(bus.observation_brief(state).get("llm_node_limit_hit"))
        count = int(self._projected_streak.get("count", 0) or 0)
        if limit_hit and not framed_already:
            return "frame"
        if not framed_already:
            return "frame"
        if last_verification.get("signal") == "step_denied" and count <= 2:
            return "retry"
        return "replan"

    def signal_from_data(self, data, ctx):
        state = ctx.get("state", {})
        requested_signal = data.get("next_signal")
        if requested_signal not in {"retry", "replan", "frame", "escalate", "give_up", "topology_patch"}:
            raise RuntimeError(f"reflection emitted invalid next_signal: {requested_signal!r}")

        self._routing_override = None
        signal = requested_signal
        contract_failure = self._is_contract_failure()
        task_route_failure = self._is_task_route_failure()

        if signal == "escalate" and not contract_failure:
            replacement = self._task_route_signal(state) if task_route_failure else "replan"
            self._routing_override = {
                "from": requested_signal,
                "to": replacement,
                "reason": "escalation blocked: no structured consumed organism-contract failure",
                "failure": self._failure,
                "failure_streak": self._projected_streak,
            }
            signal = replacement
        elif task_route_failure:
            replacement = self._task_route_signal(state)
            if replacement != signal:
                self._routing_override = {
                    "from": requested_signal,
                    "to": replacement,
                    "reason": "task-route failure overridden to appropriate route (retry/frame/replan) per routing contract",
                    "failure": self._failure,
                    "failure_streak": self._projected_streak,
                }
            signal = replacement
        elif contract_failure and signal != "escalate" and int(self._projected_streak.get("count", 0) or 0) >= 2:
            self._routing_override = {
                "from": requested_signal,
                "to": "escalate",
                "reason": "repeated structured organism-contract failure",
                "failure": self._failure,
                "failure_streak": self._projected_streak,
            }
            signal = "escalate"

        self._signal = signal
        return signal

    def patch_from_record(self, record, ctx):
        data = record.data
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        lesson = data.get("lesson", "No lesson provided")
        diagnosis = data.get("diagnosis", "No diagnosis")
        effective_goal = state.get("effective_goal", ctx.get("goal", ""))
        signal_desc = {"retry": "retry with fresh observation", "replan": "replan from scratch", "frame": "focus observation", "escalate": "escalate to self-modify", "give_up": "give up", "topology_patch": "propose topology change"}.get(self._signal, self._signal)
        effective_goal = f"{effective_goal}\n\n[REFLECT] Routed to {signal_desc}. Lesson: {lesson[:100]}. Diagnosis: {diagnosis[:100]}."
        patch = {
            **self._streak_patch,
            "reflection": {
                "lesson": lesson,
                "diagnosis": diagnosis,
                "step_goal": step.get("description", ctx.get("goal", "")),
                "recovery_signal": self._signal,
                "requested_signal": data.get("next_signal"),
                "routing_override": self._routing_override,
                "failure": self._failure,
            },
            "last_reflection": {
                "signal": self._signal,
                "requested_signal": data.get("next_signal"),
                "lesson": lesson,
                "diagnosis": diagnosis,
                "routing_override": self._routing_override,
                "failure": self._failure,
            },
            "effective_goal": effective_goal,
        }
        if self._signal == "topology_patch" and "topology_patch" in data:
            patch["topology_patch"] = data["topology_patch"]
        return patch


def run(ctx):
    return ReflectNode().run(ctx)
