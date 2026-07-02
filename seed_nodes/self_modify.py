from __future__ import annotations

import brain
import hashlib
import pathlib


ROOT = pathlib.Path(__file__).parent.parent.resolve()
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".vscode", ".idea", "pids"}
BINARY_SUFFIXES = {".pyc", ".pyd", ".dll", ".exe", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _read_file_safe(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except Exception as exc:
        return f"<read_error {type(exc).__name__}: {exc}>"


def _file_digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _capture_workspace() -> dict[str, dict[str, object]]:
    files: dict[str, dict[str, object]] = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        info: dict[str, object] = {"size": path.stat().st_size, "sha256": _file_digest(path)}
        if path.suffix.lower() in BINARY_SUFFIXES:
            info["binary"] = True
        else:
            info["text"] = _read_file_safe(path)
        files[rel] = info
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
                "last_action": state.get("last_action", {}),
                "last_result": state.get("last_result", ""),
                "last_verification": state.get("last_verification", {}),
            },
            "runtime": {
                "state": state,
                "current_node": ctx.get("node"),
            },
            "wiring": wiring,
            "workspace_files": _capture_workspace(),
            "patch_contract": {
                "record_type": "wiring_patch",
                "data": {
                    "wiring_patches": "list of {op:'set'|'delete', path:'dotted.path', value:any}",
                    "file_writes": "list of {path:'repo relative path', content:'complete file text'}",
                    "file_deletes": "list of repo relative paths",
                    "commands": "optional list of commands to run from repo root after writes",
                },
                "notes": [
                    "Write seed_nodes/name.py or seed_brains/name.py, not live_nodes/live_brains; live copies are runtime cache.",
                    "Core files brain.py, nodes.py, organism.py, desktop.py, stop_check.py can be rewritten but activate on the next run.",
                    "Python and JSON writes are validated before any file is written.",
                ],
            },
        },
        wiring=wiring,
    )
    if record.get("record_type") != "wiring_patch":
        raise RuntimeError(f"self_modify expected record_type=wiring_patch, got {record.get('record_type')}")

    data = record.get("data", {})
    wiring_patches = data.get("wiring_patches", [])
    file_writes = data.get("file_writes", [])
    file_deletes = data.get("file_deletes", [])
    commands = data.get("commands", [])
    return "modified", {
        "evolution_patch": {
            "wiring_patches": wiring_patches,
            "file_writes": file_writes,
            "file_deletes": file_deletes,
            "commands": commands,
        },
        "self_modify": {
            "status": "proposed",
            "patches": len(wiring_patches),
            "writes": len(file_writes),
            "deletes": len(file_deletes),
            "commands": len(commands),
        },
    }
