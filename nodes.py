"""Hot-swappable node loader and one-node execution chokepoint."""
from __future__ import annotations

import importlib.util
import copy
import json
import os
import pathlib
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from typing import Any

import brain
import desktop

ROOT = pathlib.Path(__file__).parent.resolve()


def _path(wiring: dict[str, Any], key: str, default: str) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get(key), default)


def _load_node(node_name: str, wiring: dict[str, Any]):
    node_dir = _path(wiring, "nodes", "organism_nodes")
    path = node_dir / f"{node_name}.py"
    if not path.exists():
        raise RuntimeError(f"topology node '{node_name}' has no module at {path}")
    spec = importlib.util.spec_from_file_location(f"endgame_node_{node_name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load node module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "run"):
        raise RuntimeError(f"node '{node_name}' does not export run(ctx)")
    return mod


class BaseNode(ABC):
    """Base class for nodes that call brain.think() with a prompt from wiring.json.
    
    Subclasses only need to define:
    - prompt_key: key in wiring["prompts"] (e.g., "planner", "decide")
    - expected_record_type: expected record_type in brain response (e.g., "plan", "decision")
    - signal_from_data(): extracts next_signal from record["data"]
    - patch_from_record(): builds patch dict from record
    """
    
    prompt_key: str = ""
    expected_record_type: str = ""
    
    @abstractmethod
    def signal_from_data(self, data: dict[str, Any]) -> str:
        """Extract next_signal from record data."""
        ...
    
    @abstractmethod
    def patch_from_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Build patch dict from full record."""
        ...
    
    def run(self, ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        wiring = ctx["wiring"]
        prompt = wiring.get("prompts", {}).get(self.prompt_key, "")
        record = brain.think(
            prompt,
            {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})},
            wiring,
            expected_record_type=self.expected_record_type,
        )
        if record.get("record_type") != self.expected_record_type:
            raise RuntimeError(f"{self.prompt_key} expected record_type {self.expected_record_type!r}, got {record.get('record_type')!r}")
        data = record.get("data", {})
        signal = self.signal_from_data(data)
        patch = self.patch_from_record(record)
        return signal, patch


def call_node(node_name: str, ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    wiring = ctx["wiring"]
    mod = _load_node(node_name, wiring)
    result = mod.run(ctx)
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"node '{node_name}' contract violation: expected (signal, patch)")
    signal, patch = result
    if not isinstance(signal, str) or not signal:
        raise RuntimeError(f"node '{node_name}' contract violation: signal must be a non-empty string")
    if not isinstance(patch, dict):
        raise RuntimeError(f"node '{node_name}' contract violation: patch must be dict")
    return signal, patch


def topology_summary(wiring: dict[str, Any]) -> dict[str, Any]:
    topo = wiring.get("topology", {})
    return {
        "cycle_start": topo.get("cycle_start"),
        "nodes": list(topo.get("nodes", [])),
        "edges": topo.get("edges", {}),
    }


# =============================================================================
# Desktop observation helpers for nodes
# =============================================================================


def observe_screen(ctx: dict[str, Any] | None = None) -> dict[str, int]:
    """Get screen dimensions."""
    return desktop.observe_screen()


def last_desktop_tree(ctx: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Get the last desktop tree."""
    return desktop.last_desktop_tree()


def get_focused_title(ctx: dict[str, Any] | None = None) -> str:
    """Get the title of the currently focused window."""
    return desktop.get_focused_title()


# =============================================================================
# Execute namespace builder
# =============================================================================


def _get_desktop_instance():
    """Get the singleton Desktop instance."""
    return desktop.get_desktop()


EVOLVABLE_SUFFIXES = {".py", ".json", ".md"}
EVOLVABLE_NAMES = {".gitattributes", ".gitignore", "LICENSE"}
BLOCKED_EVOLVE_PARTS = {".git", "__pycache__", "comms", "pids"}
BLOCKED_EVOLVE_NAMES = {"state.json", "stop.txt"}
CORE_FILES = {"brain.py", "desktop.py", "nodes.py", "organism.py", "stop_check.py"}


def _patch_data(parsed: dict[str, Any]) -> dict[str, Any]:
    data = (parsed or {}).get("data", parsed or {})
    if not isinstance(data, dict):
        raise ValueError("self_modify patch data must be an object")
    return data


def _evolution_target(raw_path: str, *, deleting: bool = False) -> tuple[pathlib.Path, str]:
    rel = str(raw_path).replace("\\", "/").strip().lstrip("/")
    if not rel:
        raise ValueError("self_modify path is empty")
    requested = pathlib.Path(rel)
    path = (ROOT / requested).resolve() if not requested.is_absolute() else requested.resolve()
    try:
        repo_rel = path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"self_modify path must stay under repository root: {raw_path}") from exc

    parts = {part.lower() for part in repo_rel.parts}
    if parts & BLOCKED_EVOLVE_PARTS:
        raise ValueError(f"self_modify path targets runtime/private area: {repo_rel.as_posix()}")
    if path.name in BLOCKED_EVOLVE_NAMES:
        raise ValueError(f"self_modify path targets runtime state: {repo_rel.as_posix()}")
    if path.name not in EVOLVABLE_NAMES and path.suffix not in EVOLVABLE_SUFFIXES:
        raise ValueError(f"self_modify path has unsupported file type: {repo_rel.as_posix()}")
    if deleting and repo_rel.as_posix() in CORE_FILES | {"wiring.json"}:
        raise ValueError(f"self_modify may rewrite but not delete core file: {repo_rel.as_posix()}")
    return path, repo_rel.as_posix()


