import os, json, time

def run(board):
    log = {"ts": time.time(), "power": board.get("power", 0), "stagnation": board.get("stagnation", 0)}
    os.makedirs("runtime/comms", exist_ok=True)
    with open("runtime/comms/telemetry.jsonl", "a") as f:
        json.dump(log, f)
        f.write("\n")
    return {"phase": "plugin.telemetry", "data": log}
