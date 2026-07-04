from __future__ import annotations
import json
import pathlib
import sys
import time
ROOT = pathlib.Path(__file__).parent.resolve()

def _tail_jsonl(path: pathlib.Path, n: int=5) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

def snapshot() -> str:
    state_path = ROOT / 'state.json'
    runtime_path = ROOT / 'comms' / 'runtime.ndjson'
    brain_path = ROOT / 'comms' / 'brain_raw.jsonl'
    parts = [f'=== {time.strftime("%H:%M:%S")} ===']
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        parts.append(f"phase={state.get('_phase')} tick={state.get('tick')} node={state.get('current_node')} next={state.get('next_node')} signal={state.get('last_signal')}")
        narr = str(state.get('goal_narration', ''))[:120]
        if narr:
            parts.append(f'narration: {narration_preview(narr)}')
        if state.get('last_error'):
            parts.append(f"error: {state['last_error'][:160]}")
        obs = state.get('desktop_tree_text')
        if obs:
            parts.append(f'observation: {len(obs)} chars focus={state.get("focused_title", "")[:60]}')
    else:
        parts.append('state.json: not yet')
    for row in _tail_jsonl(runtime_path, 3):
        parts.append(f"runtime: {row.get('event')} node={row.get('node')} signal={row.get('signal')}")
    for row in _tail_jsonl(brain_path, 2):
        phase = row.get('phase')
        if phase == 'think':
            parts.append(f"brain: think organ={row.get('organ')} payload_len={row.get('user_text_len')}")
        elif phase == 'api_request':
            parts.append('brain: api_request sent')
        elif phase == 'api_response_body':
            parts.append(f"brain: api_response {len(str(row.get('body', '')))} bytes")
        elif phase == 'response':
            parts.append(f"brain: record parsed elapsed={row.get('elapsed_s')}s")
        elif phase == 'error' or phase == 'api_error':
            parts.append(f"brain: ERROR {row.get('error') or row.get('status')}")
    return '\n'.join(parts)

def narration_preview(text: str) -> str:
    return text.replace('\n', ' ')[:120]

def main() -> int:
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    for i in range(rounds):
        print(snapshot(), flush=True)
        if i + 1 < rounds:
            time.sleep(interval)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())