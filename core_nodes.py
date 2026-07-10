import io
import copy
import ctypes
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import types
import tokenize
from typing import Any

import core_brain as brain
import core_bus as bus
import core_wiring as wiring
import check_topology

ROOT = pathlib.Path(__file__).parent.resolve()


def _patch_data(parsed: dict[str, Any]) -> dict[str, Any]:
    data = parsed["data"]
    if not isinstance(data, dict):
        raise ValueError("self_modify patch data must be an object")
    return data


def _thread_id() -> int:
    return threading.get_ident()


def _evolution_target(raw_path: str, w: dict[str, Any] | None = None) -> tuple[pathlib.Path, str]:
    rel = str(raw_path).replace("\\", "/").strip().lstrip("/")
    if not rel:
        raise ValueError("self_modify path is empty")
    requested = pathlib.Path(rel)
    path = (ROOT / requested).resolve() if not requested.is_absolute() else requested.resolve()
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"git evolution path must stay under repository root: {raw_path}") from exc
    if w is not None and not _evolvable_rel(w, rel):
        raise ValueError(f"git evolution path is outside wiring.self_modify.evolvable: {rel}")
    return path, rel


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
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{_thread_id()}")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    wiring.replace_with_retry(tmp, path)


def _apply_wiring_ops(w: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(w)
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError(f"wiring_patch must be object: {patch!r}")
        op = patch["op"]
        dotted = str(patch["path"])
        if not dotted:
            raise ValueError("wiring_patch missing path")
        parts = dotted.split(".")
        cur = patched
        for part in parts[:-1]:
            cur = cur[part]
            if not isinstance(cur, dict):
                raise ValueError(f"wiring_patch parent is not object: {dotted}")
        if op == "set":
            cur[parts[-1]] = patch["value"]
        elif op == "delete":
            del cur[parts[-1]]
        else:
            raise ValueError(f"unknown wiring_patch op: {op}")
    json.dumps(patched, ensure_ascii=False, default=str)
    return patched


def _activation_bucket(rel: str, w: dict[str, Any]) -> str:
    activation = w["self_modify"]["evolvable"]["activation"]
    if rel in set(activation["immediate"]):
        return "immediate"
    if rel in set(activation["next_run"]):
        return "next_run"
    return "supporting"


def _evolvable_source(w: dict[str, Any]) -> dict[str, Any]:
    return w["self_modify"]["evolvable"]


def _evolvable_rel(w: dict[str, Any], rel: str) -> bool:
    cfg = _evolvable_source(w)
    name = pathlib.PurePosixPath(rel.replace("\\", "/")).name
    return name in set(cfg["names"]) or pathlib.PurePosixPath(rel).suffix in set(cfg["suffixes"])


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
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
    cp = _git(["rev-parse", "--verify", ref], check=False) if ref else None
    if cp is not None and cp.returncode == 0 and cp.stdout.strip():
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
    (ROOT / "runtime_known_good_commit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def hot_swap_to_known_good(w: dict[str, Any], *, paths: list[str] | None = None) -> dict[str, Any]:
    known_good = resolve_known_good(w)
    sha = str(known_good.get("commit") or "").strip()
    if not sha:
        return {"hot_swapped": False, "reason": "no_known_good_commit", "known_good": known_good}
    targets = [str(p).replace("\\", "/") for p in paths if str(p).strip()] if paths else sorted(
        line.split("\t", 1)[-1].strip()
        for line in _git(["ls-files"]).stdout.splitlines()
        if line.strip() and _evolvable_rel(w, line.strip())
    )
    checkout_targets, missing = [], []
    for target in targets:
        (checkout_targets if _git(["cat-file", "-e", f"{sha}:{target}"], check=False).returncode == 0 else missing).append(target)
    if not checkout_targets:
        return {"hot_swapped": False, "reason": "no_targets_in_known_good", "commit": sha, "known_good": known_good, "missing_in_known_good": missing}
    _git(["checkout", sha, "--", *checkout_targets])
    result: dict[str, Any] = {"hot_swapped": True, "commit": sha, "known_good": known_good, "paths": checkout_targets}
    if missing:
        result["missing_in_known_good"] = missing
    return result


def _remote_url(remote: str) -> str:
    cp = _git(["remote", "get-url", remote], check=False)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _github_branch_url(remote_url: str, branch: str) -> str:
    url = remote_url.strip()
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
    results: list[dict[str, Any]] = []
    default_timeout = w["self_modify"]["execution"].get("timeout_s")
    for item in commands:
        if isinstance(item, dict):
            command = item.get("command")
            shell = bool(item.get("shell", isinstance(command, str)))
            timeout_s = item.get("timeout_s", default_timeout)
        else:
            command, shell, timeout_s = item, isinstance(item, str), default_timeout
        if not isinstance(command, (str, list)) or not command:
            raise ValueError(f"invalid self_modify command: {item!r}")
        cp = subprocess.run(command, cwd=ROOT, shell=shell, capture_output=True, text=True, timeout=float(timeout_s) if timeout_s is not None else None)
        result = {"command": command, "shell": shell, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}
        results.append(result)
        if cp.returncode != 0:
            raise RuntimeError(f"self_modify command failed: {result}")
    return results


def _snapshot_paths(paths: list[pathlib.Path]) -> dict[pathlib.Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in dict.fromkeys(paths)}


def _restore_snapshots(snapshots: dict[pathlib.Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.rollback.{os.getpid()}.{_thread_id()}")
            tmp.write_bytes(content)
            wiring.replace_with_retry(tmp, path)


def _file_write(item: dict[str, Any], w: dict[str, Any]) -> tuple[pathlib.Path, str, str]:
    path, rel = _evolution_target(str(item["path"]), w)
    return path, rel, _validate_content(path, rel, item["content"])


def _semantic_noop(path: pathlib.Path, content: str) -> bool:
    if not path.exists():
        return False
    current = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        ignored = {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
        tokens = lambda text: [(token.type, token.string) for token in tokenize.generate_tokens(io.StringIO(text).readline) if token.type not in ignored]
        return tokens(current) == tokens(content)
    if path.suffix == ".json":
        return json.loads(current) == json.loads(content)
    return current == content


def apply_evolution_patch(w: dict[str, Any], parsed: dict[str, Any]) -> tuple[str, Any]:
    data = _patch_data(parsed)
    read_files = {str(path).replace("\\", "/").strip().lstrip("/") for path in data["read_files"]}
    wiring_patches = list(data["wiring_patches"])
    patched_wiring = _apply_wiring_ops(w, wiring_patches)
    if patched_wiring == w:
        wiring_patches = []
    if wiring_patches:
        wiring.validate_wiring(patched_wiring)
        problems = check_topology.coherence_problems(patched_wiring)
        if problems:
            raise ValueError(f"wiring_patch would make the organism incoherent: {problems}")
    writes = [write for write in (_file_write(item, w) for item in data["file_writes"]) if not _semantic_noop(write[0], write[2])]
    deletes = [_evolution_target(str(path), w) for path in data["file_deletes"]]
    if not writes and not deletes and not wiring_patches:
        raise ValueError("self_modify patch has no semantic change")
    missing_reads = [rel for path, rel, _ in writes if path.exists() and rel not in read_files]
    missing_reads += [rel for path, rel in deletes if path.exists() and rel not in read_files]
    if wiring_patches and "wiring.json" not in read_files:
        missing_reads.append("wiring.json")
    if missing_reads:
        raise ValueError(f"self_modify patch must declare read_files for touched existing files: {sorted(set(missing_reads))}")
    touched = [path for path, _, _ in writes] + [path for path, _ in deletes] + ([ROOT / "wiring.json"] if wiring_patches else [])
    snapshots = _snapshot_paths(touched)
    rollback = bool(w["self_modify"]["execution"]["rollback_on_failure"])
    try:
        for path, _, content in writes:
            _atomic_write_text(path, content)
        for path, _ in deletes:
            path.unlink()
        if wiring_patches:
            w.clear()
            w.update(patched_wiring)
            save_wiring(w)
        for path, rel, _ in writes:
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), rel, "exec")
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
        wiring.validate_wiring(w)
        problems = check_topology.coherence_problems(w)
        if problems:
            raise ValueError(f"self_modify result is incoherent: {problems}")
        for source in ROOT.glob("*.py"):
            compile(source.read_text(encoding="utf-8"), source.name, "exec")
        command_results = _run_evolution_commands(list(data["commands"]), w)
    except Exception:
        if rollback:
            _restore_snapshots(snapshots)
            if wiring_patches:
                w.clear()
                w.update(wiring.load_json(ROOT / "wiring.json"))
        raise
    changed = [rel for _, rel, _ in writes] + [rel for _, rel in deletes]
    activation = {"immediate": [], "next_run": [], "supporting": []}
    for rel in changed + (["wiring.json"] if wiring_patches else []):
        activation[_activation_bucket(rel, w)].append(rel)
    return "set", {"wiring_patches": len(wiring_patches), "file_writes": len(writes), "file_deletes": len(deletes), "commands": command_results, "rollback_on_failure": rollback, "changed_files": changed, "activation": activation}


def commit_self_evolution(
    w: dict[str, Any],
    applied: dict[str, Any],
    patch_data: dict[str, Any],
    *,
    advance_known_good: bool = True,
) -> dict[str, Any]:
    changed_files = list(applied.get("changed_files") or [])
    if applied.get("wiring_patches"):
        changed_files.append("wiring.json")
    changed_files = sorted({str(path).replace("\\", "/") for path in changed_files if str(path).strip()})
    if not changed_files:
        return {"committed": False, "reason": "no_changed_files", "branch": git_current_branch(), "commit": git_head_sha()}
    _git(["add", "-A", "-f", "--", *changed_files])
    if not git_worktree_status():
        return {
            "committed": False,
            "reason": "no_git_changes",
            "branch": git_current_branch(),
            "commit": git_head_sha(),
            "changed_files": changed_files,
        }
    title = "Self-modify: " + str(patch_data.get("summary") or "validated self evolution").replace("\n", " ")[:60]
    body = json.dumps(
        {
            "branch": git_current_branch(),
            "changed_files": changed_files,
            "read_files": list(patch_data.get("read_files") or []),
            "rationale": str(patch_data.get("rationale") or "").strip(),
            "expected_validation": patch_data.get("expected_validation"),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    _git(["commit", "-m", title, "-m", body])
    branch, commit = git_current_branch(), git_head_sha()
    known_good = (
        update_known_good_ref(w, commit, source="commit_self_evolution")
        if advance_known_good
        else resolve_known_good(w)
    )
    pushed = known_good_ref_pushed = False
    if bool(w["self_modify"]["git"]["push_after_commit"]):
        remote = str(w["self_modify"]["git"]["remote"])
        _git(["push", remote, branch])
        pushed = True
        if advance_known_good:
            _git(["push", remote, f"{known_good['ref']}:{known_good['ref']}"])
            known_good_ref_pushed = True
    return {
        "committed": True,
        "branch": branch,
        "commit": commit,
        "known_good": known_good,
        "known_good_advanced": advance_known_good,
        "changed_files": changed_files,
        "pushed": pushed,
        "known_good_ref_pushed": known_good_ref_pushed,
        "status": git_worktree_status(),
    }


def accept_self_evolution(w: dict[str, Any], commit: str, *, source: str) -> dict[str, Any]:
    sha = str(commit or "").strip()
    if not sha:
        raise ValueError("cannot behaviorally accept self evolution without a commit")
    _git(["cat-file", "-e", f"{sha}^{{commit}}"])
    known_good = update_known_good_ref(w, sha, source=source)
    pushed = False
    if bool(w["self_modify"]["git"]["push_after_commit"]):
        remote = str(w["self_modify"]["git"]["remote"])
        _git(["push", remote, f"{known_good['ref']}:{known_good['ref']}"])
        pushed = True
    return {
        "accepted": True,
        "commit": sha,
        "known_good": known_good,
        "known_good_ref_pushed": pushed,
    }


def save_wiring(w: dict[str, Any]) -> None:
    wiring.atomic_write_json(ROOT / "wiring.json", w)


def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def _node_center(node: dict[str, Any]) -> tuple[int, int]:
    if node.get("px") is not None and node.get("py") is not None:
        return int(node.get("px") or 0), int(node.get("py") or 0)
    rect = node.get("rect") if isinstance(node.get("rect"), dict) else {}
    left, top = int(rect.get("left", 0) or 0), int(rect.get("top", 0) or 0)
    right, bottom = int(rect.get("right", left) or left), int(rect.get("bottom", top) or top)
    return left + max(0, right - left) // 2, top + max(0, bottom - top) // 2


def capability_manifest(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    st = (ctx or {}).get("state", {}) if isinstance(ctx, dict) else {}
    w = (ctx or {}).get("wiring", {}) if isinstance(ctx, dict) else {}
    manifest = copy.deepcopy(w["capabilities"])
    transport, cfg = wiring.get_transport_config(w)
    manifest["configured_model"] = {"transport": transport, "model": cfg.get("model")}
    manifest["deadline_at"] = st.get("deadline_at")
    manifest["repo_root"] = str(ROOT)
    instance = (ctx or {}).get("node_instance") if isinstance(ctx, dict) else None
    if instance is not None:
        manifest["active_faculty"] = {"name": instance, **manifest["faculties"][instance]}
    return manifest


def build_capability_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    import core_desktop as desktop
    d = desktop.get_desktop()
    state = ctx.get("state", {})
    w = ctx.get("wiring", {})
    action_index = _action_index(state)
    action_events: list[dict[str, Any]] = []
    deadline_at = state.get("deadline_at")

    def _assert_duration_open(action: str) -> None:
        if deadline_at is not None:
            deadline = float(deadline_at)
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

    def _guarded(name: str, fn):
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _assert_duration_open(name)
            return _record_action(fn(*args, **kwargs))
        return wrapper

    click = _guarded("click", lambda x, y, hwnd=0: d.click(int(x), int(y), int(hwnd or 0)))
    type_text = _guarded("type_text", lambda text: d.type_text(str(text)))
    press_key = _guarded("press_key", lambda key: d.press_key(str(key)))
    hotkey = _guarded("hotkey", lambda *keys: d.hotkey(*keys))
    scroll = _guarded("scroll", lambda x, y, amount, hwnd=0: d.scroll(int(x), int(y), int(amount), int(hwnd or 0)))
    open_url = _guarded("open_url", lambda browser, url: d.open_url(str(browser), str(url)))

    def action_nodes(action: str | None = None) -> list[dict[str, Any]]:
        return [dict(node) for node in action_index.values() if isinstance(node, dict) and node.get("action") and (action is None or node.get("action") == action)]

    def node_by_id(node_id: str) -> dict[str, Any]:
        return _require_node(node_id)

    def click_node(node_id: str) -> dict[str, Any]:
        _assert_duration_open("click_node")
        node = _require_node(node_id)
        x, y = _node_center(node)
        res = d.click(x, y, int(node.get("hwnd") or 0))
        return _record_action({"ok": bool(res.get("ok", True)), "action": "click_node", "node_id": node_id, "click": res})

    def read_node(node_id: str) -> dict[str, Any]:
        _assert_duration_open("read_node")
        node = _require_node(node_id)
        return _record_action({"ok": True, "action": "read_node", "node_id": node_id, "text": node.get("name") or node.get("text_full") or node.get("value") or ""})

    def replace_node(node_id: str, text: str) -> dict[str, Any]:
        _assert_duration_open("replace_node")
        node = _require_node(node_id)
        if node["action"] != "write":
            raise RuntimeError(f"replace_node requires a write-capable node, got {node['action']!r}: {node_id}")
        x, y = _node_center(node)
        click_result = d.click(x, y, int(node.get("hwnd") or 0))
        time.sleep(0.15)
        select_result = d.hotkey("ctrl", "a")
        type_result = d.type_text(str(text))
        return _record_action({"ok": all(bool(item.get("ok")) for item in (click_result, select_result, type_result)), "action": "replace_node", "node_id": node_id, "text": str(text), "click": click_result, "select_all": select_result, "type": type_result})

    def scroll_node(node_id: str, amount: int = -3) -> dict[str, Any]:
        _assert_duration_open("scroll_node")
        node = _require_node(node_id)
        x, y = _node_center(node)
        return _record_action(d.scroll(x, y, int(amount), int(node.get("hwnd") or 0)))

    def _base_hover_cache_config() -> dict[str, Any]:
        observe_cfg = w["observe_config"]
        return copy.deepcopy(observe_cfg["hover_cache"])

    def observe_with_config(hover_cache_config: dict[str, Any] | None = None) -> dict[str, Any]:
        _assert_duration_open("observe_with_config")
        cfg = _base_hover_cache_config()
        if hover_cache_config:
            if not isinstance(hover_cache_config, dict):
                raise RuntimeError("observe_with_config requires a dict hover_cache_config")
            cfg.update(copy.deepcopy(hover_cache_config))
        obs = d.observe({"hover_cache": cfg})
        return _record_action({"ok": True, "action": "observe_with_config", "desktop_tree_text": obs.get("desktop_tree_text", ""), "screen": (obs.get("observation_artifact") or {}).get("screen", {}), "scan_stats": (obs.get("observation_artifact") or {}).get("scan_stats", {}), "rendered_node_count": obs.get("rendered_node_count"), "max_llm_nodes": obs.get("max_llm_nodes"), "llm_node_limit_hit": obs.get("llm_node_limit_hit")})

    def observe_area(left: int, top: int, right: int, bottom: int, max_llm_nodes: int | None = None, max_depth: int | None = None, step_px: int | None = None) -> dict[str, Any]:
        _assert_duration_open("observe_area")
        cfg = _base_hover_cache_config()
        scan = dict(cfg["scan"])
        scan["area"] = {"left": int(left), "top": int(top), "right": int(right), "bottom": int(bottom)}
        if step_px is not None:
            scan["step_px"] = int(step_px)
        cfg["scan"] = scan
        filt = dict(cfg["filter"])
        if max_llm_nodes is not None:
            filt["max_llm_nodes"] = int(max_llm_nodes)
        if max_depth is not None:
            filt["max_depth"] = int(max_depth)
        cfg["filter"] = filt
        return observe_with_config(cfg)

    def consult_model(prompt: str, max_output_tokens: int = 800) -> dict[str, Any]:
        """Consult the configured model through the brain layer and record exact evidence."""
        _assert_duration_open("consult_model")
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        limit = int(max_output_tokens)
        if limit <= 0:
            raise RuntimeError("consult_model max_output_tokens must be positive")
        transport, cfg = wiring.get_transport_config(w)
        result = brain.call(
            [{"role": "user", "content": text}],
            w,
            request_config={
                "max_output_tokens": limit,
                "metadata": {"endgame_purpose": "external_consultation"},
                "plain_text": True,
            },
        )
        response = str(result["content"])
        return _record_action({
            "ok": True,
            "action": "consult_model",
            "transport": transport,
            "model": cfg.get("model"),
            "prompt_chars": len(text),
            "prompt_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
            "response": response,
            "response_chars": len(response),
            "response_sha256": __import__("hashlib").sha256(response.encode("utf-8")).hexdigest(),
        })

    # NEW: direct web research helpers for terminal faculty (recorded actions)
    def web_search(query: str, num_results: int = 10) -> dict[str, Any]:
        """Perform a web search and record the results as a capability action."""
        _assert_duration_open("web_search")
        q = str(query).strip()
        if not q:
            raise RuntimeError("web_search requires a non-empty query")
        n = max(1, min(30, int(num_results)))
        try:
            from tools import web_search as _web_search  # type: ignore
            results = _web_search(q, num_results=n)
        except Exception:
            # Fallback: use the organism's own web_search tool if available in the runtime
            results = __import__("__main__", fromlist=["web_search"]).web_search(q, num_results=n) if hasattr(__import__("__main__", fromlist=["web_search"]), "web_search") else []
        return _record_action({
            "ok": True,
            "action": "web_search",
            "query": q,
            "num_results": n,
            "results": results,
        })

    def open_page(url: str, start_line: int | None = None) -> dict[str, Any]:
        """Fetch page content and record it as a capability action."""
        _assert_duration_open("open_page")
        u = str(url).strip()
        if not u:
            raise RuntimeError("open_page requires a non-empty url")
        try:
            from tools import open_page as _open_page  # type: ignore
            content = _open_page(u, start_line=start_line)
        except Exception:
            content = ""
        return _record_action({
            "ok": True,
            "action": "open_page",
            "url": u,
            "start_line": start_line,
            "content": content,
        })

    last = {"error": state.get("last_error"), "result": state.get("last_result", ""), "action": state.get("last_action", {}), "verification": state.get("last_verification", {}), "reflection": state.get("last_reflection", {})}
    return {
        "action_nodes": action_nodes, "node_by_id": node_by_id, "click": click, "click_node": click_node, "read_node": read_node, "replace_node": replace_node,
        "type_text": type_text, "press_key": press_key, "hotkey": hotkey, "scroll": scroll,
        "scroll_node": scroll_node, "open_url": open_url, "observe_with_config": observe_with_config,
        "observe_area": observe_area, "subprocess": subprocess,
        "ctypes": ctypes, "os": os, "sys": sys, "json": json, "re": __import__("re"), "time": time,
        "pathlib": pathlib, "math": __import__("math"), "random": __import__("random"), "types": types,
        "capabilities": capability_manifest(ctx), "repo_root": str(ROOT),
        "python_executable": sys.executable, "topology_summary": wiring.topology_summary(w), "state": state, "wiring": w, "goal": ctx.get("goal", ""),
        "last": last, "observation": state.get("observation") or brain.last_observation() or bus.observation_brief(state),
        "desktop_tree": state.get("desktop_tree", {}), "desktop_tree_text": state.get("desktop_tree_text", ""),
        "action_index": action_index, "observation_artifact": state.get("observation_artifact", {}),
        "observed_at": state.get("observed_at"),
        "action_events": action_events, "_action_events": action_events,
        "consult_model": consult_model,
        "web_search": web_search,
        "open_page": open_page,
    }
