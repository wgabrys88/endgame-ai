from __future__ import annotations

import pathlib
import subprocess
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes


ROOT = pathlib.Path(__file__).resolve().parent
SKIP_PREFIXES = ("runtime_",)
BINARY_SUFFIXES = {".pyc", ".pyd", ".dll", ".exe", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

DATASHEET = bus.datasheet(
    "node_self_modify",
    kind="llm_git_firmware_update",
    inputs=["goal", "failure", "runtime_evidence", "git_context", "workspace_manifest"],
    signals=["modified", "modify_failed", "error"],
    writes=["git_evolution_patch", "self_modify", "desktop_tree_text", "focused_title"],
    record_type="git_evolution_patch",
)


def _git(args: list[str]) -> str:
    cp = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return cp.stdout


def _zsplit(raw: str) -> set[str]:
    return {item for item in raw.split("\0") if item}


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
        if any(part.startswith(SKIP_PREFIXES) for part in parts):
            continue
        files.append({
            "path": rel.replace("\\", "/"),
            "size": path.stat().st_size,
            "tracked": rel in tracked,
            "status": status.get(rel, "clean" if rel in tracked else "untracked"),
            "binary": path.suffix.lower() in BINARY_SUFFIXES,
        })
    return {
        "current_commit": nodes.git_head_sha(),
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
    }


def _runtime_evidence(wiring: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    raw_logs = sorted(ROOT.glob("runtime_raw_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    return {
        "state_path": _evidence_file(brain.root_path(wiring.get("paths", {}).get("state"), "runtime_state.json")),
        "runtime_log_path": _evidence_file(brain.root_path(wiring.get("paths", {}).get("runtime_log"), "runtime_log.ndjson")),
        "raw_log_paths": [_evidence_file(path) for path in raw_logs],
        "current_state_keys": sorted(state.keys()),
        "has_fresh_observation": all(key in state for key in ("desktop_tree_text", "focused_title", "fresh_scan")),
    }


def run(ctx):
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}
    git_context = nodes.prepare_self_evolution(wiring)

    fresh_obs = state.get("fresh_observation", {})
    payload = {
        "goal": goal,
        "observation": bus.observation_brief(state),
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
                "last_error": state.get("last_error"),
            },
            "evidence": _runtime_evidence(wiring, state),
        },
        "git_context": git_context,
        "workspace_manifest": _capture_workspace_manifest(),
        "full_file_access": {
            "mode": git_context["context_mode"],
            "github_branch_url": git_context.get("branch_url", ""),
            "local_repo_root": str(ROOT),
            "rule": "Use the checked-out repository, workspace manifest, fresh observation, and runtime evidence. The local organism applies, commits, and pushes on the current branch.",
        },
        "patch_contract": {
            "record_type": "git_evolution_patch",
            "data": {
                "summary": "short human summary",
                "rationale": "runtime/code evidence for the change",
                "read_files": "repo files from the stable prefix that ground this patch",
                "file_writes": "list of {path:'repo relative path', content:'complete file text'}",
                "file_deletes": "list of repo relative paths",
                "wiring_patches": "list of {op:'set'|'delete', path:'dotted.path', value:any}",
                "commands": "optional list of validation commands from repo root",
                "expected_validation": "what should pass after the patch",
            },
            "notes": [
                "Target root-level node modules (node_planner.py, node_observe.py, etc.) and transport modules (transport_file_proxy.py, transport_xai.py, etc.).",
                "Python and JSON writes are validated before write and again after write.",
                "The local organism applies, validates, commits, and pushes on the checked-out branch.",
                "Core files core_brain.py, core_nodes.py, core_organism.py, core_desktop.py, and core_stop_check.py activate on the next process run.",
            ],
        },
    }
    if fresh_obs:
        payload["fresh_observation"] = fresh_obs

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("node_self_modify", ""),
        payload=payload,
        wiring=wiring,
        expected_record_type="git_evolution_patch",
        request_config={"web_search": wiring.get("self_modify", {}).get("web_search", {})},
    )
    if record.get("record_type") != "git_evolution_patch":
        raise RuntimeError(f"self_modify expected record_type=git_evolution_patch, got {record.get('record_type')}")

    data = record.get("data", {})
    obs = brain.last_fresh_observation()
    return bus.emit("modified", {
        "observed_at": obs.get("observed_at"),
        "fresh_scan": obs.get("fresh_scan"),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "focused_title": obs.get("focused_title", ""),
        "git_evolution_patch": {
            "summary": data.get("summary", ""),
            "rationale": data.get("rationale", ""),
            "read_files": data.get("read_files", []),
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
    }, record=record, evidence={"git_context": git_context, "failure": payload.get("failure", {})})
