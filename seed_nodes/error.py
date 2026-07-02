"""error: mechanical error recovery node.

This node runs when any node in the topology emits an 'error' signal.
It receives error context from state and decides recovery action:
- 'planner': retry from planner (default)
- 'reflect': go to reflection for lesson extraction
- 'halt': clean exit (no zombie processes)
"""
from __future__ import annotations


def run(ctx):
    state = ctx.get("state", {})
    error_info = {
        "failed_node": state.get("last_node"),
        "error": state.get("last_error"),
        "tick": state.get("tick"),
        "signal": state.get("last_signal"),
    }
    
    # Log the error for debugging
    print(f"[ERROR NODE] Failed node: {error_info['failed_node']}, Error: {error_info['error']}")
    
    recovery = "reflect" if state.get("current_step") else "planner"
    return recovery, {"error_handled": error_info, "recovery": recovery}
