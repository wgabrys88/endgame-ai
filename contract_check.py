from __future__ import annotations
import ast
import json
import pathlib
import sys
from typing import Any
ROOT = pathlib.Path(__file__).parent.resolve()
REQUIRED_FILES = {'brain.py': 12000, 'bus.py': 2500, 'desktop.py': 5000, 'nodes.py': 12000, 'organism.py': 4500, 'stop_check.py': 1000, 'wiring.json': 4000}
REQUIRED_TOP_LEVEL_DEFS = {'brain.py': ['think', 'load_json', 'atomic_write_json', 'append_ndjson', 'root_path', 'last_fresh_observation'], 'bus.py': ['emit', 'coerce_node_output', 'validate_signal', 'datasheet', 'state_brief', 'observation_brief', 'update_failure_streak'], 'desktop.py': ['get_desktop', 'observe', 'observe_screen', 'last_desktop_tree', 'last_action_index', 'get_focused_title'], 'nodes.py': ['call_node', 'apply_evolution_patch', 'commit_self_evolution', 'prepare_self_evolution', 'build_capability_runtime', 'git_head_sha', 'git_worktree_status'], 'organism.py': ['run', 'main', 'next_node_for', 'write_state', 'runtime_event']}
REQUIRED_CLASSES = {'bus.py': {'NodeOutput': ['trace']}, 'desktop.py': {'Desktop': ['observe', 'observe_screen', 'last_desktop_tree', 'last_action_index', 'click', 'type_text', 'press_key', 'hotkey', 'scroll', 'focus_window', 'open_url', 'render_tree_text']}}
REQUIRED_NODE_FILES = ['planner', 'scheduler', 'observe', 'execute', 'frame_action', 'verify', 'reflect', 'self_modify', 'satisfied', 'error']

def _rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()

def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')

def _parse(rel: str, errors: list[str]) -> ast.Module | None:
    path = ROOT / rel
    if not path.exists():
        errors.append(f'missing required file: {rel}')
        return None
    try:
        return ast.parse(_read(path), filename=rel)
    except SyntaxError as exc:
        errors.append(f'syntax error in {rel}: {exc}')
        return None

def _top_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names

def _class_methods(tree: ast.Module, class_name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return set()

def _validate_files(errors: list[str]) -> None:
    for rel, min_bytes in REQUIRED_FILES.items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f'missing required file: {rel}')
            continue
        size = path.stat().st_size
        if size < min_bytes:
            errors.append(f'{rel} is too small for its contract: {size} bytes < {min_bytes}')

def _validate_python_surfaces(errors: list[str]) -> None:
    parsed: dict[str, ast.Module] = {}
    for rel in sorted(set(REQUIRED_TOP_LEVEL_DEFS) | set(REQUIRED_CLASSES)):
        tree = _parse(rel, errors)
        if tree is not None:
            parsed[rel] = tree
    for rel, required in REQUIRED_TOP_LEVEL_DEFS.items():
        tree = parsed.get(rel)
        if tree is None:
            continue
        names = _top_level_names(tree)
        for name in required:
            if name not in names:
                errors.append(f'{rel} missing top-level contract symbol: {name}')
    for rel, class_specs in REQUIRED_CLASSES.items():
        tree = parsed.get(rel)
        if tree is None:
            continue
        names = _top_level_names(tree)
        for class_name, methods in class_specs.items():
            if class_name not in names:
                errors.append(f'{rel} missing required class: {class_name}')
                continue
            actual = _class_methods(tree, class_name)
            for method in methods:
                if method not in actual:
                    errors.append(f'{rel}:{class_name} missing method: {method}')

def _validate_node_modules(wiring: dict[str, Any], errors: list[str]) -> None:
    topology = wiring.get('topology') or {}
    nodes = [str(item) for item in topology.get('nodes') or REQUIRED_NODE_FILES]
    edges = topology.get('edges') or {}
    known_targets = set(nodes) | {'halt'}
    for node_name in nodes:
        rel = f'organism_nodes/{node_name}.py'
        tree = _parse(rel, errors)
        if tree is None:
            continue
        names = _top_level_names(tree)
        if 'run' not in names:
            errors.append(f'{rel} missing node entrypoint run(ctx)')
        if 'DATASHEET' not in names:
            errors.append(f'{rel} missing node DATASHEET')
        node_edges = edges.get(node_name)
        if not isinstance(node_edges, dict):
            errors.append(f'wiring topology missing edges for node: {node_name}')
            continue
        for signal, target in node_edges.items():
            if not isinstance(signal, str) or not signal:
                errors.append(f'wiring topology has invalid signal for {node_name}: {signal!r}')
            if target not in known_targets:
                errors.append(f'wiring topology edge {node_name}.{signal} targets unknown node {target!r}')

