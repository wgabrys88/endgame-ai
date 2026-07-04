from __future__ import annotations
import ast
import json
import pathlib
import sys
from typing import Any
import registry
ROOT = pathlib.Path(__file__).parent.resolve()
REQUIRED_FILES = ['brain.py', 'bus.py', 'desktop.py', 'registry.py', 'evolution.py', 'node.py', 'organism.py', 'stop_check.py', 'wiring.json']
ORGAN_FILES = ['planner.py', 'scheduler.py', 'observe.py', 'execute.py', 'frame_action.py', 'verify.py', 'reflect.py', 'self_modify.py', 'satisfied.py', 'error.py']

def _parse(rel: str, errors: list[str]) -> ast.Module | None:
    path = ROOT / rel
    if not path.exists():
        errors.append(f'missing required file: {rel}')
        return None
    try:
        return ast.parse(path.read_text(encoding='utf-8', errors='replace'), filename=rel)
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
    return names

def _validate_registry(errors: list[str], wiring: dict[str, Any]) -> None:
    topo_nodes = set(str(n) for n in wiring.get('topology', {}).get('nodes', []))
    reg_nodes = set(registry.NODE_REGISTRY.keys())
    if topo_nodes != reg_nodes:
        errors.append(f'NODE_REGISTRY keys {sorted(reg_nodes)} != topology.nodes {sorted(topo_nodes)}')
    for name, node in registry.NODE_REGISTRY.items():
        if getattr(node, 'name', None) != name:
            errors.append(f'registry node {name!r} has mismatched name attribute {getattr(node, "name", None)!r}')
        if not hasattr(node, 'run'):
            errors.append(f'registry node {name!r} missing run()')
    if not hasattr(registry, 'reload_from_files'):
        errors.append('registry.reload_from_files missing')

def _validate_wiring(errors: list[str]) -> dict[str, Any]:
    path = ROOT / 'wiring.json'
    try:
        wiring = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'wiring.json invalid: {exc}')
        return {}
    topo = wiring.get('topology', {})
    if not isinstance(topo.get('nodes'), list) or not topo.get('nodes'):
        errors.append('topology.nodes missing')
    if not isinstance(topo.get('edges'), dict) or not topo.get('edges'):
        errors.append('topology.edges missing')
    if topo.get('cycle_start') not in set(topo.get('nodes') or []):
        errors.append('cycle_start not in topology.nodes')
    if not isinstance(wiring.get('limits'), dict):
        errors.append('limits block missing')
    return wiring

def validate_static_contract(root: pathlib.Path | str | None=None) -> list[str]:
    global ROOT
    old = ROOT
    if root is not None:
        ROOT = pathlib.Path(root).resolve()
    try:
        errors: list[str] = []
        for rel in REQUIRED_FILES + ORGAN_FILES:
            _parse(rel, errors)
        wiring = _validate_wiring(errors)
        if wiring:
            _validate_registry(errors, wiring)
        return errors
    finally:
        ROOT = old

def main(argv: list[str] | None=None) -> int:
    errors = validate_static_contract()
    print(json.dumps({'ok': not errors, 'error_count': len(errors), 'errors': errors}, indent=2, ensure_ascii=False))
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))