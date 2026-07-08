from __future__ import annotations

import copy
import ctypes
import json
import os
import pathlib
import subprocess
import sys
import time
import types
from typing import Any

import core_brain as brain
import core_bus as bus
import core_desktop as desktop
import core_wiring as wiring

ROOT = pathlib.Path(__file__).parent.resolve()

EVOLVABLE_SUFFIXES = {".py", ".json", ".md"}
EVOLVABLE_NAMES = {".gitattributes", ".gitignore", "LICENSE"}
CORE_FILES = {"core_brain.py", "core_desktop.py", "core_nodes.py", "core_organism.py", "core_stop_check.py"}


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
        raise ValueError(f"git evolution path must stay under repository root: {raw_path}") from exc
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


def _apply_wiring_ops(w: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(w)
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


def known_good_ref_name(w: dict[str, Any]) -> str:
    return str(w["self_modify"]["known_good_ref"]).strip()


def resolve_known_good(w: dict[str, Any]) -> dict[str, Any]:
    ref = known_good_ref_name(w)
    if ref:
        cp = _git(["rev-parse", "--verify", ref], check=False)
        if cp.returncode == 0 and cp.stdout.strip():
            return {"commit": cp.stdout.strip(), "source": "git_ref", "ref": ref}
    return {"commit": "", "source": "missing", "ref": ref}


def update_known_good_ref(w: dict[str, Any], commit: str, *, source: str) -> dict[str, Any]:
    sha = str(commit or "").strip()
    if not sha:
        raise ValueError("cannot update known-good ref without a commit")
    _git(["cat-file", "-e", f"{sha}^{{commit}}"])
    ref = known_good_ref_name(w)
    if not ref:
        raise ValueError("self_modify.known_good_ref is empty")
    before = resolve_known_good(w)
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
    w: dict[str, Any],
    *,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    known_good = resolve_known_good(w)
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


def prepare_self_evolution(w: dict[str, Any]) -> dict[str, Any]:
    cfg = w["self_modify"]["git"]
    remote = str(cfg["remote"])
    branch = git_current_branch()
    remote_url = _remote_url(remote)
    return {
        "context_mode": w["self_modify"]["context_mode"],
        "branch": branch,
        "current_commit": git_head_sha(),
        "known_good": resolve_known_good(w),
        "worktree_status": git_worktree_status(),
        "remote": remote,
        "remote_url": remote_url,
        "branch_url": _github_branch_url(remote_url, branch),
        "commit_target": "checked_out_branch",
        "push_after_commit": bool(cfg["push_after_commit"]),
    }


def _run_evolution_commands(commands: list[Any], w: dict[str, Any]) -> list[dict[str, Any]]:
    if not commands:
        return []
    cfg = w["self_modify"]["execution"]
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


def apply_evolution_patch(w: dict[str, Any], parsed: dict[str, Any]) -> tuple[str, Any]:
    data = _patch_data(parsed)
    read_files = _declared_read_files(data)
    wiring_patches = list(data.get("wiring_patches") or [])
    patched_wiring = _apply_wiring_ops(w, wiring_patches)

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
    rollback_on_failure = bool(w["self_modify"]["execution"]["rollback_on_failure"])

    try:
        for path, _, content in writes:
            _atomic_write_text(path, content)
        for path, _ in deletes:
            path.unlink(missing_ok=True)
        if wiring_patches:
            w.clear()
            w.update(patched_wiring)
            save_wiring(w)

        for path, rel, _ in writes:
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), rel, "exec")
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))

        command_results = _run_evolution_commands(list(data.get("commands") or []), w)
    except Exception:
        if rollback_on_failure:
            _restore_snapshots(snapshots)
            if wiring_patches:
                w.clear()
                w.update(brain.load_json(ROOT / "wiring.json"))
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


def commit_self_evolution(w: dict[str, Any], applied: dict[str, Any], patch_data: dict[str, Any]) -> dict[str, Any]:
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
    known_good = update_known_good_ref(w, commit, source="commit_self_evolution")
    pushed = False
    known_good_ref_pushed = False
    git_cfg = w["self_modify"]["git"]
    if bool(git_cfg["push_after_commit"]):
        remote = str(git_cfg["remote"])
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


def save_wiring(w: dict[str, Any]) -> None:
    brain.atomic_write_json(ROOT / "wiring.json", w)


def wiring_limit(name: str, default: int, w: dict[str, Any]) -> int:
    return w.get("limits", {}).get(name, default)


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


