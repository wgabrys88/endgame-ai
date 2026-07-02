from __future__ import annotations

import brain
import pathlib


ROOT = pathlib.Path(__file__).parent.parent.resolve()


def _read_file_safe(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except Exception as exc:
        return f"<read_error {type(exc).__name__}: {exc}>"


def _capture_codebase() -> dict[str, str]:
    files = {name: _read_file_safe(ROOT / name) for name in ("brain.py", "nodes.py", "organism.py", "desktop.py", "wiring.json", "stop_check.py")}
    for directory in ("seed_nodes", "seed_brains"):
        base = ROOT / directory
        if base.exists():
            for path in sorted(base.glob("*.py")):
                files[f"{directory}/{path.name}"] = _read_file_safe(path)
    return files


def run(ctx):
    """Ask the brain for wiring/live-node modifications based on current failure context."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("self_modify", ""),
        payload={
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "failure": {
                "last_error": state.get("last_error", ""),
                "last_reflection": state.get("last_reflection", {}),
            },
            "wiring": wiring,
            "codebase": _capture_codebase(),
        },
        wiring=wiring,
    )
    if record.get("record_type") != "wiring_patch":
        raise RuntimeError(f"self_modify expected record_type=wiring_patch, got {record.get('record_type')}")

    data = record.get("data", {})
    wiring_patches = data.get("wiring_patches", [])
    node_writes = data.get("node_writes", [])
    node_deletes = data.get("node_deletes", [])
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
