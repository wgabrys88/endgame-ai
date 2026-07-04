from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any
JsonDict = dict[str, Any]

@dataclass(frozen=True)
class NodeOutput:
    signal: str
    patch: JsonDict = field(default_factory=dict)
    record: JsonDict | None = None
    evidence: JsonDict = field(default_factory=dict)

    def trace(self, *, node: str) -> JsonDict:
        record_type = None
        if isinstance(self.record, dict):
            record_type = self.record.get('record_type')
        return {'kind': 'endgame.node_output.v1', 'node': node, 'signal': self.signal, 'record_type': record_type, 'patch_keys': sorted(self.patch.keys()), 'evidence_keys': sorted(self.evidence.keys()), 'emitted_at': time.time()}

def emit(signal: str, patch: JsonDict | None=None, *, record: JsonDict | None=None, evidence: JsonDict | None=None) -> NodeOutput:
    if not isinstance(signal, str) or not signal.strip():
        raise ValueError('bus signal must be a non-empty string')
    if patch is not None and (not isinstance(patch, dict)):
        raise TypeError('bus patch must be a dict')
    if record is not None and (not isinstance(record, dict)):
        raise TypeError('bus record must be a dict when provided')
    if evidence is not None and (not isinstance(evidence, dict)):
        raise TypeError('bus evidence must be a dict when provided')
    return NodeOutput(signal=signal.strip(), patch=dict(patch or {}), record=record, evidence=dict(evidence or {}))

def coerce_node_output(node: str, result: Any) -> NodeOutput:
    if isinstance(result, NodeOutput):
        return result
    raise RuntimeError(f"node '{node}' contract violation: expected NodeOutput")

def allowed_signals(wiring: JsonDict, node: str) -> set[str]:
    edges = wiring.get('topology', {}).get('edges', {})
    node_edges = edges.get(node, {})
    if not isinstance(node_edges, dict):
        return set()
    return {str(signal) for signal in node_edges.keys()}

def validate_signal(wiring: JsonDict, node: str, signal: str) -> None:
    signals = allowed_signals(wiring, node)
    if signals and signal not in signals:
        allowed = ', '.join(sorted(signals))
        raise RuntimeError(f"node '{node}' emitted signal '{signal}' outside topology contract; allowed: {allowed}")

def datasheet(node: str, *, kind: str, inputs: list[str], signals: list[str], writes: list[str], record_type: str | None=None) -> JsonDict:
    return {'node': node, 'kind': kind, 'inputs': list(inputs), 'signals': list(signals), 'writes': list(writes), 'record_type': record_type}

def state_brief(state: JsonDict) -> JsonDict:
    current_step = state.get('current_step') or {}
    return {'tick': state.get('tick'), 'current_node': state.get('current_node'), 'step_index': state.get('step', 0), 'goal_narration': state.get('goal_narration', ''), 'goal_signals': state.get('goal_signals', {}), 'current_step': {'description': current_step.get('description', ''), 'done_when': current_step.get('done_when', '')}, 'last_signal': state.get('last_signal'), 'last_error': state.get('last_error'), 'last_verification': state.get('last_verification', {}), 'last_reflection': state.get('last_reflection', {}), 'failure_streak': state.get('failure_streak', {}), 'has_action_frame': bool(state.get('action_frame'))}

def observation_brief(state: JsonDict) -> JsonDict:
    return {'focused_title': state.get('focused_title', ''), 'desktop_tree_text': state.get('desktop_tree_text', ''), 'observed_at': state.get('observed_at'), 'fresh_scan': state.get('fresh_scan', False)}

