"""Fission memory - plugin-local state only."""


def run(board):
    fissions = int(board.get("fissions", 0) or 0)
    state = board.get("_plugin_fission_log", {})
    previous = int(state.get("last_fissions", -1) or -1)
    if fissions <= previous:
        return None
    power = float(board.get("power", 0) or 0)
    stagnation = float(board.get("stagnation", 0) or 0)
    return {
        "writes": {
            "_plugin_fission_log": {
                "last_fissions": fissions,
                "power": power,
                "stagnation": stagnation,
            }
        },
        "phase": "plugin.fission_log",
        "data": {
            "fissions": fissions,
            "power": round(power, 4),
            "stagnation": round(stagnation, 4),
        },
    }