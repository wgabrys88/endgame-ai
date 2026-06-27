"""Post state telemetry to bus."""
item = {"type": "telemetry", "slot": wiring.get("instance", {}).get("slot", 1), "goal": state.get("goal"), "step": state.get("step"), "satisfied": state.get("satisfied", False), "last_error": state.get("last_error", "")}
bus_write(item, wiring)
patch = {"bus_posted": item}
signals = ["posted"]
