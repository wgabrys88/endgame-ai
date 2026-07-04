from __future__ import annotations
from typing import Any
import body_signals
import bus
from node import LlmNode

class Planner(LlmNode):
    name = 'planner'
    record_type = 'plan'
    prompt_key = 'planner'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal_seed = state.get('goal_seed') or ctx.get('goal', '')
        return {'goal_seed': goal_seed, 'goal_narration': state.get('goal_narration', goal_seed), 'goal_signals': body_signals.collect(state), 'state': bus.state_brief(state), 'last_reflection': state.get('last_reflection', {}), 'last_verification': state.get('last_verification', {}), 'plan_context': {'step': state.get('step', 0), 'plan_complete': state.get('plan_complete', False), 'replan': bool((state.get('last_reflection') or {}).get('signal') == 'replan')}}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        signal = str(data.get('next_signal') or 'step_ready')
        if signal not in {'step_ready', 'reflect'}:
            signal = 'step_ready'
        return signal

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        data = record.get('data', {})
        narration = str(data.get('goal_narration') or data.get('narration') or '').strip()
        if not narration:
            raise RuntimeError('planner must emit non-empty goal_narration')
        intent = data.get('intent')
        if not isinstance(intent, list) or not intent:
            raise RuntimeError('planner must emit non-empty intent[]')
        plan = {'next_signal': data.get('next_signal', 'step_ready'), 'goal_narration': narration, 'intent': intent}
        signals = body_signals.collect(ctx.get('state', {}))
        return {'plan': plan, 'goal_narration': narration, 'goal_signals': signals, 'step': 0, 'plan_complete': False, 'reasoning': record.get('reasoning', '')}

NODE = Planner()