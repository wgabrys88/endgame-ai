"""Poll bus for fresh interrupts."""
items = bus_read()
slot = wiring.get("instance", {}).get("slot", 1)
interrupt = None
for item in reversed(items):
    if item.get("type") == "interrupt" and item.get("slot", slot) == slot and not item.get("consumed"):
        interrupt = item
        break
if interrupt:
    patch = {"goal": interrupt.get("goal", state.get("goal", "")), "bus_interrupt": interrupt, "last_error": "interrupt"}
    signals = ["interrupt"]
else:
    patch = {}
    signals = ["no_interrupt"]
