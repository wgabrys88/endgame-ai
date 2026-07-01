from __future__ import annotations

import brain
import json
import pathlib


ROOT = pathlib.Path(__file__).parent.parent.resolve()


def _read_file_safe(path: pathlib.Path, max_chars: int = 5000) -> str:
    """Read file with size limit."""
    try:
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
            return content[:max_chars]
    except Exception:
        pass
    return ""


def _capture_codebase() -> dict[str, str]:
    """Capture essential endgame-ai files for self-modification context."""
    files = {}
    
    # Core files
    core_files = [
        "brain.py", "nodes.py", "organism.py", "desktop.py", "wiring.json",
        "stop_check.py", "workbench.py",
    ]
    for f in core_files:
        path = ROOT / f
        files[f] = _read_file_safe(path, 8000)
    
    # Seed nodes
    seed_nodes_dir = ROOT / "seed_nodes"
    if seed_nodes_dir.exists():
        for f in seed_nodes_dir.glob("*.py"):
            files[f"seed_nodes/{f.name}"] = _read_file_safe(f, 4000)
    
    # Seed brains
    seed_brains_dir = ROOT / "seed_brains"
    if seed_brains_dir.exists():
        for f in seed_brains_dir.glob("*.py"):
            files[f"seed_brains/{f.name}"] = _read_file_safe(f, 4000)
    
    # Workbench JS
    for js_file in ["workbench.js", "workbench-api.js", "workbench-state.js", "workbench-graph.js", "workbench-editor.js"]:
        path = ROOT / js_file
        files[js_file] = _read_file_safe(path, 5000)
    
    return files


def run(ctx):
    """Self-modify node: LLM proposes wiring patches and node file changes."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    
    # Context for self-modification
    last_error = state.get("last_error", "")
    last_reflection = state.get("last_reflection", {})
    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    
    # Capture codebase
    codebase = _capture_codebase()
    codebase_json = json.dumps(codebase, ensure_ascii=False)[:30000]
    
    # Build prompt
    prompt = f"""You are the SELF_MODIFY node of endgame-ai. You may rewrite wiring.json AND write new node files to live_nodes/.

GOAL: {goal}
CURRENT STEP: {step_goal}
LAST ERROR: {last_error or "none"}
LAST REFLECTION: {json.dumps(last_reflection)}

CURRENT WIRING (truncated):
{json.dumps(wiring, indent=2)[:8000]}

CODEBASE (essential files):
{codebase_json}

Return a wiring_patch record with:
- wiring_patches: list of {{"op": "set|delete", "path": "json.path", "value": ...}}
- node_writes: list of {{"path": "live_nodes/filename.py", "content": "..."}}
- node_deletes: list of "live_nodes/filename.py"

RULES:
- wiring_patches modify wiring.json (topology, prompts, config, etc.)
- node_writes create/replace node files in live_nodes/
- node_deletes remove node files from live_nodes/
- Changes should address the failure context
- Keep patches minimal and focused
"""

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("self_modify", ""),
        payload={"prompt": prompt, "goal": goal, "state": state},
        wiring=wiring
    )
    
    if record.get("record_type") != "wiring_patch":
        raise RuntimeError(f"self_modify expected record_type=wiring_patch, got {record.get('record_type')}")
    
    data = record.get("data", {})
    
    # Validate structure
    wiring_patches = data.get("wiring_patches", [])
    node_writes = data.get("node_writes", [])
    node_deletes = data.get("node_deletes", [])
    
    # Apply patches using nodes.apply_wiring_patch (but we return the patch for organism to apply)
    # The organism loop will call nodes.apply_wiring_patch when it sees the patch
    
    return "modified", {
        "wiring_patch": {
            "wiring_patches": wiring_patches,
            "node_writes": node_writes,
            "node_deletes": node_deletes,
        },
        "self_modify": {
            "status": "proposed",
            "patches": len(wiring_patches),
            "writes": len(node_writes),
            "deletes": len(node_deletes),
        },
    }