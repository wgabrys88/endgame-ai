from __future__ import annotations

import actions


def run(ctx):
    state = ctx.get("state", {})
    action = state.get("pending_action") or {"verb": "noop"}
    result = actions.perform(action)
    return "verify", {"last_action": result}
