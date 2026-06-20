"""Example hot-loaded node handler.
Drop any .py with a handler(state, config) function in nodes/ — auto-registered.
"""

def handler(state, config):
    """Pass-through gate: emits 'pass' signal unconditionally."""
    return {"signals": ["pass"], "patch": {}}
