from __future__ import annotations

import ast
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
from abc import ABC
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
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise RuntimeError(f"node '{node_name}' does not export run(ctx)")
    return mod


class BaseNode(ABC):

    prompt_key: str = ""
    expected_record_type: str = ""
    request_config: dict[str, Any] | None = None

    def build_payload(self, ctx: dict[str, Any]) -> dict[str, Any]:
        state = ctx.get("state", {})
        return {
            "goal": ctx.get("goal", ""),
            "state": bus.state_brief(state),
            "fresh_observation": state.get("fresh_observation") or bus.observation_brief(state),
        }

    def evidence(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"state": bus.state_brief(ctx.get("state", {}))}

    def signal_from_data(self, data: dict[str, Any], ctx: dict[str, Any]) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement signal_from_data or override run()")

    def patch_from_record(self, record: bus.Record, ctx: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} must implement patch_from_record or override run()")

    def think(self, ctx: dict[str, Any]) -> bus.Record:
        wiring = ctx["wiring"]
        prompt = wiring.get("prompts", {}).get(self.prompt_key, "")
        think_kwargs: dict[str, Any] = {"expected_record_type": self.expected_record_type}
        if self.request_config is not None:
            think_kwargs["request_config"] = self.request_config
        record = brain.think(prompt, self.build_payload(ctx), wiring, **think_kwargs)
        if record.get("record_type") != self.expected_record_type:
            raise RuntimeError(
                f"{self.prompt_key} expected record_type {self.expected_record_type!r}, "
                f"got {record.get('record_type')!r}"
            )
        return bus.Record.from_json(record)

    def run(self, ctx: dict[str, Any]) -> bus.NodeOutput:
        record = self.think(ctx)
        data = record.data
        signal = self.signal_from_data(data, ctx)
        patch = self.patch_from_record(record, ctx)
        return bus.emit(signal, patch, record=record, evidence=self.evidence(ctx))


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


def _get_desktop_instance():
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
DESTRUCTIVE_STUB_MARKERS = (
    "original implementation assumed present",
    "other methods preserved from original",
    "full original methods retained",
    "uia scan logic",
    "minimal coherent evolution patch",
)


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
        _validate_non_destructive_python_rewrite(path, rel, content)
        if rel == "core_desktop.py":
            if "class Desktop" not in content:
                raise ValueError("core_desktop.py must retain class Desktop")
            if content.count("\n") + (1 if content and not content.endswith("\n") else 0) < MIN_CORE_DESKTOP_LINES:
                raise ValueError(f"core_desktop.py below minimum line count ({MIN_CORE_DESKTOP_LINES})")
    elif path.suffix == ".json":
        json.loads(content)
    return content


