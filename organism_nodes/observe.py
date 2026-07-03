from __future__ import annotations
import bus
import desktop
DATASHEET = bus.datasheet('observe', kind='desktop_sensor', inputs=['wiring.observe_config'], signals=['screen_ready', 'error'], writes=['observed_at', 'desktop_tree_text', 'focused_title', 'fresh_scan', 'observation_artifact'], record_type=None)

def run(ctx):
    config = ctx.get('wiring', {}).get('observe_config', {})
    obs = desktop.observe(config)
    return bus.emit('screen_ready', {'observed_at': obs.get('observed_at'), 'desktop_tree_text': obs.get('desktop_tree_text', ''), 'focused_title': obs.get('focused_title'), 'fresh_scan': obs.get('fresh_scan'), 'observation_artifact': obs.get('observation_artifact', {})}, evidence={'focused_title': obs.get('focused_title'), 'fresh_scan': obs.get('fresh_scan')})