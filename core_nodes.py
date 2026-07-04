"""Hot-swappable node loader and one-node execution chokepoint."""
from __future__ import annotations

import importlib.util
import copy
import ctypes
import json
import os
import pathlib
import subprocess
import sys
import time
import types
from abc import ABC, abstractmethod
from typing import Any

import core_brain as brain
import core_bus as bus
import core_desktop as desktop

ROOT = pathlib.Path(__file__).parent.resolve()


def _path(wiring: dict[str, Any], key: str, default: str) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get(key), default)


def _load_node(node_name: str, wiring: dict[str, Any]):
    node_dir = _path(wiring, "nodes", ".")
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
    
    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        wiring = ctx["wiring"]
        state = ctx.get("state", {})
        prompt = wiring.get("prompts", {}).get(self.prompt_key, "")
        record = brain.think(
            prompt,
            {
                "goal": ctx.get("goal", ""),
                "state": bus.state_brief(state),
                "fresh_observation": state.get("fresh_observation") or bus.observation_brief(state),
            },
            wiring,
            expected_record_type=self.expected_record_type,
        )
        if record.get("record_type") != self.expected_record_type:
            raise RuntimeError(f"{self.prompt_key} expected record_type {self.expected_record_type!r}, got {record.get('record_type')!r}")
        data = record.get("data", {})
        signal = self.signal_from_data(data)
        patch = self.patch_from_record(record)
        return bus.emit(signal, patch, record=record, evidence={"state": bus.state_brief(state)})