def _line_count(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


def _public_python_defs(text: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            names.add(node.name)
    return names


def _validate_non_destructive_python_rewrite(path: pathlib.Path, rel: str, content: str) -> None:
    if not path.exists():
        return
    lower = content.lower()
    for marker in DESTRUCTIVE_STUB_MARKERS:
        if marker in lower:
            raise ValueError(f"self_modify content for {rel} contains destructive placeholder marker: {marker}")
    original = path.read_text(encoding="utf-8", errors="replace")
    original_lines = _line_count(original)
    new_lines = _line_count(content)
    if original_lines >= 40 and new_lines < max(20, int(original_lines * 0.55)):
        raise ValueError(
            f"self_modify rewrite of {rel} is suspiciously small "
            f"({new_lines} lines vs {original_lines}); use a minimal patch, not a replacement stub"
        )
    original_defs = _public_python_defs(original)
    new_defs = _public_python_defs(content)
    if len(original_defs) >= 5 and len(new_defs) < max(2, len(original_defs) // 2):
        missing = sorted(original_defs - new_defs)[:12]
        raise ValueError(
            f"self_modify rewrite of {rel} drops too many public definitions; "
            f"missing examples: {missing}"
        )


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


def known_good_ref_name(wiring: dict[str, Any]) -> str:
    return str(wiring.get("self_modify", {}).get("known_good_ref") or "refs/endgame/known_good").strip()


def resolve_known_good(wiring: dict[str, Any]) -> dict[str, Any]:
    ref = known_good_ref_name(wiring)
    if ref:
        cp = _git(["rev-parse", "--verify", ref], check=False)
        if cp.returncode == 0 and cp.stdout.strip():
            return {"commit": cp.stdout.strip(), "source": "git_ref", "ref": ref}
    configured = str(wiring.get("self_modify", {}).get("known_good_commit") or "").strip()
    if configured:
        return {"commit": configured, "source": "wiring_seed", "ref": ref}
    return {"commit": "", "source": "missing", "ref": ref}


def known_good_commit(wiring: dict[str, Any]) -> str:
    return str(resolve_known_good(wiring).get("commit") or "").strip()


def update_known_good_ref(wiring: dict[str, Any], commit: str, *, source: str) -> dict[str, Any]:
    sha = str(commit or "").strip()
    if not sha:
        raise ValueError("cannot update known-good ref without a commit")
    _git(["cat-file", "-e", f"{sha}^{{commit}}"])
    ref = known_good_ref_name(wiring)
    if not ref:
        raise ValueError("self_modify.known_good_ref is empty")
    before = resolve_known_good(wiring)
    _git(["update-ref", ref, sha])
    payload = {
        "schema": "endgame-ai.known-good.v1",
        "ref": ref,
        "previous": before,
        "commit": sha,
        "source": source,
        "updated_at": time.time(),
        "updated_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    }
    (ROOT / "runtime_known_good_commit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def hot_swap_to_known_good(
    wiring: dict[str, Any],
    *,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    known_good = resolve_known_good(wiring)
    sha = str(known_good.get("commit") or "").strip()
    if not sha:
        return {"hot_swapped": False, "reason": "no_known_good_commit", "known_good": known_good}
    if paths:
        targets = [str(p).replace("\\", "/") for p in paths if str(p).strip()]
    else:
        tracked = [line.split("\t", 1)[-1].strip() for line in _git(["ls-files"]).stdout.splitlines() if line.strip()]
        targets = sorted(
            p for p in tracked
            if p.endswith(tuple(EVOLVABLE_SUFFIXES)) or p in EVOLVABLE_NAMES
        )
    if not targets:
        return {"hot_swapped": False, "reason": "no_targets", "commit": sha, "known_good": known_good}
    checkout_targets: list[str] = []
    missing_in_known_good: list[str] = []
    for target in targets:
        exists = _git(["cat-file", "-e", f"{sha}:{target}"], check=False).returncode == 0
        if exists:
            checkout_targets.append(target)
        else:
            missing_in_known_good.append(target)
    if not checkout_targets:
        return {
            "hot_swapped": False,
            "reason": "no_targets_in_known_good",
            "commit": sha,
            "known_good": known_good,
            "missing_in_known_good": missing_in_known_good,
        }
    _git(["checkout", sha, "--", *checkout_targets])
    result: dict[str, Any] = {
        "hot_swapped": True,
        "commit": sha,
        "known_good": known_good,
        "paths": checkout_targets,
    }
    if missing_in_known_good:
        result["missing_in_known_good"] = missing_in_known_good
    return result


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
    cfg = wiring.get("self_modify", {}).get("git", {})
    remote = str(cfg.get("remote") or "origin")
    branch = git_current_branch()
    remote_url = _remote_url(remote)
    return {
        "context_mode": wiring.get("self_modify", {}).get("context_mode", "checked_out_branch"),
        "branch": branch,
        "current_commit": git_head_sha(),
        "known_good": resolve_known_good(wiring),
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
    commit = git_head_sha()
    known_good = update_known_good_ref(wiring, commit, source="commit_self_evolution")
    pushed = False
    known_good_ref_pushed = False
    git_cfg = wiring.get("self_modify", {}).get("git", {})
    if bool(git_cfg.get("push_after_commit", False)):
        remote = str(git_cfg.get("remote") or "origin")
        _git(["push", remote, branch])
        _git(["push", remote, f"{known_good['ref']}:{known_good['ref']}"])
        pushed = True
        known_good_ref_pushed = True
    return {
        "committed": True,
        "branch": branch,
        "commit": commit,
        "known_good": known_good,
        "changed_files": changed_files,
        "pushed": pushed,
        "known_good_ref_pushed": known_good_ref_pushed,
        "status": git_worktree_status(),
    }


def save_wiring(wiring: dict[str, Any]) -> None:
    brain.atomic_write_json(ROOT / "wiring.json", wiring)


def wiring_limit(name: str, default: int, wiring: dict[str, Any]) -> int:
    return wiring.get("limits", {}).get(name, default)


def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def _node_center(node: dict[str, Any]) -> tuple[int, int]:
    if node.get("px") is not None and node.get("py") is not None:
        return int(node.get("px") or 0), int(node.get("py") or 0)
    rect_val = node.get("rect")
    rect: dict[str, Any] = rect_val if isinstance(rect_val, dict) else {}
    left = int(rect.get("left", 0) or 0)
    right = int(rect.get("right", left) or left)
    top = int(rect.get("top", 0) or 0)
    bottom = int(rect.get("bottom", top) or top)
    return left + max(0, right - left) // 2, top + max(0, bottom - top) // 2


def build_capability_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    d = _get_desktop_instance()
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    fresh_observation = state.get("fresh_observation") or brain.last_fresh_observation() or bus.observation_brief(state)
    action_index = _action_index(state)
    action_events: list[dict[str, Any]] = []
    deadline_at = state.get("deadline_at")
    last = {
        "error": state.get("last_error"),
        "result": state.get("last_result", ""),
        "action": state.get("last_action", {}),
        "verification": state.get("last_verification", {}),
        "reflection": state.get("last_reflection", {}),
    }

    def _assert_duration_open(action: str) -> None:
        if deadline_at is None:
            return
        try:
            deadline = float(deadline_at)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid deadline_at in state: {deadline_at!r}") from exc
        now = time.time()
        if now >= deadline:
            raise RuntimeError(
                f"duration deadline expired before body action {action}: late_by_s={round(now - deadline, 3)}"
            )

    def _record_action(result: Any) -> Any:
        event = dict(result) if isinstance(result, dict) else {"ok": True, "value": result}
        event.setdefault("ok", True)
        event["event_index"] = len(action_events)
        event["recorded_at"] = time.time()
        action_events.append(event)
        if event.get("ok") is not True:
            raise RuntimeError(f"body action failed: {event}")
        return result

    def _require_node(node_id: str) -> dict[str, Any]:
        node = action_index.get(str(node_id))
        if not isinstance(node, dict):
            raise RuntimeError(f"node id is not actionable in the latest observation: {node_id}")
        return dict(node)

    def click(x: int, y: int, hwnd: int = 0) -> dict[str, Any]:
        _assert_duration_open("click")
        return _record_action(d.click(int(x), int(y), int(hwnd or 0)))

    def type_text(text: str) -> dict[str, Any]:
        _assert_duration_open("type_text")
        return _record_action(d.type_text(str(text)))

    def press_key(key: str) -> dict[str, Any]:
        _assert_duration_open("press_key")
        return _record_action(d.press_key(str(key)))

    def hotkey(*keys: Any) -> dict[str, Any]:
        _assert_duration_open("hotkey")
        return _record_action(d.hotkey(*keys))

    def scroll(x: int, y: int, amount: int, hwnd: int = 0) -> dict[str, Any]:
        _assert_duration_open("scroll")
        return _record_action(d.scroll(int(x), int(y), int(amount), int(hwnd or 0)))
    
    def action_nodes(action: str | None = None) -> list[dict[str, Any]]:
        nodes = []
        for node in action_index.values():
            if not isinstance(node, dict):
                continue
            node_action = node.get("action")
            if node_action and (action is None or node_action == action):
                nodes.append(dict(node))
        return nodes

    def node_by_id(node_id: str) -> dict[str, Any]:
        return _require_node(node_id)

    def click_node(node_id: str) -> dict[str, Any]:
        _assert_duration_open("click_node")
        node = _require_node(node_id)
        x, y = _node_center(node)
        click_res = d.click(x, y, int(node.get("hwnd") or 0))
        return _record_action({"ok": bool(click_res.get("ok", True)), "action": "click_node", "node_id": node_id, "click": click_res})

    def read_node(node_id: str) -> dict[str, Any]:
        _assert_duration_open("read_node")
        node = _require_node(node_id)
        text = node.get("name") or node.get("text_full") or node.get("value") or ""
        return _record_action({"ok": True, "action": "read_node", "node_id": node_id, "text": text})

    def scroll_node(node_id: str, amount: int = -3) -> dict[str, Any]:
        _assert_duration_open("scroll_node")
        node = _require_node(node_id)
        x, y = _node_center(node)
        return _record_action(d.scroll(x, y, int(amount), int(node.get("hwnd") or 0)))

    def open_url(browser: str, url: str) -> dict[str, Any]:
        _assert_duration_open("open_url")
        return _record_action(d.open_url(str(browser), str(url)))

    class _PyAutoGuiCompat:

        def click(self, x: int | None = None, y: int | None = None, clicks: int = 1, interval: float = 0.0, **kwargs: Any) -> Any:
            if x is None or y is None:
                raise RuntimeError("pyautogui.click requires explicit x and y")
            result = None
            for _ in range(max(1, int(clicks or 1))):
                result = click(int(x), int(y), int(kwargs.get("hwnd") or 0))
                if interval:
                    time.sleep(float(interval))
            return result

        def write(self, text: str, interval: float = 0.0) -> Any:
            if interval:
                for ch in str(text):
                    type_text(ch)
                    time.sleep(float(interval))
                return _record_action({"ok": True, "action": "pyautogui.write", "chars": len(str(text))})
            return type_text(str(text))

        typewrite = write

        def press(self, key: str, presses: int = 1, interval: float = 0.0) -> Any:
            result = None
            for _ in range(max(1, int(presses or 1))):
                result = press_key(str(key))
                if interval:
                    time.sleep(float(interval))
            return result

        def hotkey(self, *keys: str) -> Any:
            if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
                keys = tuple(keys[0])
            return hotkey(list(keys))

        def scroll(self, clicks: int, x: int | None = None, y: int | None = None, **kwargs: Any) -> Any:
            if x is None or y is None:
                return scroll(0, 0, int(clicks), int(kwargs.get("hwnd") or 0))
            return scroll(int(x), int(y), int(clicks), int(kwargs.get("hwnd") or 0))

        def sleep(self, seconds: float) -> None:
            time.sleep(float(seconds))

    pyautogui = _PyAutoGuiCompat()
    pag = pyautogui
    
    return {
        "observe_screen": d.observe_screen,
        "last_desktop_tree": d.last_desktop_tree,
        "action_nodes": action_nodes,
        "node_by_id": node_by_id,
        
        "click": click,
        "click_node": click_node,
        "read_node": read_node,
        "type_text": type_text,
        "press_key": press_key,
        "hotkey": hotkey,
        "scroll": scroll,
        "scroll_node": scroll_node,
        "open_url": open_url,
        "pyautogui": pyautogui,
        "pag": pag,
        
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
        
        "wiring_limit": wiring_limit,
        "repo_root": str(ROOT),
        "python_executable": sys.executable,
        "topology_summary": topology_summary(wiring),
        "topology_mermaid": topology_mermaid(wiring),
        
        "state": state,
        "wiring": wiring,
        "goal": goal,
        "last": last,
        "fresh_observation": fresh_observation,
        "desktop_tree": state.get("desktop_tree", {}),
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "action_index": action_index,
        "observation_artifact": state.get("observation_artifact", {}),
        "observed_at": state.get("observed_at"),
        "fresh_scan": state.get("fresh_scan", False),
        "action_events": action_events,
        "_action_events": action_events,
    }
