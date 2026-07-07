from __future__ import annotations

import core_bus as bus
from core_nodes import BaseNode


DATASHEET = bus.datasheet(
    "node_reflect",
    kind="llm_diagnostic_router",
    inputs=["goal", "current_step", "last_action", "last_result", "last_error", "last_verification", "failure_streak"],
    signals=["retry", "replan", "frame", "escalate", "give_up", "error"],
    writes=["reflection", "last_reflection", "failure_streak"],
    record_type="reflection",
)


MECHANICAL_ESCALATE_MARKERS = (
    "NameError",
    "AttributeError",
    "SyntaxError",
    "ImportError",
    "RuntimeError",
    "ValueError",
    "no topology edge",
    "missing helper",
    "body action failed",
    "produced no result",
)


class ReflectNode(BaseNode):

    prompt_key = "node_reflect"
    expected_record_type = "reflection"

    def _prepare(self, ctx):
        state = ctx.get("state", {})
        self._streak_patch = bus.update_failure_streak(state)
        self._projected_streak = self._streak_patch["failure_streak"]
        self._evidence_payload = {
            "last_action": state.get("last_action", {}),
            "last_result": state.get("last_result", ""),
            "last_error": state.get("last_error", ""),
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
        goal = ctx.get("goal", "")
        return {
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": self._evidence_payload,
            "observation": bus.observation_brief(state),
        }

    def signal_from_data(self, data, ctx):
        state = ctx.get("state", {})
        requested_signal = data.get("next_signal")
        signal = requested_signal
        if signal not in {"retry", "replan", "frame", "escalate", "give_up"}:
            raise RuntimeError(f"reflection emitted invalid next_signal: {signal!r}")

        step_index = int(state.get("step", 0) or 0)
        last_verification = state.get("last_verification") or {}
        framed_already = state.get("framing_attempted_for_step") == step_index
        diagnostic_text = " ".join(str(x) for x in [
            state.get("last_error", ""),
            data.get("diagnosis", ""),
            data.get("lesson", ""),
            state.get("last_action", {}),
            state.get("last_result", {}),
        ])
        self._routing_override = None
        if (
            last_verification.get("signal") == "step_denied"
            and self._projected_streak["count"] >= 2
            and not framed_already
            and signal in {"retry", "replan"}
        ):
            self._routing_override = {
                "from": requested_signal,
                "to": "frame",
                "reason": "same step denied twice before any action frame",
                "failure_streak": self._projected_streak,
            }
            signal = "frame"
        elif (
            last_verification.get("signal") == "step_denied"
            and self._projected_streak["count"] >= 3
            and framed_already
            and signal in {"retry", "replan", "frame"}
        ):
            self._routing_override = {
                "from": requested_signal,
                "to": "escalate",
                "reason": "same step denied after framing was already attempted",
                "failure_streak": self._projected_streak,
            }
            signal = "escalate"
        elif state.get("last_error") and any(
            marker.lower() in diagnostic_text.lower() for marker in MECHANICAL_ESCALATE_MARKERS
        ):
            if signal != "escalate":
                self._routing_override = {
                    "from": requested_signal,
                    "to": "escalate",
                    "reason": "mechanical error marker in reflection evidence",
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
        return {
            **self._streak_patch,
            "reflection": {
                "lesson": lesson,
                "diagnosis": diagnosis,
                "step_goal": step.get("description", ctx.get("goal", "")),
                "recovery_signal": self._signal,
                "requested_signal": data.get("next_signal"),
                "routing_override": self._routing_override,
            },
            "last_reflection": {
                "signal": self._signal,
                "requested_signal": data.get("next_signal"),
                "lesson": lesson,
                "diagnosis": diagnosis,
                "routing_override": self._routing_override,
            },
        }


def run(ctx):
    return ReflectNode().run(ctx)