def capability_manifest(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    st = (ctx or {}).get("state", {}) if isinstance(ctx, dict) else {}
    return {
        "schema": "endgame-ai.execute-capabilities.v1",
        "capability_model": "GUI, Python, process, file, and module access are all first-class local powers.",
        "python": {
            "execution": "exec(code, ns) in the organism process",
            "modules": ["subprocess", "os", "sys", "json", "re", "time", "pathlib", "ctypes", "math", "random", "types"],
            "repo_root": str(ROOT),
        },
        "desktop_helpers": {
            "click": "click(x, y, hwnd=0)",
            "click_node": "click_node(node_id)",
            "read_node": "read_node(node_id)",
            "type_text": "type_text(text) types into current focus; it does not accept node_id",
            "press_key": "press_key(key)",
            "hotkey": "hotkey(*keys)",
            "scroll": "scroll(x, y, amount, hwnd=0)",
            "scroll_node": "scroll_node(node_id, amount=-3)",
            "action_nodes": "action_nodes(action=None)",
            "node_by_id": "node_by_id(node_id)",
            "observe_area": "observe_area(left, top, right, bottom, max_llm_nodes=None, max_depth=None, step_px=None) returns a focused fresh observation",
            "observe_with_config": "observe_with_config(hover_cache_config) returns a fresh observation using consumed observe_config.hover_cache knobs",
            "pyautogui": "small compatibility facade over the same helpers",
            "pag": "alias for pyautogui",
        },
        "browser_helpers": {"open_url": "open_url(browser, url)"},
        "observation": {
            "state_fields": ["fresh_observation", "desktop_tree_text", "action_index", "observation_artifact"],
            "focused": "observe_area(...) and observe_with_config(...)",
        },
        "signals": ["verify", "frame", "reflect"],
        "deadline_at": st.get("deadline_at"),
    }


def build_capability_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    d = desktop.get_desktop()
    state = ctx.get("state", {})
    w = ctx.get("wiring", {})
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
            raise RuntimeError(f"duration deadline expired before body action {action}: late_by_s={round(now - deadline, 3)}")

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
        nodes_list = []
        for node in action_index.values():
            if not isinstance(node, dict):
                continue
            node_action = node.get("action")
            if node_action and (action is None or node_action == action):
                nodes_list.append(dict(node))
        return nodes_list

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

    def _base_hover_cache_config() -> dict[str, Any]:
        observe_cfg = w.get("observe_config", {}) if isinstance(w, dict) else {}
        hover = observe_cfg.get("hover_cache", observe_cfg) if isinstance(observe_cfg, dict) else {}
        return copy.deepcopy(hover if isinstance(hover, dict) else {})

    def observe_with_config(hover_cache_config: dict[str, Any] | None = None) -> dict[str, Any]:
        _assert_duration_open("observe_with_config")
        cfg = _base_hover_cache_config()
        if hover_cache_config:
            if not isinstance(hover_cache_config, dict):
                raise RuntimeError("observe_with_config requires a dict hover_cache_config")
            cfg.update(copy.deepcopy(hover_cache_config))
        obs = d.observe({"hover_cache": cfg})
        return _record_action({
            "ok": True,
            "action": "observe_with_config",
            "desktop_tree_text": obs.get("desktop_tree_text", ""),
            "scan_stats": (obs.get("observation_artifact") or {}).get("scan_stats", {}),
            "rendered_node_count": obs.get("rendered_node_count"),
            "max_llm_nodes": obs.get("max_llm_nodes"),
            "llm_node_limit_hit": obs.get("llm_node_limit_hit"),
        })

    def observe_area(
        left: int, top: int, right: int, bottom: int,
        max_llm_nodes: int | None = None,
        max_depth: int | None = None,
        step_px: int | None = None,
    ) -> dict[str, Any]:
        _assert_duration_open("observe_area")
        cfg = _base_hover_cache_config()
        scan = dict(cfg.get("scan", {}))
        scan["area"] = {"left": int(left), "top": int(top), "right": int(right), "bottom": int(bottom)}
        if step_px is not None:
            scan["step_px"] = int(step_px)
        cfg["scan"] = scan
        filt = dict(cfg.get("filter", {}))
        if max_llm_nodes is not None:
            filt["max_llm_nodes"] = int(max_llm_nodes)
        if max_depth is not None:
            filt["max_depth"] = int(max_depth)
        cfg["filter"] = filt
        return observe_with_config(cfg)

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
        "observe_with_config": observe_with_config,
        "observe_area": observe_area,
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
        "capabilities": capability_manifest(ctx),
        "repo_root": str(ROOT),
        "python_executable": sys.executable,
        "topology_summary": wiring.topology_summary(w),
        "topology_mermaid": wiring.topology_mermaid(w),
        "state": state,
        "wiring": w,
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
