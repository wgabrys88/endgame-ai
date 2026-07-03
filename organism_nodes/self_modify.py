from __future__ import annotations
import hashlib
import pathlib
import subprocess
from typing import Any
import brain
import bus
import nodes
ROOT = pathlib.Path(__file__).parent.parent.resolve()
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.vscode', '.idea', 'pids'}
BINARY_SUFFIXES = {'.pyc', '.pyd', '.dll', '.exe', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.webp'}
DATASHEET = bus.datasheet('self_modify', kind='llm_git_firmware_update', inputs=['goal', 'failure', 'runtime_evidence', 'git_context', 'workspace_manifest'], signals=['modified', 'modify_failed', 'error'], writes=['git_evolution_patch', 'self_modify', 'desktop_tree_text', 'focused_title'], record_type='git_evolution_patch')

def _git(args: list[str]) -> str:
    cp = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or '').strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return cp.stdout

def _zsplit(raw: str) -> set[str]:
    return {item for item in raw.split('\x00') if item}

def _status_map() -> dict[str, str]:
    rows = [line for line in _git(['status', '--porcelain']).splitlines() if line.strip()]
    status: dict[str, str] = {}
    for row in rows:
        if len(row) >= 4:
            status[row[3:].replace('\\', '/')] = row[:2].strip() or 'modified'
    return status

def _capture_workspace_manifest() -> dict[str, Any]:
    tracked = _zsplit(_git(['ls-files', '-z']))
    untracked = _zsplit(_git(['ls-files', '--others', '--exclude-standard', '-z']))
    status = _status_map()
    files: list[dict[str, Any]] = []
    for rel in sorted(tracked | untracked):
        path = ROOT / rel
        if not path.is_file():
            continue
        parts = pathlib.PurePosixPath(rel.replace('\\', '/')).parts
        if any((part in SKIP_DIRS for part in parts)):
            continue
        files.append({'path': rel.replace('\\', '/'), 'size': path.stat().st_size, 'tracked': rel in tracked, 'status': status.get(rel, 'clean' if rel in tracked else 'untracked'), 'binary': path.suffix.lower() in BINARY_SUFFIXES})
    return {'current_commit': nodes.git_head_sha(), 'branch': nodes.git_current_branch(), 'git_status': nodes.git_worktree_status(), 'files': files}

