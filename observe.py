from __future__ import annotations
from typing import Any
import bus
import desktop
from node import MechanicalNode

class Observe(MechanicalNode):
    name = 'observe'

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        config = ctx.get('wiring', {}).get('observe_config', {})
        obs = desktop.observe(config)
        if not obs.get('desktop_tree_text'):
            raise RuntimeError('observe missing desktop_tree_text')
        return bus.emit('screen_ready', {'observed_at': obs['observed_at'], 'desktop_tree_text': obs['desktop_tree_text'], 'focused_title': obs.get('focused_title', ''), 'fresh_scan': obs.get('fresh_scan', True), 'action_index': obs.get('action_index', {}), 'observation_artifact': obs.get('observation_artifact', {})}, evidence={'focused_title': obs.get('focused_title'), 'fresh_scan': obs.get('fresh_scan', True), 'action_index_count': len(obs.get('action_index') or {})})

NODE = Observe()