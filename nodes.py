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
        record = brain.think(prompt, {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})}, wiring)
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


def last_observation_snapshot(ctx: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Get the last full observation snapshot."""
    return desktop.last_observation_snapshot()


def get_focused_title(ctx: dict[str, Any] | None = None) -> str:
    """Get the title of the currently focused window."""
    return desktop.get_focused_title()


# =============================================================================
# Execute namespace builder
# =============================================================================


def _get_desktop_instance():
    """Get the singleton Desktop instance."""
    return desktop.get_desktop()


def execute_verb(verb: str, target: dict[str, Any] | None = None, value: str | None = None) -> str:
    """Convenience verbs for common actions."""
    d = _get_desktop_instance()
    target = target or {}
    
    if verb == "click":
        x = target.get("px") or target.get("x")
        y = target.get("py") or target.get("y")
        hwnd = target.get("hwnd", 0)
        if x is not None and y is not None:
            d.click(x, y, hwnd)
            return f"clicked at ({x},{y})"
        return "click: missing x/y"
    
    elif verb == "write":
        text = value or target.get("text", "")
        d.type_text(text)
        return f"typed: {text}"
    
    elif verb == "press":
        key = value or target.get("key", "")
        d.press_key(key)
        return f"pressed: {key}"
    
    elif verb == "hotkey":
        keys = value or target.get("keys", "")
        d.hotkey(keys)
        return f"hotkey: {keys}"
    
    elif verb == "focus":
        target_str = value or target.get("title", "")
        d.focus_window(target_str)
        return f"focused: {target_str}"
    
    elif verb == "scroll":
        amount = target.get("amount", 3)
        direction = target.get("direction", "down")
        x = target.get("px", 0)
        y = target.get("py", 0)
        hwnd = target.get("hwnd", 0)
        d.scroll(x, y, amount if direction == "down" else -amount, hwnd)
        return f"scrolled {direction} {amount}"
    
    elif verb == "wait":
        wait_time = target.get("seconds", 1)
        time.sleep(wait_time)
        return f"waited {wait_time}s"
    
    elif verb == "launch":
        cmd = value or target.get("command", "")
        subprocess.Popen(cmd, shell=True)
        return f"launched: {cmd}"
    
    elif verb == "open_url":
        browser = target.get("browser", "chrome")
        url = value or target.get("url", "")
        if browser == "chrome":
            subprocess.Popen(["chrome", url])
        else:
            import webbrowser
            webbrowser.open(url)
        return f"opened {url} in {browser}"
    
    elif verb == "remember":
        key = target.get("key", "")
        val = value or target.get("value", "")
        return f"remembered {key}={val}"
    
    return f"unknown verb: {verb}"


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
    writes = list(data.get("file_writes") or [])
    writes.extend(data.get("node_writes") or [])
    writes.extend(data.get("brain_writes") or [])
    return writes


def _collect_file_deletes(data: dict[str, Any]) -> list[str]:
    deletes = list(data.get("file_deletes") or [])
    deletes.extend(data.get("node_deletes") or [])
    deletes.extend(data.get("brain_deletes") or [])
    return [str(path) for path in deletes]


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


def require_clean_worktree() -> None:
    status = git_worktree_status()
    if status:
        sample = "\n".join(status[:20])
        raise RuntimeError(f"self_modify requires a clean git worktree before branch creation:\n{sample}")


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
    """Create a clean timestamped branch before asking Grok for a patch."""
    require_clean_worktree()
    cfg = wiring.get("self_modify", {}).get("git", {})
    remote = str(cfg.get("remote") or "origin")
    prefix = str(cfg.get("branch_prefix") or "self-evolve").strip("/")
    base_branch = git_current_branch()
    base_commit = git_head_sha()
    branch = f"{prefix}/{time.strftime('%Y%m%dT%H%M%S')}-{base_commit[:7]}"
    _git(["switch", "-c", branch])
    remote_url = _remote_url(remote)
    published = False
    if bool(cfg.get("publish_context_branch", False)):
        _git(["push", "-u", remote, branch])
        published = True
    return {
        "context_mode": wiring.get("self_modify", {}).get("context_mode", "hybrid"),
        "base_branch": base_branch,
        "branch": branch,
        "base_commit": base_commit,
        "current_commit": git_head_sha(),
        "remote": remote,
        "remote_url": remote_url,
        "branch_url": _github_branch_url(remote_url, branch),
        "published": published,
    }


def _self_evolve_prefix(wiring: dict[str, Any]) -> str:
    return str(wiring.get("self_modify", {}).get("git", {}).get("branch_prefix") or "self-evolve").strip("/")


def require_self_evolve_branch(wiring: dict[str, Any]) -> None:
    branch = git_current_branch()
    prefix = _self_evolve_prefix(wiring) + "/"
    if not branch.startswith(prefix):
        raise RuntimeError(f"self_modify patches must apply on a {prefix} branch, current branch is {branch!r}")


def _run_evolution_commands(commands: list[Any], wiring: dict[str, Any]) -> list[dict[str, Any]]:
    if not commands:
        return []
    cfg = wiring.get("self_modify", {}).get("execution", {})
    if not cfg.get("enabled", True):
        raise RuntimeError("self_modify commands requested but self_modify.execution.enabled is false")
    max_commands = int(cfg.get("max_commands", 3))
    default_timeout = float(cfg.get("timeout_s", 60))
    require_success = bool(cfg.get("require_success", True))
    if len(commands) > max_commands:
        raise RuntimeError(f"self_modify command limit exceeded: {len(commands)}/{max_commands}")
    results: list[dict[str, Any]] = []
    for item in commands:
        if isinstance(item, dict):
            command = item.get("command")
            shell = bool(item.get("shell", isinstance(command, str)))
            timeout_s = float(item.get("timeout_s", default_timeout))
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
            timeout=timeout_s,
        )
        result = {
            "command": command,
            "shell": shell,
            "returncode": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
        }
        results.append(result)
        if require_success and cp.returncode != 0:
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
    require_self_evolve_branch(wiring)
    data = _patch_data(parsed)
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
    """Commit a successful validated self-evolution patch on its timestamp branch."""
    require_self_evolve_branch(wiring)
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
    title = "Self-evolve: " + summary.replace("\n", " ")[:60]
    rationale = str(patch_data.get("rationale") or "").strip()
    expected = patch_data.get("expected_validation")
    body = json.dumps(
        {
            "branch": git_current_branch(),
            "changed_files": changed_files,
            "rationale": rationale,
            "expected_validation": expected,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    _git(["commit", "-m", title, "-m", body])
    return {
        "committed": True,
        "branch": git_current_branch(),
        "commit": git_head_sha(),
        "changed_files": changed_files,
        "status": git_worktree_status(),
    }


def save_wiring(wiring: dict[str, Any]) -> None:
    """Atomic write of wiring.json."""
    brain.atomic_write_json(ROOT / "wiring.json", wiring)


def wiring_limit(name: str, default: int, wiring: dict[str, Any]) -> int:
    """Get a limit from wiring with default."""
    return wiring.get("limits", {}).get(name, default)


def build_execute_namespace(ctx: dict[str, Any]) -> dict[str, Any]:
    """Build the namespace for execute node's exec()."""
    d = _get_desktop_instance()
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    last = {
        "error": state.get("last_error"),
        "result": state.get("last_result", ""),
        "action": state.get("last_action", {}),
        "verification": state.get("last_verification", {}),
        "reflection": state.get("last_reflection", {}),
    }
    
    return {
        # Observation
        "observe_screen": observe_screen,
        "last_observation_snapshot": last_observation_snapshot,
        "get_focused_title": get_focused_title,
        
        # Convenience verbs
        "execute_verb": execute_verb,
        
        # Raw desktop actions
        "click": d.click,
        "type_text": d.type_text,
        "press_key": d.press_key,
        "hotkey": d.hotkey,
        "scroll": d.scroll,
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
        "screen": state.get("screen", {}),
        "elements": state.get("elements", {}),
        "windows": state.get("windows", []),
        "screen_text": state.get("screen_text", ""),
        "focused_title": state.get("focused_title", ""),
    }


# Need ctypes import for build_execute_namespace
import ctypes
