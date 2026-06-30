from __future__ import annotations

from nodes import BaseNode


class VerifyNode(BaseNode):
    prompt_key = "verify"
    expected_record_type = "verification"
    
    def signal_from_data(self, data):
        return str(data.get("next_signal") or "planner")
    
    def patch_from_record(self, record):
        return {"verification": record.get("data", {})}


def run(ctx):
    return VerifyNode().run(ctx)