from __future__ import annotations
import argparse
import pathlib
import time
from typing import Any
import body_signals
import brain
import evolution
import registry
import stop_check
ROOT = pathlib.Path(__file__).parent.resolve()

def load_wiring() -> dict[str, Any]:
    return brain.load_json(ROOT / 'wiring.json')

def state_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get('paths', {}).get('state'), 'state.json')

def control_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get('paths', {}).get('control'), 'comms/control.json')

def runtime_log_path(wiring: dict[str, Any]) -> pathlib.Path:
    return brain.root_path(wiring.get('paths', {}).get('runtime_log'), 'comms/runtime.ndjson')

def write_state(wiring: dict[str, Any], state: dict[str, Any]) -> None:
    brain.atomic_write_json(state_path(wiring), state)

def runtime_event(wiring: dict[str, Any], event: str, **payload: Any) -> None:
    brain.append_ndjson(runtime_log_path(wiring), {'ts': time.time(), 'event': event, **payload})

def default_control(wiring: dict[str, Any]) -> dict[str, Any]:
    ctrl = dict(wiring.get('control_default') or {})
    required = ('mode', 'step_token', 'updated_at')
    missing = [k for k in required if k not in ctrl]
    if missing:
        raise RuntimeError(f'control_default missing keys: {missing}')
    if ctrl['mode'] not in {'run', 'pause', 'step'}:
        raise RuntimeError(f"invalid control_default.mode: {ctrl['mode']!r}")
    return dict(ctrl)

def read_control(wiring: dict[str, Any]) -> dict[str, Any]:
    path = control_path(wiring)
    if not path.exists():
        ctrl = default_control(wiring)
        ctrl['updated_at'] = time.time()
        brain.atomic_write_json(path, ctrl)
        return ctrl
    ctrl = brain.load_json(path)
    mode = ctrl.get('mode')
    if mode not in {'run', 'pause', 'step'}:
        raise RuntimeError(f'invalid control mode in {path}: {mode!r}')
    ctrl['step_token'] = int(ctrl.get('step_token', 0))
    return ctrl

def reset_runtime(wiring: dict[str, Any]) -> None:
    for key, default in [('state', 'state.json'), ('runtime_log', 'comms/runtime.ndjson')]:
        p = brain.root_path(wiring.get('paths', {}).get(key), default)
        if p.exists():
            p.unlink()
    (ROOT / 'comms').mkdir(exist_ok=True)

def wait_before_node(wiring: dict[str, Any], state: dict[str, Any], node_name: str) -> None:
    entered_pause = False
    while True:
        stop_check.check_stop(f'organism wait_before_node:{node_name}')
        ctrl = read_control(wiring)
        mode = ctrl['mode']
        token = int(ctrl.get('step_token', 0))
        if mode == 'run':
            return
        consumed = int(state.get('_last_step_token_consumed', -1))
        if mode == 'step' and token > consumed:
            state['_last_step_token_consumed'] = token
            state['_phase'] = 'stepping_node'
            state['current_node'] = node_name
            write_state(wiring, state)
            runtime_event(wiring, 'step_consumed', node=node_name, step_token=token)
            return
        if not entered_pause:
            state['_phase'] = 'paused_before_node'
            state['current_node'] = node_name
            state['control_mode'] = mode
            write_state(wiring, state)
            runtime_event(wiring, 'paused_before_node', node=node_name, mode=mode, step_token=token)
            entered_pause = True
        time.sleep(0.1)

