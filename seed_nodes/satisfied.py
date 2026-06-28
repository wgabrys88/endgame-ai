"""satisfied: terminal rest node."""
patch = {"satisfied": not state.get("plan_failed", False), "last_error": state.get("last_error", "")}
signals = ["idle"]
