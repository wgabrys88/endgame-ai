# Deterministic Analysis Toolchain

Endgame-ai includes a **deterministic analysis bridge** (`ps_bridge.py` at repo root) that wraps all static analysis tools behind structured JSON. No shell syntax issues (`&&`, `||`, `|`) — pure `subprocess.run`.

## Available Commands

```bash
python ps_bridge.py run "powershell command"      # Raw PowerShell
python ps_bridge.py git_status                    # git status --porcelain
python ps_bridge.py git_diff [files...]           # git diff
python ps_bridge.py git_add [files...]            # git add
python ps_bridge.py git_commit "message"          # git commit -m
python ps_bridge.py git_log [n]                   # git log --oneline -n
python ps_bridge.py pyright [target]              # python -m pyright --outputjson
python ps_bridge.py vulture [target] [min_conf]   # python -m vulture --min-confidence
python ps_bridge.py pyan3 [target]                # pyan3 --uses --format dot
python ps_bridge.py pydeps [target]               # pydeps --noshow
python ps_bridge.py code2flow [target]            # code2flow --format dot
python ps_bridge.py pycallgraph [target]          # python -m pycallgraph
```

Each returns:
```json
{"exit_code": 0, "stdout": "...", "stderr": "...", "success": true}
```

## Call Graph Analysis

```bash
# pyan3 (works via direct executable)
python ps_bridge.py pyan3 . > deps.dot

# pydeps (needs Graphviz dot)
python ps_bridge.py pydeps .

# code2flow (needs Graphviz dot)
python ps_bridge.py code2flow .

# pycallgraph
python ps_bridge.py pycallgraph .
```

## Finding Bloat

```bash
# Dead code (vulture)
python ps_bridge.py vulture . 90

# Type errors (pyright)
python ps_bridge.py pyright .

# Call graph → find unreachable nodes
python ps_bridge.py pyan3 . --uses --no-defines --colored --grouped --annotated --dot --file deps.dot
```

## Integration with Self-Modify

`node_self_modify` can emit `commands` in its patch:
```json
{
  "commands": [
    {"command": "python ps_bridge.py pyright .", "shell": false},
    {"command": "python ps_bridge.py vulture . 80", "shell": false}
  ]
}
```

The organism runs them, validates (Python compile + JSON parse), commits on success, hot-swaps to known-good on failure.