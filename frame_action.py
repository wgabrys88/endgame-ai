from __future__ import annotations
from typing import Any
import bus
import capability
from node import LlmNode

class FrameAction(LlmNode):
    name = 'frame_action'
    record_type = 'action_frame'
    prompt_key = 'frame_action'

    def payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        step_index = int(state.get('step', 0) or 0)
        return {
            'goal': goal,
            'goal_narration': state.get('goal_narration', goal),
            'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', ''), 'step_index': step_index},
            'observation': bus.observation_brief(state),
            'action_index': bus.action_index_brief(state),
            'prior_action_frame': state.get('action_frame'),
            'capability_contract': capability.CAPABILITY_CONTRACT,
            'evidence': {
                'state': bus.state_brief(state),
                'last_action': state.get('last_action', {}),
                'last_result': state.get('last_result', ''),
                'last_error': state.get('last_error', ''),
                'last_code': state.get('last_code', ''),
            },
            'framing_context': {
                'why': 'execute returned CANNOT/FRAME or failed; produce one concrete strategy before retry.',
                'target_format': "click_node('ui_N') | focus_window('title') | pyautogui.write after click_node",
                'must_cite': 'action_index id and SEMANTIC_UI role that satisfies step.done_when',
            },
        }

    def signal(self, data: dict[str, Any], record: dict[str, Any]) -> str:
        signal = str(data.get('next_signal') or 'framed')
        if signal not in {'framed', 'reflect'}:
            raise RuntimeError(f"frame_action invalid next_signal: {signal!r}")
        return signal

    def patch(self, record: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get('state', {})
        data = record.get('data', {})
        step_index = int(state.get('step', 0) or 0)
        frame = {
            'screen_summary': data.get('screen_summary', ''),
            'target': data.get('target', ''),
            'strategy': data.get('strategy', ''),
            'risk': data.get('risk', 'low'),
            'notes': data.get('notes', ''),
            'step_index': step_index,
            'click_node_id': data.get('click_node_id', ''),
        }
        return {'action_frame': frame, 'framing_attempted_for_step': step_index}

NODE = FrameAction()