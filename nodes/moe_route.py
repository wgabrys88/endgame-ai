"""Route goal to this slot or delegate through bus."""
moe = wiring.get("moe", {}) or {}
required = moe.get("required_permission", "desktop_exec")
perms = wiring.get("instance", {}).get("permissions", []) or []
goal = (state.get("goal") or "").lower()
delegate_keywords = [str(x).lower() for x in moe.get("delegate_keywords", [])]
if required and required not in perms:
    bus_write({"type": "delegated_goal", "goal": state.get("goal"), "from_slot": wiring.get("instance", {}).get("slot"), "reason": "missing_permission"}, wiring)
    patch = {"delegated": True}
    signals = ["delegated"]
elif delegate_keywords and any(k in goal for k in delegate_keywords) and wiring.get("instance", {}).get("slot", 1) != moe.get("default_exec_slot", 1):
    bus_write({"type": "delegated_goal", "goal": state.get("goal"), "from_slot": wiring.get("instance", {}).get("slot"), "reason": "keyword"}, wiring)
    patch = {"delegated": True}
    signals = ["delegated"]
else:
    patch = {"delegated": False}
    signals = ["self"]
