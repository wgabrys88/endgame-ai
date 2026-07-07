from __future__ import annotations

import core_bus as bus
from core_nodes import BaseNode


DATASHEET = bus.datasheet(
    "node_planner",
    kind="llm_intent_decomposer",
    inputs=["goal", "state_brief", "fresh_observation"],
    signals=["step_ready", "reflect", "error"],
    writes=["plan", "reasoning"],
    record_type="plan",
)


class PlannerNode(BaseNode):
    prompt_key = "node_planner"
    expected_record_type = "plan"

    def signal_from_data(self, data, ctx):
        signal = data.get("next_signal")
        if signal not in {"step_ready", "reflect"}:
            raise RuntimeError(f"planner emitted invalid next_signal: {signal!r}")
        return signal

    def patch_from_record(self, record, ctx):
        data = record.data
        return {
            "plan": data,
            "step": 0,
            "plan_complete": False,
            "reasoning": record.reasoning,
        }


def run(ctx):
    return PlannerNode().run(ctx)
