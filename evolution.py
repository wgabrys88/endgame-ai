from __future__ import annotations
import copy
import json
import os
import pathlib
import subprocess
import threading
from typing import Any
import brain
ROOT = pathlib.Path(__file__).parent.resolve()

EVOLVABLE_SUFFIXES = {'.py', '.json', '.md'}
EVOLVABLE_NAMES = {'.gitattributes', '.gitignore', 'LICENSE'}
BLOCKED_EVOLVE_PARTS = {'.git', '__pycache__', 'comms', 'pids'}
BLOCKED_EVOLVE_NAMES = {'state.json', 'stop.txt'}
CORE_FILES = frozenset({'brain.py', 'desktop.py', 'registry.py', 'evolution.py', 'node.py', 'organism.py', 'stop_check.py', 'bus.py', 'contract_check.py'})
ORGAN_FILES = frozenset({'planner.py','scheduler.py','observe.py','execute.py','frame_action.py','verify.py','reflect.py','self_modify.py','satisfied.py','error.py'})
PROTECTED_FULL_WRITE_SUFFIXES = ('.py',)
DEFAULT_WIRING_NEW_PATH_PREFIXES = ('self_modify.', 'model.stable_prefix.', 'model.organs.', 'limits.', 'prompts.')

def _patch_data(parsed: dict[str, Any]) -> dict[str, Any]:
    data = (parsed or {}).get('data', parsed or {})
    if not isinstance(data, dict):
        raise ValueError('self_modify patch data must be an object')
    return data

def _evolution_target(raw_path: str, *, deleting: bool=False) -> tuple[pathlib.Path, str]:
    rel = str(raw_path).replace('\\', '/').strip().lstrip('/')
    if not rel:
        raise ValueError('self_modify path is empty')
    requested = pathlib.Path(rel)
    path = (ROOT / requested).resolve() if not requested.is_absolute() else requested.resolve()
    try:
        repo_rel = path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f'self_modify path must stay under repository root: {raw_path}') from exc
    parts = {part.lower() for part in repo_rel.parts}
    if parts & BLOCKED_EVOLVE_PARTS:
        raise ValueError(f'self_modify path targets runtime/private area: {repo_rel.as_posix()}')
    if path.name in BLOCKED_EVOLVE_NAMES:
        raise ValueError(f'self_modify path targets runtime state: {repo_rel.as_posix()}')
    if path.name not in EVOLVABLE_NAMES and path.suffix not in EVOLVABLE_SUFFIXES:
        raise ValueError(f'self_modify path has unsupported file type: {repo_rel.as_posix()}')
    if deleting and repo_rel.as_posix() in CORE_FILES | {'wiring.json'}:
        raise ValueError(f'self_modify may rewrite but not delete core file: {repo_rel.as_posix()}')
    return (path, repo_rel.as_posix())

def _path_exists_in_mapping(mapping: dict[str, Any], dotted: str) -> bool:
    cur: Any = mapping
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True

def _wiring_new_path_allowed(wiring: dict[str, Any], dotted: str) -> bool:
    allowed = list(DEFAULT_WIRING_NEW_PATH_PREFIXES)
    allowed.extend((str(item) for item in wiring.get('self_modify', {}).get('wiring_allowed_new_prefixes', []) or []))
    return any((dotted == prefix.rstrip('.') or dotted.startswith(prefix) for prefix in allowed))

def _requires_diff_for_full_write(rel: str, path: pathlib.Path) -> bool:
    if not path.exists() or path.suffix not in PROTECTED_FULL_WRITE_SUFFIXES:
        return False
    if rel in CORE_FILES:
        return True
    return rel in ORGAN_FILES

def _collect_unified_diffs(data: dict[str, Any]) -> list[str]:
    raw_items = data.get('unified_diffs')
    if raw_items is None:
        raw_items = data.get('file_diffs')
    if raw_items is None:
        raw_items = []
    if isinstance(raw_items, str):
        raw_items = [raw_items]
    diffs: list[str] = []
    for item in list(raw_items or []):
        if isinstance(item, str):
            diff = item
        elif isinstance(item, dict):
            diff = str(item.get('diff') or item.get('patch') or '')
        else:
            raise ValueError(f'unified_diffs entry must be string or object: {item!r}')
        if diff.strip():
            diffs.append(diff if diff.endswith('\n') else diff + '\n')
    return diffs