def _validate_wiring(errors: list[str]) -> dict[str, Any]:
    path = ROOT / 'wiring.json'
    try:
        wiring = json.loads(_read(path))
    except Exception as exc:
        errors.append(f'wiring.json is not valid JSON: {exc}')
        return {}
    topology = wiring.get('topology')
    if not isinstance(topology, dict):
        errors.append('wiring.json missing topology object')
        return wiring
    if not isinstance(topology.get('nodes'), list) or not topology.get('nodes'):
        errors.append('wiring topology.nodes must be a non-empty list')
    if not isinstance(topology.get('edges'), dict) or not topology.get('edges'):
        errors.append('wiring topology.edges must be a non-empty object')
    cycle_start = topology.get('cycle_start')
    if cycle_start not in set(topology.get('nodes') or []):
        errors.append(f'wiring cycle_start is not a known node: {cycle_start!r}')
    return wiring

def _validate_model_tuning(wiring: dict[str, Any], errors: list[str]) -> None:
    model = wiring.get('model') or {}
    organs = model.get('organs') or {}
    required_organs = {'plan', 'action_frame', 'execution', 'verification', 'reflection', 'git_evolution_patch', 'satisfied'}
    if not isinstance(organs, dict):
        errors.append('model.organs must be an object')
        return
    for organ in sorted(required_organs):
        cfg = organs.get(organ)
        if not isinstance(cfg, dict):
            errors.append(f'model.organs.{organ} missing per-organ config')
            continue
        effort = cfg.get('reasoning_effort')
        if effort not in {'none', 'low', 'medium', 'high'}:
            errors.append(f'model.organs.{organ}.reasoning_effort invalid: {effort!r}')
        if cfg.get('max_output_tokens') is not None and int(cfg['max_output_tokens']) < 200:
            errors.append(f'model.organs.{organ}.max_output_tokens is too low')
        if cfg.get('temperature') is not None:
            temp = float(cfg['temperature'])
            if temp < 0 or temp > 2:
                errors.append(f'model.organs.{organ}.temperature outside supported range: {temp}')

def _validate_source_access(wiring: dict[str, Any], errors: list[str]) -> None:
    self_modify = wiring.get('self_modify') or {}
    web_search = self_modify.get('web_search') or {}
    if not isinstance(web_search, dict) or not web_search.get('enabled'):
        errors.append('self_modify.web_search.enabled must be true for source-grounded firmware repair')
        return
    if web_search.get('allowed_domains') and web_search.get('excluded_domains'):
        errors.append('self_modify.web_search cannot set both allowed_domains and excluded_domains')
    allowed = [str(item) for item in web_search.get('allowed_domains') or []]
    if len(allowed) > 5:
        errors.append('self_modify.web_search.allowed_domains exceeds xAI max of 5')
    for domain in ('github.com', 'raw.githubusercontent.com'):
        if domain not in allowed:
            errors.append(f'self_modify.web_search.allowed_domains missing {domain}')

def validate_static_contract(root: pathlib.Path | str | None=None) -> list[str]:
    global ROOT
    old_root = ROOT
    if root is not None:
        ROOT = pathlib.Path(root).resolve()
    try:
        errors: list[str] = []
        _validate_files(errors)
        _validate_python_surfaces(errors)
        wiring = _validate_wiring(errors)
        _validate_node_modules(wiring, errors)
        _validate_model_tuning(wiring, errors)
        _validate_source_access(wiring, errors)
        return errors
    finally:
        ROOT = old_root

def raise_on_contract_failure(root: pathlib.Path | str | None=None) -> None:
    errors = validate_static_contract(root)
    if errors:
        joined = '\n'.join((f'- {error}' for error in errors))
        raise RuntimeError(f'organism contract validation failed:\n{joined}')

def main(argv: list[str] | None=None) -> int:
    errors = validate_static_contract(pathlib.Path(argv[0]).resolve() if argv else ROOT)
    result = {'ok': not errors, 'error_count': len(errors), 'errors': errors}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if errors else 0
if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))