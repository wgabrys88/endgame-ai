import pathlib
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_wiring as wiring_mod
from core_node_base import BaseNode

ROOT = pathlib.Path(__file__).resolve().parent
BINARY_SUFFIXES = {".pyc", ".pyd", ".dll", ".exe", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
PATCH_KEYS = ("summary", "rationale", "read_files", "wiring_patches", "file_writes", "file_deletes", "commands", "expected_validation")


def _zsplit(raw: str) -> set[str]:
    return {item for item in raw.split("\0") if item}


def _status_map() -> dict[str, str]:
    status: dict[str, str] = {}
    for row in [line for line in nodes._git(["status", "--porcelain"]).stdout.splitlines() if line.strip()]:
        if len(row) >= 4:
            status[row[3:].replace("\\", "/")] = row[:2].strip() or "modified"
    return status


def _capture_workspace_manifest(wiring: dict[str, Any]) -> dict[str, Any]:
    tracked = _zsplit(nodes._git(["ls-files", "-z"]).stdout)
    untracked = _zsplit(nodes._git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout)
    status = _status_map()
    skip_prefixes = tuple(wiring["self_modify"]["evolvable"]["skip_prefixes"])
    files = []
    for rel in sorted(tracked | untracked):
        path = ROOT / rel
        if path.is_file() and not any(part.startswith(skip_prefixes) for part in pathlib.PurePosixPath(rel.replace("\\", "/")).parts):
            files.append(
                {
                    "path": rel.replace("\\", "/"),
                    "size": path.stat().st_size,
                    "tracked": rel in tracked,
                    "status": status[rel] if rel in status else ("clean" if rel in tracked else "untracked"),
                    "binary": path.suffix.lower() in BINARY_SUFFIXES,
                }
            )
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
    return {"path": rel, "exists": True, "size": path.stat().st_size}


def _runtime_evidence(wiring: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "state_path": _evidence_file(wiring_mod.root_path(wiring["paths"]["state"])),
        "control_path": _evidence_file(wiring_mod.root_path(wiring["paths"]["control"])),
        "current_state_keys": sorted(state.keys()),
        "has_observation": "desktop_tree_text" in state,
    }


def _repair_baseline(state: dict[str, Any]) -> dict[str, Any]:
    step = state.get("current_step") or {
        "description": state["goal"],
        "done_when": "The original failure is retried and its intended observable effect is proven.",
    }
    executions = bus.execution_evidence(state)
    turn = executions.get("faculties") if isinstance(executions, dict) else None
    candidate_faculties = sorted(turn.keys()) if isinstance(turn, dict) else []
    last_action = state.get("last_action") or {}
    faculty = last_action.get("faculty") if isinstance(last_action, dict) else None
    if not candidate_faculties and isinstance(faculty, str) and faculty:
        candidate_faculties = [faculty]
    return {
        "failure_signature": bus.failure_signature(state),
        "step": {
            "description": str(step["description"]),
            "done_when": str(step["done_when"]),
        },
        "candidate_faculties": candidate_faculties,
        "executions": executions,
        "verification": state.get("last_verification") or {},
        "failure": state.get("last_failure") or {},
        "error": state.get("last_error"),
        "last_action": last_action,
        "last_code": state.get("last_code") or "",
        "last_result": state.get("last_result") or {},
        "action_frame": state.get("action_frame"),
        "observation": bus.observation_brief(state),
        "captured_at_tick": state.get("tick"),
    }


class SelfModifyNode(BaseNode):
    prompt_key = "node_self_modify"
    expected_record_type = "git_evolution_patch"

    def build_payload(self, ctx):
        state, wiring = ctx["state"], ctx["wiring"]
        goal = state["effective_goal"]
        step = state.get("current_step") or {}
        self._git_context = nodes.prepare_self_evolution(wiring)
        self._failure = {
            "last_error": state.get("last_error", ""),
            "last_reflection": state.get("last_reflection", {}),
            "last_failure": state.get("last_failure", {}),
            "last_action": state.get("last_action", {}),
            "last_result": state.get("last_result", ""),
            "last_verification": state.get("last_verification", {}),
        }
        self._baseline = _repair_baseline(state)
        self._organism_contract = {
            "capabilities": nodes.capability_manifest(ctx),
            "topology": wiring_mod.topology_summary(wiring),
            "activation": wiring["self_modify"]["evolvable"]["activation"],
            "self_modify_route": "reflect.escalate/topology_patch",
            "behavioral_acceptance": "A candidate commit becomes known-good only after node_repair_validate proves the original failure resolved.",
        }
        return {
            "goal": goal,
            "step": {"description": step.get("description", goal), "done_when": step.get("done_when", "")},
            "failure": self._failure,
            "repair_baseline": self._baseline,
            "runtime": {
                "state_summary": {
                    "current_node": ctx.get("node"),
                    "tick": state.get("tick"),
                    "last_error": state.get("last_error"),
                },
                "evidence": _runtime_evidence(wiring, state),
            },
            "context_mode": self._git_context["context_mode"],
            "github_branch_url": self._git_context.get("branch_url", ""),
            "local_repo_root": str(ROOT),
            "observation": bus.observation_brief(state),
            "git_context": self._git_context,
            "workspace_manifest": _capture_workspace_manifest(wiring),
            "organism_contract": self._organism_contract,
        }

    def run(self, ctx):
        state = ctx["state"]
        self.request_config = {"web_search": ctx["wiring"]["self_modify"]["web_search"]}
        record = self.think(ctx)
        data = record.data
        obs = brain.last_observation()
        repair_id = f"repair-{state['tick']}-{self._baseline['failure_signature']}"
        repair_validation = {
            "repair_id": repair_id,
            "status": "awaiting_apply",
            "summary": data["summary"],
            "rationale": data["rationale"],
            "expected_validation": data["expected_validation"],
            "baseline": self._baseline,
            "proposed_at_tick": state["tick"],
        }
        effective = (
            f"{state['effective_goal']}\n\n[SELF_MODIFY] Proposed candidate repair {repair_id}: "
            f"{data['summary']}. Structural patches: {len(data['wiring_patches'])}, "
            f"writes: {len(data['file_writes'])}, deletes: {len(data['file_deletes'])}. "
            "The repair is not accepted until a fresh behavioral probe resolves the captured failure."
        )
        patch = {
            "observed_at": obs.get("observed_at"),
            "desktop_tree_text": obs.get("desktop_tree_text", ""),
            "git_evolution_patch": {key: data[key] for key in PATCH_KEYS},
            "self_modify": {
                "status": "proposed",
                "git_context": self._git_context,
                "patches": len(data["wiring_patches"]),
                "writes": len(data["file_writes"]),
                "deletes": len(data["file_deletes"]),
                "commands": len(data["commands"]),
                "repair_id": repair_id,
            },
            "repair_validation": repair_validation,
            "effective_goal": effective,
        }
        return bus.emit(
            "modified",
            patch,
            record=record,
            evidence={
                "git_context": self._git_context,
                "failure": self._failure,
                "repair_baseline": self._baseline,
                "organism_contract": self._organism_contract,
            },
        )


def run(ctx):
    return SelfModifyNode().run(ctx)
