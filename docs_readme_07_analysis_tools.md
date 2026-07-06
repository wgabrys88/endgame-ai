# 7. Deterministic Analysis Tools: Finding Bloat

The repository includes a deterministic PowerShell bridge (`ps_bridge.py` at repo root) that wraps all analysis tools with structured JSON output. No shell syntax issues (`&&`, `||`, `|`).

## ps_bridge.py Commands

```bash
# Move to repo root (already there)
python ps_bridge.py run "command"
python ps_bridge.py git_status
python ps_bridge.py git_diff
python ps_bridge.py git_add "file.py"
python ps_bridge.py git_commit "message"
python ps_bridge.py git_log 20
python ps_bridge.py pyright .
python ps_bridge.py vulture . 80
python ps_bridge.py pyan3 . --uses --no-defines --colored --grouped --annotated --dot --file deps.dot
python ps_bridge.py pydeps . --noshow
python ps_bridge.py code2flow . --format dot
python ps_bridge.py pycallgraph .
```

Each returns:
```json
{"exit_code": 0, "stdout": "...", "stderr": "...", "success": true}
```

## Vulture: Dead Code Detection

```bash
python ps_bridge.py vulture . 80
```

Finds unused imports, methods, attributes, classes. Run after every self-modify to catch regressions.

## Pyright: Static Type Checking

```bash
python ps_bridge.py pyright .
```

Catches type errors the brain might introduce. The organism runs this as a validation command in self-modify patches.

## Call Graph Analysis

```bash
# pyan3 (module import graph)
python ps_bridge.py pyan3 .

# pydeps (dependency graph, needs Graphviz dot)
python ps_bridge.py pydeps .

# code2flow (function call graph)
python ps_bridge.py code2flow .

# python-call-graph
python ps_bridge.py pycallgraph .
```

Generate `.dot` files for Graphviz visualization. `deps.dot` (152KB) already exists from pyan3.

## Finding Bloat: The Workflow

1. `python ps_bridge.py vulture . 80` → dead code
2. `python ps_bridge.py pyright .` → type errors, unused imports
3. `python ps_bridge.py pyan3 . --uses --no-defines --dot --file deps.dot` → import cycles, unused modules
4. `python ps_bridge.py pydeps . --noshow` → dependency clusters
5. Delete. Simplify. Commit.

The organism can run this workflow on itself via `node_self_modify`.