def next_node_for(wiring: dict[str, Any], current: str, signal_name: str) -> str:
    edges = wiring.get('topology', {}).get('edges', {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise RuntimeError(f"topology has no edges for node '{current}'")
    nxt = node_edges.get(signal_name)
    if not isinstance(nxt, str) or not nxt:
        raise RuntimeError(f"node '{current}' emitted signal '{signal_name}' with no topology edge")
    return nxt

def _apply_self_modify(wiring: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    evolution_patch = patch.get('git_evolution_patch')
    if not evolution_patch:
        return patch
    _, applied = evolution.apply_evolution_patch(wiring, {'data': evolution_patch})
    patch.setdefault('self_modify', {})['applied'] = applied
    patch['self_modify']['commit'] = evolution.commit_self_evolution(wiring, applied, evolution_patch)
    return patch

def _tick(wiring: dict[str, Any], state: dict[str, Any], goal: str, current: str) -> tuple[dict[str, Any], str, str]:
    wait_before_node(wiring, state, current)
    state['_phase'] = 'executing_node'
    state['current_node'] = current
    write_state(wiring, state)
    runtime_event(wiring, 'node_start', node=current, tick=state['tick'])
    print(f'[organism] tick={state["tick"]} node={current}', flush=True)
    ctx = {'wiring': wiring, 'state': dict(state), 'goal': goal, 'node': current}
    signal_name, patch = registry.call_node(current, ctx)
    if current == 'self_modify':
        patch = _apply_self_modify(wiring, patch)
    state.update(patch)
    if signal_name == 'halt':
        state['_phase'] = 'halted'
        write_state(wiring, state)
        runtime_event(wiring, 'halted', node=current, reason=state.get('error_handled', {}))
        return state, signal_name, 'halt'
    nxt = next_node_for(wiring, current, signal_name)
    state['last_signal'] = signal_name
    state['last_node'] = current
    state['next_node'] = nxt
    state['tick'] += 1
    state['_phase'] = 'node_complete'
    write_state(wiring, state)
    runtime_event(wiring, 'node_complete', node=current, signal=signal_name, next_node=nxt, tick=state['tick'])
    if current == 'execute':
        delay_ms = int(wiring.get('timing', {}).get('post_execute_delay_ms', 0))
        if delay_ms > 0:
            print(f'[organism] post_execute_delay {delay_ms}ms', flush=True)
            time.sleep(delay_ms / 1000.0)
    return state, signal_name, nxt

def run(goal: str | None, *, reset: bool=False, max_ticks: int | None=None, max_brain_calls: int | None=None, start_node: str | None=None) -> dict[str, Any]:
    stop_check.register_pid('organism')
    wiring = load_wiring()
    if max_brain_calls is not None:
        wiring.setdefault('model', {})['max_brain_calls'] = max_brain_calls
    if reset:
        reset_runtime(wiring)
    brain.reset_call_budget()
    topo = wiring.get('topology', {})
    current = str(start_node or topo.get('cycle_start') or 'planner')
    if current not in set(topo.get('nodes', [])):
        raise RuntimeError(f"start node '{current}' is not in topology.nodes")
    seed = goal or ''
    state: dict[str, Any] = {'_phase': 'starting', 'goal': seed, 'goal_seed': seed, 'goal_narration': seed, 'goal_signals': body_signals.collect({}), 'tick': 0, 'current_node': current, 'last_error': None, 'last_action': None, 'wiring_transport': wiring.get('model', {}).get('transport'), 'start_node': current}
    write_state(wiring, state)
    runtime_event(wiring, 'organism_start', goal=goal or '', transport=state['wiring_transport'])
    print(f'[organism] start goal={goal or "(empty)"} node={current} transport={state["wiring_transport"]}', flush=True)
    try:
        while True:
            stop_check.check_stop('organism main loop')
            if max_ticks is not None and state['tick'] >= max_ticks:
                state['_phase'] = 'max_ticks'
                write_state(wiring, state)
                return state
            state, signal, nxt = _tick(wiring, state, goal or '', current)
            if signal == 'halt':
                return state
            current = nxt
    except KeyboardInterrupt:
        state['_phase'] = 'interrupted'
        write_state(wiring, state)
        return state
    except Exception as exc:
        state['_phase'] = 'error'
        state['last_error'] = f'{type(exc).__name__}: {exc}'
        write_state(wiring, state)
        runtime_event(wiring, 'error', node=current, error=state['last_error'])
        nxt = next_node_for(wiring, current, 'error')
        state['last_signal'] = 'error'
        state['last_node'] = current
        state['next_node'] = nxt
        state['tick'] += 1
        current = nxt
        while True:
            stop_check.check_stop('organism error recovery')
            if max_ticks is not None and state['tick'] >= max_ticks:
                return state
            state, signal, nxt = _tick(wiring, state, goal or '', current)
            if signal == 'halt':
                return state
            current = nxt

def run_single_node(node_name: str, goal: str, *, reset: bool=False, max_brain_calls: int | None=None) -> dict[str, Any]:
    stop_check.register_pid('organism')
    wiring = load_wiring()
    if max_brain_calls is not None:
        wiring.setdefault('model', {})['max_brain_calls'] = max_brain_calls
    if reset:
        reset_runtime(wiring)
    brain.reset_call_budget()
    if node_name not in set(wiring.get('topology', {}).get('nodes', [])):
        raise RuntimeError(f"node '{node_name}' not in topology.nodes")
    seed = goal or ''
    state: dict[str, Any] = {'_phase': 'starting', 'goal': seed, 'goal_seed': seed, 'goal_narration': seed, 'goal_signals': body_signals.collect({}), 'tick': 0, 'current_node': node_name, 'last_error': None, 'last_action': None, 'wiring_transport': wiring.get('model', {}).get('transport'), 'start_node': node_name}
    write_state(wiring, state)
    runtime_event(wiring, 'organism_start', goal=goal or '', transport=state['wiring_transport'], single_node=node_name)
    state, signal_name, _ = _tick(wiring, state, goal or '', node_name)
    print(f'Node: {node_name}')
    print(f'Signal: {signal_name}')
    if state.get('desktop_tree_text'):
        print(f'Observation chars: {len(state["desktop_tree_text"])}')
        print('--- desktop_tree_text ---')
        print(state['desktop_tree_text'][:2000])
    return state

def main(argv: list[str] | None=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('goal', nargs='?', default='')
    ap.add_argument('--reset', action='store_true')
    ap.add_argument('--max-ticks', type=int, default=None)
    ap.add_argument('--max-brain-calls', type=int, default=None)
    ap.add_argument('--start-node', default=None)
    ap.add_argument('--execute-node', default=None)
    args = ap.parse_args(argv)
    if args.execute_node:
        run_single_node(args.execute_node, args.goal, reset=args.reset, max_brain_calls=args.max_brain_calls)
    else:
        run(args.goal, reset=args.reset, max_ticks=args.max_ticks, max_brain_calls=args.max_brain_calls, start_node=args.start_node)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())