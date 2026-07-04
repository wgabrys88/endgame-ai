from __future__ import annotations
from typing import Any
import bus
from node import MechanicalNode

class Scheduler(MechanicalNode):
    name = 'scheduler'

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        state = ctx.get('state', {})
        plan_obj = state.get('plan', {})
        if isinstance(plan_obj, dict):
            plan = plan_obj.get('intent', [])
        elif isinstance(plan_obj, list):
            plan = plan_obj
        else:
            plan = []
        step_idx = int(state.get('step', 0) or 0)
        if step_idx >= len(plan):
            return bus.emit('plan_complete', {'plan_complete': True, 'current_step': None, 'action_frame': None})
        step = plan[step_idx] if isinstance(plan[step_idx], dict) else {'description': str(plan[step_idx]), 'done_when': ''}
        return bus.emit('step_ready', {'current_step': step, 'step_goal': step.get('description', str(step)), 'step': step_idx, 'action_frame': None, 'framing_attempted_for_step': None})

NODE = Scheduler()