def _paths_from_unified_diff(diff_text: str) -> set[str]:
    paths: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith('diff --git '):
            parts = line.split()
            if len(parts) >= 4:
                for raw in parts[2:4]:
                    if raw.startswith('a/') or raw.startswith('b/'):
                        rel = raw[2:]
                        if rel != '/dev/null':
                            paths.add(rel)
        elif line.startswith('--- ') or line.startswith('+++ '):
            raw = line[4:].split('\t', 1)[0].strip()
            if raw in {'/dev/null', 'dev/null'}:
                continue
            if raw.startswith('a/') or raw.startswith('b/'):
                paths.add(raw[2:])
    return {path.replace('\\', '/').strip().lstrip('/') for path in paths if path.strip()}

def _validate_unified_diff_targets(diff_text: str, read_files: set[str]) -> list[str]:
    touched: list[str] = []
    paths = _paths_from_unified_diff(diff_text)
    if not paths:
        raise ValueError('unified diff does not name any repository files')
    for rel in sorted(paths):
        path, safe_rel = _evolution_target(rel)
        touched.append(safe_rel)
        if path.exists() and safe_rel not in read_files:
            raise ValueError(f'unified diff touches existing file without declaring read_files: {safe_rel}')
    return touched

def _apply_unified_diff(diff_text: str) -> None:
    for args in (['apply', '--check', '--whitespace=nowarn', '-'], ['apply', '--whitespace=nowarn', '-']):
        cp = subprocess.run(['git', *args], cwd=ROOT, input=diff_text, capture_output=True, text=True)
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or '').strip()
            raise RuntimeError(f"git {' '.join(args)} failed for self_modify unified diff: {detail}")

def _run_static_contract_check() -> dict[str, Any]:
    import contract_check
    errors = contract_check.validate_static_contract(ROOT)
    if errors:
        raise RuntimeError('organism contract validation failed after self_modify: ' + '; '.join(errors))
    return {'ok': True, 'checker': 'contract_check.validate_static_contract', 'errors': []}

def _validate_content(path: pathlib.Path, rel: str, content: Any) -> str:
    if not isinstance(content, str):
        raise ValueError(f'self_modify content for {rel} must be a string')
    if path.suffix == '.py':
        compile(content, rel, 'exec')
    elif path.suffix == '.json':
        json.loads(content)
    return content

def _atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp.{os.getpid()}.{threading_id()}')
    tmp.write_text(content, encoding='utf-8', newline='\n')
    os.replace(tmp, path)

def threading_id() -> int:
    try:
        import threading
        return threading.get_ident()
    except Exception:
        return 0

