from __future__ import annotations
from typing import Any
import bus
from node import LlmNode

class FrameAction(LlmNode):
    name = 'frame_action'
    record_type = 'action_frame'
    prompt_key = 'frame_action'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        return {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')}, 'evidence': {'state': bus.state_brief(state), 'last_action': state.get('last_action', {}), 'last_result': state.get('last_result', ''), 'last_error': state.get('last_error', '')}}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        signal = str(data.get('next_signal') or 'framed')
        if signal not in {'framed', 'reflect'}:
            raise RuntimeError(f"frame_action invalid next_signal: {signal!r}")
        return signal

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        data = record.get('data', {})
        step_index = int(state.get('step', 0) or 0)
        frame = {'screen_summary': data.get('screen_summary', ''), 'target': data.get('target', ''), 'strategy': data.get('strategy', ''), 'risk': data.get('risk', 'low'), 'notes': data.get('notes', ''), 'step_index': step_index}
        return {'action_frame': frame, 'framing_attempted_for_step': step_index}

NODE = FrameAction()