from __future__ import annotations

import bus
from nodes import BaseNode


DATASHEET = bus.datasheet(
    "planner",
    kind="llm_intent_decomposer",
    inputs=["goal", "state_brief", "fresh_observation"],
    signals=["step_ready", "reflect", "error"],
    writes=["plan", "reasoning"],
    record_type="plan",
)


class PlannerNode(BaseNode):
    prompt_key = "planner"
    expected_record_type = "plan"

    def signal_from_data(self, data):
        signal = str(data.get("next_signal") or "step_ready")
        return signal if signal in {"step_ready", "reflect"} else "reflect"

    def patch_from_record(self, record):
        data = record.get("data", {})
        return {
            "plan": data,
            "step": 0,
            "plan_complete": False,
            "reasoning": record.get("reasoning", ""),
        }


def run(ctx):
    return PlannerNode().run(ctx)
