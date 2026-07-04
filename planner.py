from __future__ import annotations
from typing import Any
import bus
from node import LlmNode

class Planner(LlmNode):
    name = 'planner'
    record_type = 'plan'
    prompt_key = 'planner'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        return {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'state': bus.state_brief(state)}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        signal = str(data.get('next_signal') or 'step_ready')
        if signal not in {'step_ready', 'reflect'}:
            raise RuntimeError(f"planner invalid next_signal: {signal!r}")
        return signal

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        data = record.get('data', {})
        narration = str(data.get('goal_narration') or data.get('narration') or ctx.get('goal', '') or '')
        return {'plan': data, 'goal_narration': narration, 'step': 0, 'plan_complete': False, 'reasoning': record.get('reasoning', '')}

NODE = Planner()