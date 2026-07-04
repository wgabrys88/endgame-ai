from __future__ import annotations
import importlib
import pathlib
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

_ORGAN_FILES = {'planner.py': 'planner', 'scheduler.py': 'scheduler', 'observe.py': 'observe', 'execute.py': 'execute', 'frame_action.py': 'frame_action', 'verify.py': 'verify', 'reflect.py': 'reflect', 'self_modify.py': 'self_modify', 'satisfied.py': 'satisfied', 'error.py': 'error'}
_DEPS_FILES = {'bus.py': 'bus', 'node.py': 'node', 'win32_api.py': 'win32_api', 'desktop.py': 'desktop', 'body_signals.py': 'body_signals', 'brain.py': 'brain'}
_RELOAD_ORDER = ('bus', 'node', 'win32_api', 'desktop', 'body_signals', 'brain', 'planner', 'scheduler', 'observe', 'execute', 'frame_action', 'verify', 'reflect', 'self_modify', 'satisfied', 'error', 'registry', 'evolution')

def _rebind_registry() -> None:
    import planner as _planner
    import scheduler as _scheduler
    import observe as _observe
    import execute as _execute
    import frame_action as _frame_action
    import verify as _verify
    import reflect as _reflect
    import self_modify as _self_modify
    import satisfied as _satisfied
    import error as _error
    NODE_REGISTRY.update({'planner': _planner.NODE, 'scheduler': _scheduler.NODE, 'observe': _observe.NODE, 'execute': _execute.NODE, 'frame_action': _frame_action.NODE, 'verify': _verify.NODE, 'reflect': _reflect.NODE, 'self_modify': _self_modify.NODE, 'satisfied': _satisfied.NODE, 'error': _error.NODE})

def reload_from_files(changed_files: list[str]) -> list[str]:
    names = {pathlib.Path(f).name for f in changed_files}
    targets = {_ORGAN_FILES[n] for n in names if n in _ORGAN_FILES}
    targets |= {_DEPS_FILES[n] for n in names if n in _DEPS_FILES}
    if 'registry.py' in names:
        targets.add('registry')
    if 'evolution.py' in names:
        targets.add('evolution')
    reloaded: list[str] = []
    for mod_name in _RELOAD_ORDER:
        if mod_name not in targets:
            continue
        mod = importlib.reload(importlib.import_module(mod_name))
        reloaded.append(mod_name)
    if targets & set(_ORGAN_FILES.values()):
        _rebind_registry()
    return reloaded

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