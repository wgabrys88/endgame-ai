import pathlib
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_wiring as wiring_mod

ROOT = pathlib.Path(__file__).resolve().parent
SKIP_PREFIXES = ("runtime_",)
BINARY_SUFFIXES = {".pyc", ".pyd", ".dll", ".exe", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _zsplit(raw: str) -> set[str]:
    return {item for item in raw.split("\0") if item}


def _status_map() -> dict[str, str]:
    status: dict[str, str] = {}
    for row in [line for line in nodes._git(["status", "--porcelain"]).stdout.splitlines() if line.strip()]:
        if len(row) >= 4:
            status[row[3:].replace("\\", "/")] = row[:2].strip() or "modified"
    return status


def _capture_workspace_manifest() -> dict[str, Any]:
    tracked = _zsplit(nodes._git(["ls-files", "-z"]).stdout)
    untracked = _zsplit(nodes._git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout)
    status = _status_map()
    files = []
    for rel in sorted(tracked | untracked):
        path = ROOT / rel
        if path.is_file() and not any(part.startswith(SKIP_PREFIXES) for part in pathlib.PurePosixPath(rel.replace("\\", "/")).parts):
            files.append({"path": rel.replace("\\", "/"), "size": path.stat().st_size, "tracked": rel in tracked, "status": status.get(rel, "clean" if rel in tracked else "untracked"), "binary": path.suffix.lower() in BINARY_SUFFIXES})
    return {"current_commit": nodes.git_head_sha(), "branch": nodes.git_current_branch(), "git_status": nodes.git_worktree_status(), "files": files}


def _evidence_file(path: pathlib.Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and path.is_relative_to(ROOT) else str(path)
    return {"path": rel, "exists": False} if not path.exists() or not path.is_file() else {"path": rel, "exists": True, "size": path.stat().st_size}


def _runtime_evidence(wiring: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"state_path": _evidence_file(wiring_mod.root_path(wiring["paths"]["state"])), "event_log_path": _evidence_file(wiring_mod.root_path(wiring["paths"]["event_log"])), "control_path": _evidence_file(wiring_mod.root_path(wiring["paths"]["control"])), "current_state_keys": sorted(state.keys()), "has_observation": "desktop_tree_text" in state}


def run(ctx):
    state, wiring = ctx.get("state", {}), ctx.get("wiring", {})
    goal = state["effective_goal"]
    step = state.get("current_step") or {}
    git_context = nodes.prepare_self_evolution(wiring)
    payload = {
        "goal": goal,
        "step": {"description": step.get("description", goal), "done_when": step.get("done_when", "")},
        "failure": {"last_error": state.get("last_error", ""), "last_reflection": state.get("last_reflection", {}), "last_failure": state.get("last_failure", {}), "last_action": state.get("last_action", {}), "last_result": state.get("last_result", ""), "last_verification": state.get("last_verification", {})},
        "runtime": {"state_summary": {"current_node": ctx.get("node"), "tick": state.get("tick"), "last_error": state.get("last_error")}, "evidence": _runtime_evidence(wiring, state)},
        "context_mode": git_context["context_mode"],
        "github_branch_url": git_context.get("branch_url", ""),
        "local_repo_root": str(ROOT),
        "observation": bus.observation_brief(state),
        "git_context": git_context,
        "workspace_manifest": _capture_workspace_manifest(),
        "organism_contract": {"capabilities": nodes.capability_manifest(ctx), "topology": wiring_mod.topology_summary(wiring), "self_modify_route": "reflect.escalate/topology_patch"},
    }
    record = brain.think(wiring["prompts"]["node_self_modify"], payload, wiring, expected_record_type="git_evolution_patch", request_config={"web_search": wiring["self_modify"]["web_search"]})
    if record.get("record_type") != "git_evolution_patch":
        raise RuntimeError(f"self_modify expected record_type=git_evolution_patch, got {record.get('record_type')}")
    data = record.get("data", {})
    obs = brain.last_observation()
    effective = f"{goal}\n\n[SELF_MODIFY] Proposed evolution: {data.get('summary', '')}. Patches: {len(data.get('wiring_patches', []) or [])}, writes: {len(data.get('file_writes', []) or [])}, deletes: {len(data.get('file_deletes', []) or [])}."
    patch = {
        "observed_at": obs.get("observed_at"), "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "git_evolution_patch": {key: data.get(key, [] if key.endswith("s") else "") for key in ("summary", "rationale", "read_files", "wiring_patches", "file_writes", "file_deletes", "commands", "expected_validation")},
        "self_modify": {"status": "proposed", "git_context": git_context, "patches": len(data.get("wiring_patches", []) or []), "writes": len(data.get("file_writes", []) or []), "deletes": len(data.get("file_deletes", []) or []), "commands": len(data.get("commands", []) or [])},
        "effective_goal": effective,
    }
    return bus.emit("modified", patch, record=bus.Record.from_json(record), evidence={"git_context": git_context, "failure": payload["failure"], "organism_contract": payload["organism_contract"]})
