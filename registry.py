from __future__ import annotations
from typing import Any
import bus
import planner
import scheduler
import observe
import execute
import frame_action
import verify
import reflect
import self_modify
import satisfied
import error

NODE_REGISTRY: dict[str, Any] = {
    'planner': planner.NODE,
    'scheduler': scheduler.NODE,
    'observe': observe.NODE,
    'execute': execute.NODE,
    'frame_action': frame_action.NODE,
    'verify': verify.NODE,
    'reflect': reflect.NODE,
    'self_modify': self_modify.NODE,
    'satisfied': satisfied.NODE,
    'error': error.NODE,
}

def call_node(node_name: str, ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    node = NODE_REGISTRY[node_name]
    result = node.run(ctx)
    if not isinstance(result, bus.NodeOutput):
        raise RuntimeError(f"node '{node_name}' must return NodeOutput")
    wiring = ctx['wiring']
    bus.validate_signal(wiring, node_name, result.signal)
    patch = dict(result.patch)
    patch.setdefault('_last_bus_frame', result.trace(node=node_name))
    return (result.signal, patch)