def _evidence_file(path: pathlib.Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    if not path.exists() or not path.is_file():
        return {'path': rel, 'exists': False}
    return {'path': rel, 'exists': True, 'size': path.stat().st_size}

def _runtime_evidence(wiring: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    raw_logs = sorted(ROOT.glob('*.txt'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    return {'state_path': _evidence_file(brain.root_path(wiring.get('paths', {}).get('state'), 'state.json')), 'runtime_log_path': _evidence_file(brain.root_path(wiring.get('paths', {}).get('runtime_log'), 'comms/runtime.ndjson')), 'raw_log_paths': [_evidence_file(path) for path in raw_logs], 'current_state_keys': sorted(state.keys()), 'has_fresh_observation': all((key in state for key in ('desktop_tree_text', 'focused_title', 'fresh_scan')))}

def _file_digest(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {'path': path.relative_to(ROOT).as_posix(), 'exists': False}
    content = path.read_text(encoding='utf-8', errors='replace')
    return {'path': path.relative_to(ROOT).as_posix(), 'exists': True, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(content.encode('utf-8', errors='replace')).hexdigest()}

def _immune_contract() -> dict[str, Any]:
    protected = ['brain.py', 'bus.py', 'desktop.py', 'nodes.py', 'organism.py', 'stop_check.py', 'contract_check.py', 'organism_nodes/*.py', 'brain_transports/*.py']
    validation = ['python -m compileall -q .', 'python -m json.tool wiring.json', 'python contract_check.py']
    return {'principle': 'self_modify is surgery: preserve organ contracts before committing firmware changes', 'protected_sources': protected, 'required_validation': validation, 'rules': ['Use unified_diffs for existing Python files; full file_writes are for new files or non-protected supporting files.', 'Every touched existing file must be listed in read_files.', 'Do not create new wiring paths unless they are under an explicitly allowed prefix.', 'Do not replace a body organ with a stub that only compiles; contract_check.py must pass.', 'Prefer one narrow repair grounded in the current source over broad rewrites or placebo config keys.']}

def _source_fingerprints() -> list[dict[str, Any]]:
    candidates = ['brain.py', 'bus.py', 'desktop.py', 'nodes.py', 'organism.py', 'contract_check.py', 'wiring.json', 'organism_nodes/execute.py', 'organism_nodes/frame_action.py', 'organism_nodes/reflect.py', 'organism_nodes/self_modify.py', 'organism_nodes/observe.py', 'brain_transports/xai.py']
    return [_file_digest(ROOT / rel) for rel in candidates]

def run(ctx):
    state = ctx.get('state', {})
    wiring = ctx.get('wiring', {})
    goal = ctx.get('goal', '')
    step = state.get('current_step') or {}
    git_context = nodes.prepare_self_evolution(wiring)
    fresh_obs = state.get('fresh_observation', {})
    payload = {'goal': goal, 'observation': bus.observation_brief(state), 'step': {'description': step.get('description', goal), 'done_when': step.get('done_when', '')}, 'failure': {'last_error': state.get('last_error', ''), 'last_reflection': state.get('last_reflection', {}), 'last_action': state.get('last_action', {}), 'last_result': state.get('last_result', ''), 'last_verification': state.get('last_verification', {})}, 'runtime': {'state_summary': {'current_node': ctx.get('node'), 'tick': state.get('tick'), 'last_error': state.get('last_error')}, 'evidence': _runtime_evidence(wiring, state)}, 'git_context': git_context, 'workspace_manifest': _capture_workspace_manifest(), 'full_file_access': {'mode': git_context['context_mode'], 'github_branch_url': git_context.get('branch_url', ''), 'local_repo_root': str(ROOT), 'rule': 'Use the checked-out repository, workspace manifest, fresh observation, and runtime evidence. The local organism applies, commits, and pushes on the current branch.'}, 'patch_contract': {'record_type': 'git_evolution_patch', 'data': {'summary': 'short human summary', 'rationale': 'runtime/code evidence for the change', 'read_files': 'repo files from the stable prefix that ground this patch', 'unified_diffs': 'preferred list of unified git diffs for existing Python source files', 'file_writes': "list of {path:'repo relative path', content:'complete file text'} for new files or non-protected supporting files only", 'file_deletes': 'list of repo relative paths; protected organism source cannot be deleted', 'wiring_patches': "list of {op:'set'|'delete', path:'dotted.path', value:any}; new paths must use allowed prefixes", 'commands': 'validation commands from repo root; include python contract_check.py', 'expected_validation': 'what should pass after the patch'}, 'immune_contract': _immune_contract(), 'source_fingerprints': _source_fingerprints(), 'notes': ['Target organism_nodes/ for node behavior changes and brain_transports/ for transport changes.', 'Existing Python source must be changed through unified_diffs, not full-file replacement.', 'Python, JSON, topology, node entrypoints, and core body symbols are validated before commit/push.', 'The local organism applies, validates, commits, and pushes only after contract_check.py passes.']}}
    if fresh_obs:
        payload['fresh_observation'] = fresh_obs
    record = brain.think(system_prompt=wiring.get('prompts', {}).get('self_modify', ''), payload=payload, wiring=wiring, expected_record_type='git_evolution_patch', request_config={'web_search': wiring.get('self_modify', {}).get('web_search', {})})
    if record.get('record_type') != 'git_evolution_patch':
        raise RuntimeError(f"self_modify expected record_type=git_evolution_patch, got {record.get('record_type')}")
    data = record.get('data', {})
    obs = brain.last_fresh_observation()
    return bus.emit('modified', {'observed_at': obs.get('observed_at'), 'fresh_scan': obs.get('fresh_scan'), 'desktop_tree_text': obs.get('desktop_tree_text', ''), 'focused_title': obs.get('focused_title', ''), 'git_evolution_patch': {'summary': data.get('summary', ''), 'rationale': data.get('rationale', ''), 'read_files': data.get('read_files', []), 'wiring_patches': data.get('wiring_patches', []), 'file_writes': data.get('file_writes', []), 'unified_diffs': data.get('unified_diffs', data.get('file_diffs', [])), 'file_deletes': data.get('file_deletes', []), 'commands': data.get('commands', []), 'expected_validation': data.get('expected_validation', '')}, 'self_modify': {'status': 'proposed', 'git_context': git_context, 'patches': len(data.get('wiring_patches', []) or []), 'writes': len(data.get('file_writes', []) or []), 'diffs': len(data.get('unified_diffs', data.get('file_diffs', [])) or []), 'deletes': len(data.get('file_deletes', []) or []), 'commands': len(data.get('commands', []) or [])}}, record=record, evidence={'git_context': git_context, 'failure': payload.get('failure', {})})