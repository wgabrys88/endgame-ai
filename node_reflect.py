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
    "no topology edge",
    "missing helper",
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
            "observation": bus.observation_brief(state),
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": self._evidence_payload,
            "routing_rule": {
                "retry": "same plan can work with a better concrete action or better target",
                "replan": "plan step is wrong or too coarse",
                "escalate": "organism wiring, prompt, code, observation, or transport contract is broken",
                "give_up": "goal is impossible or unsafe with current body",
            },
        }

    def signal_from_data(self, data, ctx):
        state = ctx.get("state", {})
        signal = data.get("next_signal", "replan")
        if signal not in {"retry", "replan", "frame", "escalate", "give_up"}:
            signal = "replan"

        step_index = int(state.get("step", 0) or 0)
        last_verification = state.get("last_verification") or {}
        diagnostic_text = " ".join(str(x) for x in [
            state.get("last_error", ""),
            data.get("diagnosis", ""),
            data.get("lesson", ""),
            state.get("last_action", {}),
        ])
        if (
            last_verification.get("signal") == "step_denied"
            and self._projected_streak["count"] >= 2
            and state.get("framing_attempted_for_step") != step_index
            and signal in {"retry", "replan"}
        ):
            signal = "frame"
        elif state.get("last_error") and any(
            marker.lower() in diagnostic_text.lower() for marker in MECHANICAL_ESCALATE_MARKERS
        ):
            signal = "escalate"
        self._signal = signal
        return signal

    def patch_from_record(self, record, ctx):
        data = record.get("data", {})
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
            },
            "last_reflection": {"signal": self._signal, "lesson": lesson, "diagnosis": diagnosis},
        }


def run(ctx):
    return ReflectNode().run(ctx)
