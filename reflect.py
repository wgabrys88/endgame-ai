from __future__ import annotations
from typing import Any
import bus
from node import LlmNode

class Reflect(LlmNode):
    name = 'reflect'
    record_type = 'reflection'
    prompt_key = 'reflect'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        streak_patch = bus.update_failure_streak(state)
        return {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')}, 'evidence': {'last_action': state.get('last_action', {}), 'last_result': state.get('last_result', ''), 'last_error': state.get('last_error', ''), 'last_verification': state.get('last_verification', {}), 'failure_streak': streak_patch['failure_streak'], 'state': bus.state_brief(state)}, 'routing_rule': {'retry': 'same plan can work with a better concrete action or better target', 'replan': 'plan step is wrong or too coarse', 'escalate': 'organism wiring, prompt, code, observation, or transport contract is broken', 'give_up': 'goal is impossible or unsafe with current body'}}

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        signal = str(data.get('next_signal') or 'replan')
        if signal not in {'retry', 'replan', 'escalate', 'give_up'}:
            raise RuntimeError(f"reflect invalid next_signal: {signal!r}")
        return signal

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        data = record.get('data', {})
        signal = self.signal(data, record)
        streak_patch = bus.update_failure_streak(state)
        lesson = data.get('lesson', 'No lesson provided')
        diagnosis = data.get('diagnosis', 'No diagnosis')
        return {**streak_patch, 'reflection': {'lesson': lesson, 'diagnosis': diagnosis, 'step_goal': step.get('description', goal), 'recovery_signal': signal}, 'last_reflection': {'signal': signal, 'lesson': lesson, 'diagnosis': diagnosis}}

NODE = Reflect()