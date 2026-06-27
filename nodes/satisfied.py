"""Terminal rest node."""
patch = {"satisfied": not state.get("plan_failed", False), "last_error": ""}
signals = ["idle"]