def _validate_content(path: pathlib.Path, rel: str, content: Any) -> str:
    if not isinstance(content, str):
        raise ValueError(f"self_modify content for {rel} must be a string")
    if path.suffix == ".py":
        compile(content, rel, "exec")
    elif path.suffix == ".json":
        json.loads(content)
    return content


def _atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading_id()}")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def threading_id() -> int:
    try:
        import threading
        return threading.get_ident()
    except Exception:
        return 0


def _apply_wiring_ops(wiring: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(wiring)
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError(f"wiring_patch must be object: {patch!r}")
        op = patch.get("op", "set")
        dotted = str(patch.get("path") or "")
        if not dotted:
            raise ValueError("wiring_patch missing path")
        parts = dotted.split(".")
        cur = patched
        for part in parts[:-1]:
            if not isinstance(cur.get(part), dict):
                cur[part] = {}
            cur = cur[part]
        if op == "set":
            cur[parts[-1]] = patch.get("value")
        elif op == "delete":
            cur.pop(parts[-1], None)
        else:
            raise ValueError(f"unknown wiring_patch op: {op}")
    json.dumps(patched, ensure_ascii=False, default=str)
    return patched


def _collect_file_writes(data: dict[str, Any]) -> list[dict[str, str]]:
    return list(data.get("file_writes") or [])


def _collect_file_deletes(data: dict[str, Any]) -> list[str]:
    return [str(path) for path in list(data.get("file_deletes") or [])]


def _declared_read_files(data: dict[str, Any]) -> set[str]:
    return {str(path).replace("\\", "/").strip().lstrip("/") for path in list(data.get("read_files") or []) if str(path).strip()}


def _activation_bucket(rel: str) -> str:
    if rel == "wiring.json" or rel.startswith("organism_nodes/") or rel.startswith("brain_transports/"):
        return "immediate"
    if rel in CORE_FILES:
        return "next_run"
    return "supporting"


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check and cp.returncode != 0:
        detail = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return cp


def git_head_sha() -> str:
    return _git(["rev-parse", "HEAD"]).stdout.strip()


def git_current_branch() -> str:
    return _git(["branch", "--show-current"]).stdout.strip()


def git_worktree_status() -> list[str]:
    return [line for line in _git(["status", "--porcelain"]).stdout.splitlines() if line.strip()]


def _remote_url(remote: str) -> str:
    cp = _git(["remote", "get-url", remote], check=False)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _github_branch_url(remote_url: str, branch: str) -> str:
    url = remote_url.strip()
    if not url:
        return ""
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url.removeprefix("git@github.com:")
    if url.endswith(".git"):
        url = url[:-4]
    return f"{url}/tree/{branch}" if url.startswith("https://github.com/") else ""


def prepare_self_evolution(wiring: dict[str, Any]) -> dict[str, Any]:
    """Describe the checked-out branch before asking the brain for an evolution patch."""
    cfg = wiring.get("self_modify", {}).get("git", {})
    remote = str(cfg.get("remote") or "origin")
    branch = git_current_branch()
    remote_url = _remote_url(remote)
    return {
        "context_mode": wiring.get("self_modify", {}).get("context_mode", "checked_out_branch"),
        "branch": branch,
        "current_commit": git_head_sha(),
        "worktree_status": git_worktree_status(),
        "remote": remote,
        "remote_url": remote_url,
        "branch_url": _github_branch_url(remote_url, branch),
        "commit_target": "checked_out_branch",
        "push_after_commit": bool(cfg.get("push_after_commit", True)),
    }


def _run_evolution_commands(commands: list[Any], wiring: dict[str, Any]) -> list[dict[str, Any]]:
    if not commands:
        return []
    cfg = wiring.get("self_modify", {}).get("execution", {})
    default_timeout = cfg.get("timeout_s")
    results: list[dict[str, Any]] = []
    for item in commands:
        if isinstance(item, dict):
            command = item.get("command")
            shell = bool(item.get("shell", isinstance(command, str)))
            timeout_s = item.get("timeout_s", default_timeout)
        else:
            command = item
            shell = isinstance(command, str)
            timeout_s = default_timeout
        if not isinstance(command, (str, list)) or not command:
            raise ValueError(f"invalid self_modify command: {item!r}")
        cp = subprocess.run(
            command,
            cwd=ROOT,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=float(timeout_s) if timeout_s is not None else None,
        )
        result = {
            "command": command,
            "shell": shell,
            "returncode": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
        }
        results.append(result)
        if cp.returncode != 0:
            raise RuntimeError(f"self_modify command failed: {result}")
    return results


def _snapshot_paths(paths: list[pathlib.Path]) -> dict[pathlib.Path, bytes | None]:
    snapshots: dict[pathlib.Path, bytes | None] = {}
    for path in paths:
        if path not in snapshots:
            snapshots[path] = path.read_bytes() if path.exists() else None
    return snapshots


def _restore_snapshots(snapshots: dict[pathlib.Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.rollback.{os.getpid()}.{threading_id()}")
            tmp.write_bytes(content)
            os.replace(tmp, path)


def apply_evolution_patch(wiring: dict[str, Any], parsed: dict[str, Any]) -> tuple[str, Any]:
    """Apply a validated self-evolution patch to canonical repository source."""
    data = _patch_data(parsed)
    read_files = _declared_read_files(data)
    wiring_patches = list(data.get("wiring_patches") or [])
    patched_wiring = _apply_wiring_ops(wiring, wiring_patches)

    writes: list[tuple[pathlib.Path, str, str]] = []
    for item in _collect_file_writes(data):
        if not isinstance(item, dict):
            raise ValueError(f"file_writes entry must be object: {item!r}")
        path, rel = _evolution_target(str(item.get("path") or ""))
        content = _validate_content(path, rel, item.get("content"))
        writes.append((path, rel, content))

    deletes: list[tuple[pathlib.Path, str]] = []
    for raw_path in _collect_file_deletes(data):
        path, rel = _evolution_target(raw_path, deleting=True)
        deletes.append((path, rel))

    missing_reads = []
    for path, rel, _ in writes:
        if path.exists() and rel not in read_files:
            missing_reads.append(rel)
    for path, rel in deletes:
        if path.exists() and rel not in read_files:
            missing_reads.append(rel)
    if wiring_patches and "wiring.json" not in read_files:
        missing_reads.append("wiring.json")
    if missing_reads:
        raise ValueError(f"self_modify patch must declare read_files for touched existing files: {sorted(set(missing_reads))}")

    touched_paths = [path for path, _, _ in writes] + [path for path, _ in deletes]
    if wiring_patches:
        touched_paths.append(ROOT / "wiring.json")
    snapshots = _snapshot_paths(touched_paths)
    rollback_on_failure = bool(wiring.get("self_modify", {}).get("execution", {}).get("rollback_on_failure", True))

    try:
        for path, _, content in writes:
            _atomic_write_text(path, content)
        for path, _ in deletes:
            path.unlink(missing_ok=True)
        if wiring_patches:
            wiring.clear()
            wiring.update(patched_wiring)
            save_wiring(wiring)

        for path, rel, _ in writes:
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), rel, "exec")
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))

        command_results = _run_evolution_commands(list(data.get("commands") or []), wiring)
    except Exception:
        if rollback_on_failure:
            _restore_snapshots(snapshots)
            if wiring_patches:
                wiring.clear()
                wiring.update(brain.load_json(ROOT / "wiring.json"))
        raise

    changed = [rel for _, rel, _ in writes] + [rel for _, rel in deletes]
    activation = {"immediate": [], "next_run": [], "supporting": []}
    for rel in changed + (["wiring.json"] if wiring_patches else []):
        activation[_activation_bucket(rel)].append(rel)
    return "set", {
        "wiring_patches": len(wiring_patches),
        "file_writes": len(writes),
        "file_deletes": len(deletes),
        "commands": command_results,
        "rollback_on_failure": rollback_on_failure,
        "changed_files": changed,
        "activation": activation,
    }


