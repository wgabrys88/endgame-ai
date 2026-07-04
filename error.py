from __future__ import annotations
from typing import Any
import bus
from node import MechanicalNode

class Error(MechanicalNode):
    name = 'error'

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        state = ctx.get('state', {})
        error_info = {'failed_node': state.get('last_node'), 'error': state.get('last_error'), 'tick': state.get('tick'), 'signal': state.get('last_signal')}
        recovery = 'reflect' if state.get('current_step') else 'planner'
        return bus.emit(recovery, {'error_handled': error_info, 'recovery': recovery})

NODE = Error()