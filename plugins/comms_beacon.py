import time
from comms import agent_id, post

BEACON_INTERVAL = 30.0


def run(board):
    state = board.get("_plugin_beacon", {})
    now = time.time()
    if now - float(state.get("last", 0)) < BEACON_INTERVAL:
        return None
    post(
        agent_id(),
        "colony",
        f"beacon stag={float(board.get('stagnation', 0)):.2f} power={float(board.get('power', 0)):.3f}",
        kind="beacon",
    )
    return {"writes": {"_plugin_beacon": {"last": now}}}