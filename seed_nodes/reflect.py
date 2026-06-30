from __future__ import annotations

from nodes import BaseNode


class ReflectNode(BaseNode):
    prompt_key = "reflect"
    expected_record_type = "reflection"
    
    def signal_from_data(self, data):
        return str(data.get("next_signal") or "planner")
    
    def patch_from_record(self, record):
        return {"reflection": record.get("data", {})}


def run(ctx):
    return ReflectNode().run(ctx)