def commit_self_evolution(wiring: dict[str, Any], applied: dict[str, Any], patch_data: dict[str, Any]) -> dict[str, Any]:
    """Commit a successful validated self-evolution patch on the checked-out branch."""
    changed_files = list(applied.get("changed_files") or [])
    if applied.get("wiring_patches"):
        changed_files.append("wiring.json")
    changed_files = sorted({str(path).replace("\\", "/") for path in changed_files if str(path).strip()})
    if not changed_files:
        return {
            "committed": False,
            "reason": "no_changed_files",
            "branch": git_current_branch(),
            "commit": git_head_sha(),
        }
    _git(["add", "-A", "--", *changed_files])
    status = git_worktree_status()
    if not status:
        return {
            "committed": False,
            "reason": "no_git_changes",
            "branch": git_current_branch(),
            "commit": git_head_sha(),
            "changed_files": changed_files,
        }
    summary = str(patch_data.get("summary") or "validated self evolution").strip()
    title = "Self-modify: " + summary.replace("\n", " ")[:60]
    rationale = str(patch_data.get("rationale") or "").strip()
    expected = patch_data.get("expected_validation")
    body = json.dumps(
        {
            "branch": git_current_branch(),
            "changed_files": changed_files,
            "read_files": list(patch_data.get("read_files") or []),
            "rationale": rationale,
            "expected_validation": expected,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    _git(["commit", "-m", title, "-m", body])
    branch = git_current_branch()
    pushed = False
    git_cfg = wiring.get("self_modify", {}).get("git", {})
    if bool(git_cfg.get("push_after_commit", False)):
        _git(["push", str(git_cfg.get("remote") or "origin"), branch])
        pushed = True
    return {
        "committed": True,
        "branch": branch,
        "commit": git_head_sha(),
        "changed_files": changed_files,
        "pushed": pushed,
        "status": git_worktree_status(),
    }


def save_wiring(wiring: dict[str, Any]) -> None:
    """Atomic write of wiring.json."""
    brain.atomic_write_json(ROOT / "wiring.json", wiring)


def wiring_limit(name: str, default: int, wiring: dict[str, Any]) -> int:
    """Get a limit from wiring with default."""
    return wiring.get("limits", {}).get(name, default)


def _desktop_tree_index(state: dict[str, Any]) -> dict[str, Any]:
    tree = state.get("desktop_tree") or {}
    index = tree.get("node_index") if isinstance(tree, dict) else {}
    return index if isinstance(index, dict) else {}


def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def _node_center(node: dict[str, Any]) -> tuple[int, int]:
    if node.get("px") is not None and node.get("py") is not None:
        return int(node.get("px") or 0), int(node.get("py") or 0)
    rect = node.get("rect") if isinstance(node.get("rect"), dict) else {}
    left = int(rect.get("left", 0) or 0)
    right = int(rect.get("right", left) or left)
    top = int(rect.get("top", 0) or 0)
    bottom = int(rect.get("bottom", top) or top)
    return left + max(0, right - left) // 2, top + max(0, bottom - top) // 2


def build_capability_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    """Build the shared machine capability runtime for action and evolution nodes."""
    d = _get_desktop_instance()
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    fresh_observation = brain.last_fresh_observation() or {
        "focused_title": state.get("focused_title", ""),
        "fresh_scan": state.get("fresh_scan", False),
        "observed_at": state.get("observed_at"),
        "desktop_tree": state.get("desktop_tree", {}),
        "screen_text": state.get("screen_text", ""),
        "observation_artifact": state.get("observation_artifact", {}),
        "observation_delta": state.get("observation_delta", {}),
    }
    last = {
        "error": state.get("last_error"),
        "result": state.get("last_result", ""),
        "action": state.get("last_action", {}),
        "verification": state.get("last_verification", {}),
        "reflection": state.get("last_reflection", {}),
    }

    def node_by_id(node_id: str) -> dict[str, Any]:
        return dict(_desktop_tree_index(state).get(str(node_id), {}) or {})

    def action_nodes(action: str | None = None) -> list[dict[str, Any]]:
        nodes = []
        for node in _desktop_tree_index(state).values():
            if not isinstance(node, dict):
                continue
            node_action = node.get("action")
            if node_action and (action is None or node_action == action):
                nodes.append(dict(node))
        return nodes

    def click_node(node_id: str) -> dict[str, Any]:
        node = dict(_action_index(state).get(str(node_id), {}) or {})
        if not node:
            node = node_by_id(node_id)
        if not node:
            return {"ok": False, "action": "click_node", "error": f"node not found: {node_id}"}
        x, y = _node_center(node)
        return d.click(x, y, int(node.get("hwnd") or 0))

    def scroll_node(node_id: str, amount: int = -3) -> dict[str, Any]:
        node = dict(_action_index(state).get(str(node_id), {}) or {})
        if not node:
            node = node_by_id(node_id)
        if not node:
            return {"ok": False, "action": "scroll_node", "error": f"node not found: {node_id}"}
        x, y = _node_center(node)
        return d.scroll(x, y, int(amount), int(node.get("hwnd") or 0))
    
    return {
        # Observation
        "observe_screen": observe_screen,
        "last_desktop_tree": last_desktop_tree,
        "get_focused_title": get_focused_title,
        "node_by_id": node_by_id,
        "action_nodes": action_nodes,
        
        # Raw desktop actions
        "click": d.click,
        "click_node": click_node,
        "type_text": d.type_text,
        "press_key": d.press_key,
        "hotkey": d.hotkey,
        "scroll": d.scroll,
        "scroll_node": scroll_node,
        "focus_window": d.focus_window,
        "open_url": d.open_url,
        
        # System modules
        "subprocess": subprocess,
        "ctypes": ctypes,
        "os": __import__("os"),
        "sys": sys,
        "json": json,
        "re": __import__("re"),
        "time": time,
        "pathlib": pathlib,
        "math": __import__("math"),
        "random": __import__("random"),
        
        # Repository context
        "wiring_limit": wiring_limit,
        "repo_root": str(ROOT),
        "python_executable": sys.executable,
        
        # Context
        "state": state,
        "wiring": wiring,
        "goal": goal,
        "last": last,
        "fresh_observation": fresh_observation,
        "desktop_tree": state.get("desktop_tree", {}),
        "observation_artifact": state.get("observation_artifact", {}),
        "observation_delta": state.get("observation_delta", {}),
        "screen_text": state.get("screen_text", ""),
        "focused_title": state.get("focused_title", ""),
        "observed_at": state.get("observed_at"),
        "fresh_scan": state.get("fresh_scan", False),
    }


# Need ctypes import for build_capability_runtime.
import ctypes
