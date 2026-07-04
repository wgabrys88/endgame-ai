from __future__ import annotations
import hashlib
import pathlib
from typing import Any
import brain
import bus
import evolution
ROOT = pathlib.Path(__file__).parent.resolve()
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.vscode', '.idea', 'pids'}
BINARY_SUFFIXES = {'.pyc', '.pyd', '.dll', '.exe', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.webp'}
ORGAN_FILES = ['planner.py', 'scheduler.py', 'observe.py', 'execute.py', 'frame_action.py', 'verify.py', 'reflect.py', 'self_modify.py', 'satisfied.py', 'error.py']

def _git(args: list[str]) -> str:
    import subprocess
    cp = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(cp.stderr or cp.stdout or '').strip()}")
    return cp.stdout

def _zsplit(raw: str) -> set[str]:
    return {item for item in raw.split('\x00') if item}

def _status_map() -> dict[str, str]:
    status: dict[str, str] = {}
    for row in [line for line in _git(['status', '--porcelain']).splitlines() if line.strip()]:
        if len(row) >= 4:
            status[row[3:].replace('\\', '/')] = row[:2].strip() or 'modified'
    return status

def _capture_workspace_manifest(wiring: dict[str, Any]) -> dict[str, Any]:
    max_files = int(wiring.get('limits', {}).get('max_workspace_manifest_files', 40))
    tracked = _zsplit(_git(['ls-files', '-z']))
    untracked = _zsplit(_git(['ls-files', '--others', '--exclude-standard', '-z']))
    status = _status_map()
    files: list[dict[str, Any]] = []
    for rel in sorted(tracked | untracked):
        path = ROOT / rel
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in pathlib.PurePosixPath(rel.replace('\\', '/')).parts):
            continue
        files.append({'path': rel.replace('\\', '/'), 'size': path.stat().st_size, 'tracked': rel in tracked, 'status': status.get(rel, 'clean' if rel in tracked else 'untracked'), 'binary': path.suffix.lower() in BINARY_SUFFIXES})
    omitted = max(0, len(files) - max_files)
    if omitted:
        files = files[:max_files]
    return {'current_commit': evolution.git_head_sha(), 'branch': evolution.git_current_branch(), 'git_status': evolution.git_worktree_status(), 'files': files, 'omitted_files': omitted}

def _evidence_file(path: pathlib.Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    if not path.exists() or not path.is_file():
        return {'path': rel, 'exists': False}
    return {'path': rel, 'exists': True, 'size': path.stat().st_size}

def _runtime_evidence(wiring: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    raw_logs = sorted(ROOT.glob('*.txt'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    return {'state_path': _evidence_file(brain.root_path(wiring.get('paths', {}).get('state'), 'state.json')), 'runtime_log_path': _evidence_file(brain.root_path(wiring.get('paths', {}).get('runtime_log'), 'comms/runtime.ndjson')), 'raw_log_paths': [_evidence_file(p) for p in raw_logs], 'current_state_keys': sorted(state.keys()), 'has_fresh_observation': all(k in state for k in ('desktop_tree_text', 'focused_title', 'fresh_scan'))}

def _file_digest(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {'path': path.relative_to(ROOT).as_posix(), 'exists': False}
    content = path.read_text(encoding='utf-8', errors='replace')
    return {'path': path.relative_to(ROOT).as_posix(), 'exists': True, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(content.encode('utf-8', errors='replace')).hexdigest()}

def _immune_contract() -> dict[str, Any]:
    protected = ['brain.py', 'bus.py', 'desktop.py', 'registry.py', 'evolution.py', 'node.py', 'organism.py', 'stop_check.py', 'contract_check.py', *ORGAN_FILES]
    return {'principle': 'self_modify is surgery: preserve organ contracts before committing firmware changes', 'protected_sources': protected, 'required_validation': ['python -m compileall -q .', 'python -m json.tool wiring.json', 'python contract_check.py'], 'rules': ['Use unified_diffs for existing Python files; file_writes only for new files.', 'Every touched existing file must be listed in read_files.', 'contract_check.py must pass before commit.', 'Prefer one narrow repair over broad rewrites.']}

def _source_fingerprints() -> list[dict[str, Any]]:
    candidates = ['brain.py', 'bus.py', 'desktop.py', 'registry.py', 'evolution.py', 'organism.py', 'contract_check.py', 'wiring.json', 'execute.py', 'frame_action.py', 'reflect.py', 'self_modify.py', 'observe.py']
    return [_file_digest(ROOT / rel) for rel in candidates]

class SelfModify:
    name = 'self_modify'

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        state = ctx.get('state', {})
        wiring = ctx.get('wiring', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        git_context = evolution.prepare_self_evolution(wiring)
        payload = {'goal': goal, 'goal_narration': state.get('goal_narration', goal), 'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')}, 'failure': {'last_error': state.get('last_error', ''), 'last_reflection': state.get('last_reflection', {}), 'last_action': state.get('last_action', {}), 'last_result': state.get('last_result', ''), 'last_verification': state.get('last_verification', {})}, 'runtime': {'state_summary': {'current_node': ctx.get('node'), 'tick': state.get('tick'), 'last_error': state.get('last_error')}, 'evidence': _runtime_evidence(wiring, state)}, 'git_context': git_context, 'workspace_manifest': _capture_workspace_manifest(wiring), 'patch_contract': {'record_type': 'git_evolution_patch', 'data': {'summary': 'short human summary', 'rationale': 'runtime/code evidence', 'read_files': 'repo files that ground this patch', 'unified_diffs': 'preferred for existing Python', 'file_writes': 'new files only', 'file_deletes': 'non-protected paths only', 'wiring_patches': 'allowed prefixes only', 'commands': 'include python contract_check.py', 'expected_validation': 'what should pass'}, 'immune_contract': _immune_contract(), 'source_fingerprints': _source_fingerprints()}}
        record = brain.think(organ=self.name, system_prompt=wiring.get('prompts', {}).get('self_modify', ''), payload=payload, wiring=wiring, expected_record_type='git_evolution_patch', request_config={'web_search': wiring.get('self_modify', {}).get('web_search', {})})
        if record.get('record_type') != 'git_evolution_patch':
            raise RuntimeError(f"self_modify expected record_type=git_evolution_patch, got {record.get('record_type')!r}")
        data = record.get('data', {})
        obs = brain.last_fresh_observation()
        return bus.emit('modified', {'observed_at': obs.get('observed_at'), 'fresh_scan': obs.get('fresh_scan'), 'desktop_tree_text': obs.get('desktop_tree_text', ''), 'focused_title': obs.get('focused_title', ''), 'git_evolution_patch': {'summary': data.get('summary', ''), 'rationale': data.get('rationale', ''), 'read_files': data.get('read_files', []), 'wiring_patches': data.get('wiring_patches', []), 'file_writes': data.get('file_writes', []), 'unified_diffs': data.get('unified_diffs', data.get('file_diffs', [])), 'file_deletes': data.get('file_deletes', []), 'commands': data.get('commands', []), 'expected_validation': data.get('expected_validation', '')}, 'self_modify': {'status': 'proposed', 'git_context': git_context}}, record=record, evidence={'git_context': git_context, 'failure': payload.get('failure', {})})

NODE = SelfModify()