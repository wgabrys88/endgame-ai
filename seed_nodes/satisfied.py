from __future__ import annotations


def run(ctx):
    state = ctx.get("state", {})
    return "halt", {
        "satisfied": not bool(state.get("plan_failed")),
        "last_error": state.get("last_error"),
    }
