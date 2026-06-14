"""Secondary telemetry beacon - plugin-local state only."""
import time
from comms import agent_id, post_telemetry

_INTERVAL = 45.0


def run(board):
    state = board.get("_plugin_telemetry", {})
    now = time.time()
    if now - float(state.get("last", 0)) < _INTERVAL:
        return None
    post_telemetry(
        agent_id(),
        stagnation=float(board.get("stagnation", 0)),
        power=float(board.get("power", 0)),
        velocity=float(board.get("velocity", 0)),
        fissions=int(board.get("fissions", 0)),
        phase=str(board.get("_last_phase", "idle"))[:32],
        cycles=int(board.get("_pressure", {}).get("cycles", 0)),
    )
    return {"writes": {"_plugin_telemetry": {"last": now}}}