def call_node(node_name: str, ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    wiring = ctx["wiring"]
    mod = _load_node(node_name, wiring)
    result = mod.run(ctx)
    output = bus.coerce_node_output(node_name, result)
    bus.validate_signal(wiring, node_name, output.signal)
    patch = dict(output.patch)
    patch.setdefault("_last_bus_frame", output.trace(node=node_name))
    sheet = getattr(mod, "DATASHEET", None)
    if isinstance(sheet, dict):
        patch.setdefault("_last_datasheet", dict(sheet))
    return output.signal, patch


def topology_summary(wiring: dict[str, Any]) -> dict[str, Any]:
    topo = wiring.get("topology", {})
    return {
        "cycle_start": topo.get("cycle_start"),
        "nodes": list(topo.get("nodes", [])),
        "edges": topo.get("edges", {}),
    }


def node_datasheets(wiring: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Load compact datasheets exported by node modules."""
    sheets: dict[str, dict[str, Any]] = {}
    for node_name in wiring.get("topology", {}).get("nodes", []):
        try:
            mod = _load_node(str(node_name), wiring)
        except Exception:
            continue
        sheet = getattr(mod, "DATASHEET", None)
        if isinstance(sheet, dict):
            sheets[str(node_name)] = dict(sheet)
    return sheets


def topology_mermaid(wiring: dict[str, Any]) -> str:
    return bus.mermaid_state_diagram(wiring, node_datasheets(wiring))


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
BLOCKED_EVOLVE_PARTS = {".git", "__pycache__"}
BLOCKED_EVOLVE_PREFIXES = ("runtime_",)
BLOCKED_EVOLVE_NAMES: set[str] = set()
CORE_FILES = {
    "core_brain.py",
    "core_desktop.py",
    "core_nodes.py",
    "core_organism.py",
    "core_stop_check.py",
}
MIN_CORE_DESKTOP_LINES = 80


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
    if path.name.startswith(BLOCKED_EVOLVE_PREFIXES):
        raise ValueError(f"self_modify path targets runtime artifact: {repo_rel.as_posix()}")
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
        if rel == "core_desktop.py":
            if "class Desktop" not in content:
                raise ValueError("core_desktop.py must retain class Desktop")
            if content.count("\n") + (1 if content and not content.endswith("\n") else 0) < MIN_CORE_DESKTOP_LINES:
                raise ValueError(f"core_desktop.py below minimum line count ({MIN_CORE_DESKTOP_LINES})")
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
    if rel == "wiring.json" or rel in {
        "node_planner.py", "node_scheduler.py", "node_observe.py", "node_execute.py", "node_frame_action.py",
        "node_verify.py", "node_reflect.py", "node_self_modify.py", "node_satisfied.py", "node_error.py",
        "transport_file_proxy.py", "transport_xai.py", "transport_openai.py", "transport_opencode.py",
        "transport_browser_ai.py", "core_observation.py",
    }:
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


def known_good_commit(wiring: dict[str, Any]) -> str:
    return str(wiring.get("self_modify", {}).get("known_good_commit") or "").strip()


def hot_swap_to_known_good(
    wiring: dict[str, Any],
    *,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    """Restore tracked body files from the configured known-good commit (self hot-swap)."""
    sha = known_good_commit(wiring)
    if not sha:
        return {"hot_swapped": False, "reason": "no_known_good_commit"}
    if paths:
        targets = [str(p).replace("\\", "/") for p in paths if str(p).strip()]
    else:
        tracked = [line.split("\t", 1)[-1].strip() for line in _git(["ls-files"]).stdout.splitlines() if line.strip()]
        targets = sorted(
            p for p in tracked
            if p.endswith(tuple(EVOLVABLE_SUFFIXES)) or p in EVOLVABLE_NAMES
        )
    if not targets:
        return {"hot_swapped": False, "reason": "no_targets", "commit": sha}
    _git(["checkout", sha, "--", *targets])
    return {"hot_swapped": True, "commit": sha, "paths": targets}


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
    index = desktop.last_action_index() or state.get("action_index") or {}
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
    fresh_observation = state.get("fresh_observation") or brain.last_fresh_observation() or bus.observation_brief(state)
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

    def _focus_node_window(node: dict[str, Any]) -> dict[str, Any]:
        hwnd = int(node.get("hwnd") or 0)
        if hwnd:
            return d.focus_window(f"hwnd:{hwnd}")
        parent_id = str(node.get("parent_id") or "")
        if parent_id.startswith("W"):
            return d.focus_window(parent_id)
        return {"ok": True, "action": "focus_window", "skipped": True}

    def click_node(node_id: str) -> dict[str, Any]:
        node = dict(_action_index(state).get(str(node_id), {}) or {})
        if not node:
            node = node_by_id(node_id)
        if not node:
            return {"ok": False, "action": "click_node", "error": f"node not found: {node_id}"}
        focus_res = _focus_node_window(node)
        if not focus_res.get("ok", False):
            return {"ok": False, "action": "click_node", "error": "focus before click failed", "focus": focus_res}
        x, y = _node_center(node)
        click_res = d.click(x, y, int(node.get("hwnd") or 0))
        return {"ok": bool(click_res.get("ok", True)), "action": "click_node", "node_id": node_id, "focus": focus_res, "click": click_res}

    def scroll_node(node_id: str, amount: int = -3) -> dict[str, Any]:
        node = dict(_action_index(state).get(str(node_id), {}) or {})
        if not node:
            node = node_by_id(node_id)
        if not node:
            return {"ok": False, "action": "scroll_node", "error": f"node not found: {node_id}"}
        x, y = _node_center(node)
        return d.scroll(x, y, int(amount), int(node.get("hwnd") or 0))

    class _PyAutoGuiCompat:
        """Dependency-free pyautogui-shaped facade backed by the organism body."""

        def click(self, x: int | None = None, y: int | None = None, clicks: int = 1, interval: float = 0.0, **kwargs: Any) -> Any:
            if x is None or y is None:
                return {"ok": False, "action": "pyautogui.click", "error": "x and y are required in this body"}
            result = None
            for _ in range(max(1, int(clicks or 1))):
                result = d.click(int(x), int(y), int(kwargs.get("hwnd") or 0))
                if interval:
                    time.sleep(float(interval))
            return result

        def write(self, text: str, interval: float = 0.0) -> Any:
            if interval:
                for ch in str(text):
                    d.type_text(ch)
                    time.sleep(float(interval))
                return {"ok": True, "action": "pyautogui.write", "chars": len(str(text))}
            return d.type_text(str(text))

        typewrite = write

        def press(self, key: str, presses: int = 1, interval: float = 0.0) -> Any:
            result = None
            for _ in range(max(1, int(presses or 1))):
                result = d.press_key(str(key))
                if interval:
                    time.sleep(float(interval))
            return result

        def hotkey(self, *keys: str) -> Any:
            if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
                keys = tuple(keys[0])
            return d.hotkey(list(keys))

        def scroll(self, clicks: int, x: int | None = None, y: int | None = None, **kwargs: Any) -> Any:
            if x is None or y is None:
                return d.scroll(0, 0, int(clicks), int(kwargs.get("hwnd") or 0))
            return d.scroll(int(x), int(y), int(clicks), int(kwargs.get("hwnd") or 0))

        def sleep(self, seconds: float) -> None:
            time.sleep(float(seconds))

    pyautogui = _PyAutoGuiCompat()
    pag = pyautogui
    
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
        "pyautogui": pyautogui,
        "pag": pag,
        
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
        "types": types,
        
        # Repository context
        "wiring_limit": wiring_limit,
        "repo_root": str(ROOT),
        "python_executable": sys.executable,
        "topology_summary": topology_summary(wiring),
        "topology_mermaid": topology_mermaid(wiring),
        
        # Context
        "state": state,
        "wiring": wiring,
        "goal": goal,
        "last": last,
        "fresh_observation": fresh_observation,
        "desktop_tree": state.get("desktop_tree", {}),
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "observation_artifact": state.get("observation_artifact", {}),
        "focused_title": state.get("focused_title", ""),
        "observed_at": state.get("observed_at"),
        "fresh_scan": state.get("fresh_scan", False),
    }