def _apply_wiring_ops(wiring: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(wiring)
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError(f'wiring_patch must be object: {patch!r}')
        op = patch.get('op', 'set')
        dotted = str(patch.get('path') or '')
        if not dotted:
            raise ValueError('wiring_patch missing path')
        existed = _path_exists_in_mapping(patched, dotted)
        if not existed and (not _wiring_new_path_allowed(wiring, dotted)):
            raise ValueError(f'self_modify wiring_patch creates undeclared path {dotted!r}; add an allowed prefix deliberately before using it')
        parts = dotted.split('.')
        cur = patched
        for part in parts[:-1]:
            if not isinstance(cur.get(part), dict):
                if not _wiring_new_path_allowed(wiring, dotted):
                    raise ValueError(f'self_modify may not create intermediate wiring path for {dotted!r}')
                cur[part] = {}
            cur = cur[part]
        if op == 'set':
            cur[parts[-1]] = patch.get('value')
        elif op == 'delete':
            if not existed:
                raise ValueError(f'self_modify wiring delete targets missing path: {dotted!r}')
            cur.pop(parts[-1], None)
        else:
            raise ValueError(f'unknown wiring_patch op: {op}')
    json.dumps(patched, ensure_ascii=False, default=str)
    return patched

def _collect_file_writes(data: dict[str, Any]) -> list[dict[str, str]]:
    return list(data.get('file_writes') or [])

def _collect_file_deletes(data: dict[str, Any]) -> list[str]:
    return [str(path) for path in list(data.get('file_deletes') or [])]

def _declared_read_files(data: dict[str, Any]) -> set[str]:
    return {str(path).replace('\\', '/').strip().lstrip('/') for path in list(data.get('read_files') or []) if str(path).strip()}

def _activation_bucket(rel: str) -> str:
    if rel == 'wiring.json' or rel in ORGAN_FILES:
        return 'immediate'
    if rel in CORE_FILES:
        return 'next_run'
    return 'supporting'

def _git(args: list[str], *, check: bool=True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    if check and cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or '').strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return cp

def git_head_sha() -> str:
    return _git(['rev-parse', 'HEAD']).stdout.strip()

def git_current_branch() -> str:
    return _git(['branch', '--show-current']).stdout.strip()

def git_worktree_status() -> list[str]:
    return [line for line in _git(['status', '--porcelain']).stdout.splitlines() if line.strip()]

def _remote_url(remote: str) -> str:
    cp = _git(['remote', 'get-url', remote], check=False)
    return cp.stdout.strip() if cp.returncode == 0 else ''

def _github_branch_url(remote_url: str, branch: str) -> str:
    url = remote_url.strip()
    if not url:
        return ''
    if url.startswith('git@github.com:'):
        url = 'https://github.com/' + url.removeprefix('git@github.com:')
    if url.endswith('.git'):
        url = url[:-4]
    return f'{url}/tree/{branch}' if url.startswith('https://github.com/') else ''

def prepare_self_evolution(wiring: dict[str, Any]) -> dict[str, Any]:
    cfg = wiring.get('self_modify', {}).get('git', {})
    remote = str(cfg.get('remote') or 'origin')
    branch = git_current_branch()
    remote_url = _remote_url(remote)
    return {'context_mode': wiring.get('self_modify', {}).get('context_mode', 'checked_out_branch'), 'branch': branch, 'current_commit': git_head_sha(), 'worktree_status': git_worktree_status(), 'remote': remote, 'remote_url': remote_url, 'branch_url': _github_branch_url(remote_url, branch), 'commit_target': 'checked_out_branch', 'push_after_commit': bool(cfg.get('push_after_commit', True))}

def _run_evolution_commands(commands: list[Any], wiring: dict[str, Any]) -> list[dict[str, Any]]:
    if not commands:
        return []
    cfg = wiring.get('self_modify', {}).get('execution', {})
    default_timeout = cfg.get('timeout_s')
    results: list[dict[str, Any]] = []
    for item in commands:
        if isinstance(item, dict):
            command = item.get('command')
            shell = bool(item.get('shell', isinstance(command, str)))
            timeout_s = item.get('timeout_s', default_timeout)
        else:
            command = item
            shell = isinstance(command, str)
            timeout_s = default_timeout
        if not isinstance(command, (str, list)) or not command:
            raise ValueError(f'invalid self_modify command: {item!r}')
        cp = subprocess.run(command, cwd=ROOT, shell=shell, capture_output=True, text=True, timeout=float(timeout_s) if timeout_s is not None else None)
        result = {'command': command, 'shell': shell, 'returncode': cp.returncode, 'stdout': cp.stdout, 'stderr': cp.stderr}
        results.append(result)
        if cp.returncode != 0:
            raise RuntimeError(f'self_modify command failed: {result}')
    return results

def _snapshot_paths(paths: list[pathlib.Path]) -> dict[pathlib.Path, bytes | None]:
    snapshots: dict[pathlib.Path, bytes | None] = {}
    for path in paths:
        if path not in snapshots:
            snapshots[path] = path.read_bytes() if path.exists() else None
    return snapshots

def _restore_snapshots(snapshots: dict[pathlib.Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f'{path.name}.rollback.{os.getpid()}.{threading_id()}')
            tmp.write_bytes(content)
            os.replace(tmp, path)

def apply_evolution_patch(wiring: dict[str, Any], parsed: dict[str, Any]) -> tuple[str, Any]:
    data = _patch_data(parsed)
    read_files = _declared_read_files(data)
    wiring_patches = list(data.get('wiring_patches') or [])
    unified_diffs = _collect_unified_diffs(data)
    patched_wiring = _apply_wiring_ops(wiring, wiring_patches)
    diff_touched: list[str] = []
    for diff_text in unified_diffs:
        diff_touched.extend(_validate_unified_diff_targets(diff_text, read_files))
    writes: list[tuple[pathlib.Path, str, str]] = []
    for item in _collect_file_writes(data):
        if not isinstance(item, dict):
            raise ValueError(f'file_writes entry must be object: {item!r}')
        path, rel = _evolution_target(str(item.get('path') or ''))
        if _requires_diff_for_full_write(rel, path):
            raise ValueError(f'self_modify may not full-rewrite protected existing Python file {rel}; use unified_diffs with narrow context instead')
        content = _validate_content(path, rel, item.get('content'))
        writes.append((path, rel, content))
    deletes: list[tuple[pathlib.Path, str]] = []
    for raw_path in _collect_file_deletes(data):
        path, rel = _evolution_target(raw_path, deleting=True)
        if path.exists() and (rel in CORE_FILES or rel in ORGAN_FILES):
            raise ValueError(f'self_modify may not delete protected organism source file: {rel}')
        deletes.append((path, rel))
    missing_reads = []
    for path, rel, _ in writes:
        if path.exists() and rel not in read_files:
            missing_reads.append(rel)
    for path, rel in deletes:
        if path.exists() and rel not in read_files:
            missing_reads.append(rel)
    if wiring_patches and 'wiring.json' not in read_files:
        missing_reads.append('wiring.json')
    if missing_reads:
        raise ValueError(f'self_modify patch must declare read_files for touched existing files: {sorted(set(missing_reads))}')
    touched_paths = [path for path, _, _ in writes] + [path for path, _ in deletes]
    for rel in diff_touched:
        path = (ROOT / rel).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError:
            continue
        touched_paths.append(path)
    if wiring_patches:
        touched_paths.append(ROOT / 'wiring.json')
    snapshots = _snapshot_paths(touched_paths)
    rollback_on_failure = bool(wiring.get('self_modify', {}).get('execution', {}).get('rollback_on_failure', True))
    try:
        for diff_text in unified_diffs:
            _apply_unified_diff(diff_text)
        for path, _, content in writes:
            _atomic_write_text(path, content)
        for path, _ in deletes:
            path.unlink(missing_ok=True)
        if wiring_patches:
            wiring.clear()
            wiring.update(patched_wiring)
            save_wiring(wiring)
        for path, rel, _ in writes:
            if path.suffix == '.py':
                compile(path.read_text(encoding='utf-8'), rel, 'exec')
            elif path.suffix == '.json':
                json.loads(path.read_text(encoding='utf-8'))
        contract_result = _run_static_contract_check()
        command_results = _run_evolution_commands(list(data.get('commands') or []), wiring)
        post_command_contract_result = _run_static_contract_check()
    except Exception:
        if rollback_on_failure:
            _restore_snapshots(snapshots)
            if wiring_patches:
                wiring.clear()
                wiring.update(brain.load_json(ROOT / 'wiring.json'))
        raise
    changed = [rel for _, rel, _ in writes] + [rel for _, rel in deletes] + sorted(set(diff_touched))
    activation = {'immediate': [], 'next_run': [], 'supporting': []}
    for rel in changed + (['wiring.json'] if wiring_patches else []):
        activation[_activation_bucket(rel)].append(rel)
    return ('set', {'wiring_patches': len(wiring_patches), 'file_writes': len(writes), 'unified_diffs': len(unified_diffs), 'file_deletes': len(deletes), 'commands': command_results, 'contract_check': contract_result, 'post_command_contract_check': post_command_contract_result, 'rollback_on_failure': rollback_on_failure, 'changed_files': sorted(set(changed)), 'activation': activation})

def commit_self_evolution(wiring: dict[str, Any], applied: dict[str, Any], patch_data: dict[str, Any]) -> dict[str, Any]:
    changed_files = list(applied.get('changed_files') or [])
    if applied.get('wiring_patches'):
        changed_files.append('wiring.json')
    changed_files = sorted({str(path).replace('\\', '/') for path in changed_files if str(path).strip()})
    if not changed_files:
        return {'committed': False, 'reason': 'no_changed_files', 'branch': git_current_branch(), 'commit': git_head_sha()}
    _git(['add', '-A', '--', *changed_files])
    status = git_worktree_status()
    if not status:
        return {'committed': False, 'reason': 'no_git_changes', 'branch': git_current_branch(), 'commit': git_head_sha(), 'changed_files': changed_files}
    summary = str(patch_data.get('summary') or 'validated self evolution').strip()
    title = 'Self-modify: ' + summary.replace('\n', ' ')[:60]
    rationale = str(patch_data.get('rationale') or '').strip()
    expected = patch_data.get('expected_validation')
    body = json.dumps({'branch': git_current_branch(), 'changed_files': changed_files, 'read_files': list(patch_data.get('read_files') or []), 'rationale': rationale, 'expected_validation': expected}, ensure_ascii=False, indent=2, default=str)
    _git(['commit', '-m', title, '-m', body])
    branch = git_current_branch()
    pushed = False
    git_cfg = wiring.get('self_modify', {}).get('git', {})
    if bool(git_cfg.get('push_after_commit', False)):
        _git(['push', str(git_cfg.get('remote') or 'origin'), branch])
        pushed = True
    return {'committed': True, 'branch': branch, 'commit': git_head_sha(), 'changed_files': changed_files, 'pushed': pushed, 'status': git_worktree_status()}

def save_wiring(wiring: dict[str, Any]) -> None:
    brain.atomic_write_json(ROOT / 'wiring.json', wiring)

def wiring_limit(name: str, default: int, wiring: dict[str, Any]) -> int:
    return wiring.get('limits', {}).get(name, default)

