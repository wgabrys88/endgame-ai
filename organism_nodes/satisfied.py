from __future__ import annotations
import bus
DATASHEET = bus.datasheet('satisfied', kind='halt_gate', inputs=['plan_complete', 'last_reflection', 'last_error'], signals=['halt'], writes=['satisfied', 'last_error'], record_type=None)

def run(ctx):
    state = ctx.get('state', {})
    return bus.emit('halt', {'satisfied': not bool(state.get('plan_failed')) and (not bool(state.get('last_error'))), 'last_error': state.get('last_error')})