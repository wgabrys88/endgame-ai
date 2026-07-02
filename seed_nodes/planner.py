from __future__ import annotations

from nodes import BaseNode


class PlannerNode(BaseNode):
    prompt_key = "planner"
    expected_record_type = "plan"
    
    def signal_from_data(self, data):
        return str(data.get("next_signal") or "step_ready")
    
    def patch_from_record(self, record):
        return {"plan": record.get("data", {}), "reasoning": record.get("reasoning", "")}


def run(ctx):
    return PlannerNode().run(ctx)