def action_index_brief(state: JsonDict, *, limit: int = 24) -> list[JsonDict]:
    index = state.get('action_index') if isinstance(state.get('action_index'), dict) else {}
    rows: list[JsonDict] = []
    for node_id in sorted(index.keys(), key=lambda k: (str(index[k].get('zone', '')), str(index[k].get('role', '')), k)):
        node = index[node_id]
        if not isinstance(node, dict):
            continue
        rows.append({'id': node_id, 'role': node.get('role', ''), 'zone': node.get('zone', ''), 'x': node.get('x'), 'y': node.get('y'), 'hwnd': node.get('hwnd'), 'window_title': node.get('window_title', ''), 'hint': node.get('hint', '')})
        if len(rows) >= limit:
            break
    omitted = max(0, len(index) - len(rows))
    if omitted:
        rows.append({'omitted': omitted})
    return rows

def failure_signature(state: JsonDict) -> str:
    step = state.get('current_step') or {}
    parts = {'step': step.get('description', ''), 'done_when': step.get('done_when', ''), 'error': state.get('last_error') or '', 'verification': state.get('last_verification') or {}, 'action_conclusion': (state.get('last_action') or {}).get('conclusion', '')}
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

def update_failure_streak(state: JsonDict) -> JsonDict:
    signature = failure_signature(state)
    previous = state.get('failure_streak') or {}
    count = int(previous.get('count', 0) or 0) + 1 if previous.get('signature') == signature else 1
    return {'failure_streak': {'signature': signature, 'count': count, 'updated_at': time.time()}}

SEMANTIC_ROLES = ('text_input', 'text_area', 'button', 'link', 'clickable')

def roles_required_by_done_when(done_when: str) -> set[str]:
    text = (done_when or '').lower()
    return {role for role in SEMANTIC_ROLES if role in text}

def roles_present_in_semantic_ui(tree: str) -> set[str]:
    present: set[str] = set()
    for line in (tree or '').splitlines():
        stripped = line.strip()
        if not stripped.startswith('- '):
            continue
        for role in SEMANTIC_ROLES:
            if stripped.startswith(f'- {role} '):
                present.add(role)
                break
    return present

def observation_contract_failure(state: JsonDict) -> tuple[bool, str]:
    step = state.get('current_step') or {}
    done_when = str(step.get('done_when') or '')
    required = roles_required_by_done_when(done_when)
    if not required:
        return False, ''
    tree = str(state.get('desktop_tree_text') or '')
    if not tree.strip():
        return True, f'done_when expects {sorted(required)} but SEMANTIC_UI tree is empty'
    present = roles_present_in_semantic_ui(tree)
    missing = sorted(required - present)
    if not missing:
        return False, ''
    return True, f'done_when expects {sorted(required)} but SEMANTIC_UI lacks {missing}'

def should_force_observation_escalate(state: JsonDict, wiring: JsonDict | None=None) -> tuple[bool, str]:
    cfg = (wiring or {}).get('reflect_escalation', {})
    min_streak = int(cfg.get('observation_missing_min_streak', 3) or 3)
    streak = state.get('failure_streak') or {}
    count = int(streak.get('count', 0) or 0)
    if count < min_streak:
        return False, ''
    failed, reason = observation_contract_failure(state)
    if not failed:
        return False, ''
    return True, f'failure_streak={count} with observation contract gap: {reason}'

def mermaid_state_diagram(wiring: JsonDict, datasheets: dict[str, JsonDict] | None=None) -> str:
    topo = wiring.get('topology', {})
    edges = topo.get('edges', {})
    lines = ['stateDiagram-v2', f"    [*] --> {topo.get('cycle_start', 'planner')} : cycle_start"]
    for src, mapping in edges.items():
        if not isinstance(mapping, dict):
            continue
        for signal, dst in mapping.items():
            if dst == 'halt':
                lines.append(f'    {src} --> [*] : {signal}')
            else:
                lines.append(f'    {src} --> {dst} : {signal}')
    for node, sheet in sorted((datasheets or {}).items()):
        signals = ', '.join(sheet.get('signals') or [])
        record_type = sheet.get('record_type') or 'mechanical'
        lines.append(f'    note right of {node}')
        lines.append(f"        {sheet.get('kind', 'node')} | record={record_type}")
        if signals:
            lines.append(f'        signals: {signals}')
        lines.append('    end note')
    return '\n'.join(lines) + '\n'