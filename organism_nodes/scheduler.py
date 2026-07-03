from __future__ import annotations
import bus
DATASHEET = bus.datasheet('scheduler', kind='mechanical_step_selector', inputs=['plan.intent', 'state.step'], signals=['step_ready', 'plan_complete', 'error'], writes=['current_step', 'step_goal', 'step', 'action_frame'], record_type=None)

def run(ctx):
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
    step = plan[step_idx]
    if not isinstance(step, dict):
        step = {'description': str(step), 'done_when': ''}
    return bus.emit('step_ready', {'current_step': step, 'step_goal': step.get('description', str(step)), 'step': step_idx, 'action_frame': None, 'framing_attempted_for_step': None})