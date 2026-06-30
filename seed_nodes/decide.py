from __future__ import annotations

from nodes import BaseNode


class DecideNode(BaseNode):
    prompt_key = "decide"
    expected_record_type = "decision"
    
    def signal_from_data(self, data):
        return str(data.get("next_signal") or "act")
    
    def patch_from_record(self, record):
        data = record.get("data", {})
        return {"decision": data, "pending_action": data.get("action", {"verb": "noop"})}


def run(ctx):
    return DecideNode().run(ctx)