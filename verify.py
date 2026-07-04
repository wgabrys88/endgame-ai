from __future__ import annotations
from typing import Any
import bus
from node import LlmNode

class Verify(LlmNode):
    name = 'verify'
    record_type = 'verification'
    prompt_key = 'verify'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        return {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')}, 'evidence': {'last_action': state.get('last_action', {}), 'last_result': state.get('last_result', ''), 'last_error': state.get('last_error', ''), 'state': bus.state_brief(state)}}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        signal = str(data.get('next_signal') or 'step_denied')
        success = bool(data.get('success', False))
        if signal not in {'step_confirmed', 'step_denied'}:
            raise RuntimeError(f"verify invalid next_signal: {signal!r}")
        if signal == 'step_confirmed' and not success:
            return 'step_denied'
        if signal == 'step_denied' and success:
            raise RuntimeError('verify success=true conflicts with step_denied')
        return signal

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        data = record.get('data', {})
        success = bool(data.get('success', False))
        signal = self.signal(data, record)
        step_goal = step.get('description', goal)
        patch = {'verification': {'success': success, 'reasoning': data.get('reasoning', record.get('reasoning', '')), 'step_goal': step_goal, 'done_when': step.get('done_when', '')}, 'last_verification': {'success': success, 'signal': signal}}
        if success:
            patch['step'] = int(state.get('step', 0) or 0) + 1
            patch['failure_streak'] = {'signature': None, 'count': 0}
            patch['action_frame'] = None
        return patch

NODE = Verify()