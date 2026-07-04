from __future__ import annotations
from typing import Any
import bus
from node import MechanicalNode

class Satisfied(MechanicalNode):
    name = 'satisfied'

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        state = ctx.get('state', {})
        return bus.emit('halt', {'satisfied': not bool(state.get('plan_failed')) and not bool(state.get('last_error')), 'last_error': state.get('last_error')})

NODE = Satisfied()