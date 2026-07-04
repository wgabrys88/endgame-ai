from __future__ import annotations
import pathlib
from typing import Any
import brain
import bus
import evolution
ROOT = pathlib.Path(__file__).parent.resolve()
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.vscode', '.idea', 'pids'}
BINARY_SUFFIXES = {'.pyc', '.pyd', '.dll', '.exe', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.webp'}

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
    return {'state_path': _evidence_file(brain.root_path(wiring.get('paths', {}).get('state'), 'state.json')), 'runtime_log_path': _evidence_file(brain.root_path(wiring.get('paths', {}).get('runtime_log'), 'comms/runtime.ndjson')), 'current_state_keys': sorted(state.keys()), 'has_fresh_observation': all(k in state for k in ('desktop_tree_text', 'focused_title', 'fresh_scan'))}

class SelfModify:
    name = 'self_modify'

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        state = ctx.get('state', {})
        wiring = ctx.get('wiring', {})
        goal = ctx.get('goal', '')
        step = state.get('current_step') or {}
        git_context = evolution.prepare_self_evolution(wiring)
        payload = {
            'goal': goal,
            'goal_narration': state.get('goal_narration', goal),
            'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')},
            'failure': {'last_error': state.get('last_error', ''), 'last_reflection': state.get('last_reflection', {}), 'last_action': state.get('last_action', {}), 'last_result': state.get('last_result', ''), 'last_verification': state.get('last_verification', {})},
            'runtime': {'state_summary': {'current_node': ctx.get('node'), 'tick': state.get('tick'), 'last_error': state.get('last_error')}, 'evidence': _runtime_evidence(wiring, state)},
            'git_context': git_context,
            'workspace_manifest': _capture_workspace_manifest(wiring),
            'full_file_access': {'mode': git_context.get('context_mode'), 'github_branch_url': git_context.get('branch_url', ''), 'local_repo_root': str(ROOT), 'rule': 'Ground patches in stable prefix firmware + branch URL. Return git_evolution_patch only.'},
            'patch_contract': {'record_type': 'git_evolution_patch', 'data': {'summary': 'str', 'rationale': 'str', 'read_files': 'paths read from stable prefix', 'file_writes': 'new files', 'unified_diffs': 'narrow edits to existing py/json', 'commands': ['python contract_check.py'], 'expected_validation': 'contract_check passes'}},
        }
        record = brain.think(organ=self.name, system_prompt=wiring.get('prompts', {}).get('self_modify', ''), payload=payload, wiring=wiring, expected_record_type='git_evolution_patch', request_config={'web_search': wiring.get('self_modify', {}).get('web_search', {})})
        if record.get('record_type') != 'git_evolution_patch':
            raise RuntimeError(f"self_modify expected record_type=git_evolution_patch, got {record.get('record_type')!r}")
        data = record.get('data', {})
        obs = brain.last_fresh_observation()
        return bus.emit('modified', {'observed_at': obs.get('observed_at'), 'fresh_scan': obs.get('fresh_scan'), 'desktop_tree_text': obs.get('desktop_tree_text', ''), 'focused_title': obs.get('focused_title', ''), 'git_evolution_patch': {'summary': data.get('summary', ''), 'rationale': data.get('rationale', ''), 'read_files': data.get('read_files', []), 'wiring_patches': data.get('wiring_patches', []), 'file_writes': data.get('file_writes', []), 'unified_diffs': data.get('unified_diffs', data.get('file_diffs', [])), 'file_deletes': data.get('file_deletes', []), 'commands': data.get('commands', []), 'expected_validation': data.get('expected_validation', '')}, 'self_modify': {'status': 'proposed', 'git_context': git_context}}, record=record, evidence={'git_context': git_context, 'failure': payload.get('failure', {})})

NODE = SelfModify()