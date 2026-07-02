from __future__ import annotations

import hashlib
import pathlib
import subprocess
from typing import Any

import brain
import desktop
import nodes


ROOT = pathlib.Path(__file__).parent.parent.resolve()
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".vscode", ".idea", "pids"}
BINARY_SUFFIXES = {".pyc", ".pyd", ".dll", ".exe", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _git(args: list[str]) -> str:
    cp = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return cp.stdout


def _zsplit(raw: str) -> set[str]:
    return {item for item in raw.split("\0") if item}


def _file_digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _status_map() -> dict[str, str]:
    rows = [line for line in _git(["status", "--porcelain"]).splitlines() if line.strip()]
    status: dict[str, str] = {}
    for row in rows:
        if len(row) >= 4:
            status[row[3:].replace("\\", "/")] = row[:2].strip() or "modified"
    return status


def _capture_workspace_manifest() -> dict[str, Any]:
    tracked = _zsplit(_git(["ls-files", "-z"]))
    untracked = _zsplit(_git(["ls-files", "--others", "--exclude-standard", "-z"]))
    status = _status_map()
    files: list[dict[str, Any]] = []
    for rel in sorted(tracked | untracked):
        path = ROOT / rel
        if not path.is_file():
            continue
        parts = pathlib.PurePosixPath(rel.replace("\\", "/")).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        files.append({
            "path": rel.replace("\\", "/"),
            "size": path.stat().st_size,
            "sha256": _file_digest(path),
            "tracked": rel in tracked,
            "status": status.get(rel, "clean" if rel in tracked else "untracked"),
            "binary": path.suffix.lower() in BINARY_SUFFIXES,
        })
    return {
        "commit_sha": nodes.git_head_sha(),
        "branch": nodes.git_current_branch(),
        "git_status": nodes.git_worktree_status(),
        "files": files,
    }


def _evidence_file(path: pathlib.Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    if not path.exists() or not path.is_file():
        return {"path": rel, "exists": False}
    return {
        "path": rel,
        "exists": True,
        "size": path.stat().st_size,
        "sha256": _file_digest(path),
    }


def _runtime_evidence(wiring: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    raw_logs = sorted(ROOT.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    return {
        "state_path": _evidence_file(brain.root_path(wiring.get("paths", {}).get("state"), "state.json")),
        "runtime_log_path": _evidence_file(brain.root_path(wiring.get("paths", {}).get("runtime_log"), "comms/runtime.ndjson")),
        "raw_log_paths": [_evidence_file(path) for path in raw_logs],
        "current_state_keys": sorted(state.keys()),
        "has_fresh_observation": all(key in state for key in ("desktop_tree", "screen_text", "focused_title", "fresh_scan")),
    }


def run(ctx):
    """Ask Grok for a git-native self-evolution patch based on manifests and evidence paths."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}
    obs = desktop.observe(wiring.get("observe_config", {}))
    git_context = nodes.prepare_self_evolution(wiring)

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
                "state_summary": {
                    "current_node": ctx.get("node"),
                    "tick": state.get("tick"),
                    "focused_title": obs.get("focused_title", ""),
                    "fresh_scan": obs.get("fresh_scan", False),
                    "observed_at": obs.get("observed_at"),
                    "screen_text_chars": len(str(obs.get("screen_text", ""))),
                    "element_count": int((obs.get("desktop_tree", {}) or {}).get("element_count", 0) or 0),
                    "window_count": int((obs.get("desktop_tree", {}) or {}).get("window_count", 0) or 0),
                    "last_error": state.get("last_error"),
                },
                "observation": {
                    "focused_title": obs.get("focused_title", ""),
                    "fresh_scan": obs.get("fresh_scan", False),
                    "observed_at": obs.get("observed_at"),
                    "screen_text": obs.get("screen_text", ""),
                    "desktop_tree": obs.get("desktop_tree", {}),
                },
                "evidence": _runtime_evidence(wiring, state),
            },
            "git_context": git_context,
            "workspace_manifest": _capture_workspace_manifest(),
            "full_file_access": {
                "mode": git_context["context_mode"],
                "github_branch_url": git_context.get("branch_url", ""),
                "published": git_context.get("published", False),
                "local_repo_root": str(ROOT),
                "rule": "Do not infer full file contents from the manifest. Use the GitHub branch when published; otherwise propose only changes justified by manifest, wiring, and runtime evidence.",
            },
            "patch_contract": {
                "record_type": "git_evolution_patch",
                "data": {
                    "summary": "short human summary",
                    "rationale": "runtime/code evidence for the change",
                    "file_writes": "list of {path:'repo relative path', content:'complete file text'}",
                    "file_deletes": "list of repo relative paths",
                    "wiring_patches": "list of {op:'set'|'delete', path:'dotted.path', value:any}",
                    "commands": "optional list of validation commands from repo root",
                    "expected_validation": "what should pass after the patch",
                },
                "notes": [
                    "Target organism_nodes/ for node changes and brain_transports/ for transport changes.",
                    "Python and JSON writes are validated before write and again after write.",
                    "The local organism applies, validates, commits, and may publish; Grok must not push directly.",
                    "Core files brain.py, nodes.py, organism.py, desktop.py, and stop_check.py activate on the next process run.",
                ],
            },
        },
        wiring=wiring,
        expected_record_type="git_evolution_patch",
        request_config={"web_search": wiring.get("self_modify", {}).get("web_search", {})},
    )
    if record.get("record_type") != "git_evolution_patch":
        raise RuntimeError(f"self_modify expected record_type=git_evolution_patch, got {record.get('record_type')}")

    data = record.get("data", {})
    return "modified", {
        "observed_at": obs.get("observed_at"),
        "fresh_scan": obs.get("fresh_scan"),
        "desktop_tree": obs.get("desktop_tree", {}),
        "screen_text": obs.get("screen_text", ""),
        "focused_title": obs.get("focused_title", ""),
        "git_evolution_patch": {
            "summary": data.get("summary", ""),
            "rationale": data.get("rationale", ""),
            "wiring_patches": data.get("wiring_patches", []),
            "file_writes": data.get("file_writes", []),
            "file_deletes": data.get("file_deletes", []),
            "commands": data.get("commands", []),
            "expected_validation": data.get("expected_validation", ""),
        },
        "self_modify": {
            "status": "proposed",
            "git_context": git_context,
            "patches": len(data.get("wiring_patches", []) or []),
            "writes": len(data.get("file_writes", []) or []),
            "deletes": len(data.get("file_deletes", []) or []),
            "commands": len(data.get("commands", []) or []),
        },
    }
