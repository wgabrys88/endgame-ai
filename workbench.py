"""workbench — live control/debug panel for endgame-ai.

Truth model:
  - state.json              current organism snapshot (live truth)
  - comms/runtime.ndjson    slim organism lifecycle events only
  - <timestamp>.txt         single forensic raw brain log (request/response wire bytes)
  - wiring.json             editable brain/config topology

Forensic raw logs are for inspection and derived usage stats — never live state.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any

import brain as brain_mod

ROOT = pathlib.Path(__file__).parent.resolve()
PORT = int(os.environ.get("ENDGAME_WORKBENCH_PORT", "8800"))
ROD_BRAIN_CALLS = 2
STATE_PATH = ROOT / "state.json"
WIRING_PATH = ROOT / "wiring.json"
GOAL_PATH = ROOT / "goal.json"
CONTROL_PATH = ROOT / "comms" / "control.json"
WORKBENCH_HTML = ROOT / "workbench.html"


# ─── file helpers ───────────────────────────────────────────────────────────

def _read_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: pathlib.Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}.{time.time_ns()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


# ─── organism control / stepper ─────────────────────────────────────────────

def _default_control() -> dict:
    return {"mode": "run", "step_requested": False, "updated_at": 0, "updated_by": "default"}


def _read_control() -> dict:
    data = _read_json(CONTROL_PATH, _default_control())
    if not isinstance(data, dict):
        data = _default_control()
    mode = data.get("mode")
    if mode not in ("run", "pause", "step"):
        data["mode"] = "run"
    data.setdefault("step_requested", False)
    data.setdefault("updated_at", 0)
    return data


def _write_control(patch: dict) -> dict:
    cur = _read_control()
    cur.update({k: v for k, v in patch.items() if k in {"mode", "step_requested", "updated_by"}})
    if cur.get("mode") not in ("run", "pause", "step"):
        cur["mode"] = "run"
    cur["updated_at"] = time.time()
    _write_json(CONTROL_PATH, cur)
    return cur


def _root_path(value: str | None, default: str) -> pathlib.Path:
    raw = os.path.expandvars(os.path.expanduser(str(value or default)))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def _stat(path: pathlib.Path) -> dict:
    try:
        st = path.stat()
        return {"exists": True, "path": str(path), "mtime": st.st_mtime, "age_s": max(0, time.time() - st.st_mtime), "size": st.st_size}
    except OSError:
        return {"exists": False, "path": str(path), "mtime": 0, "age_s": None, "size": 0}


def _tail_lines(path: pathlib.Path, max_lines: int = 200, max_bytes: int = 600_000) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(max(0, size - max_bytes))
                f.readline()  # drop partial first line
            raw = f.read()
    except OSError:
        return []
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines()[-max_lines:]


def _tail_ndjson(path: pathlib.Path, max_lines: int = 200, max_bytes: int = 600_000) -> list[dict]:
    rows: list[dict] = []
    for line in _tail_lines(path, max_lines=max_lines, max_bytes=max_bytes):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _model_cfg() -> dict:
    return _read_json(WIRING_PATH, {}).get("model", {})


def _runtime_path(model: dict | None = None) -> pathlib.Path:
    model = model or _model_cfg()
    return _root_path(model.get("runtime_log_path"), "comms/runtime.ndjson")


def _raw_log_paths(limit: int = 20) -> list[dict]:
    paths = sorted(ROOT.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in paths[:limit]:
        if p.name.lower() in ("readme.txt", "license.txt"):
            continue
        out.append({**_stat(p), "name": p.name})
    return out


def _active_raw_log(model: dict | None = None) -> pathlib.Path:
    model = model or _model_cfg()
    explicit = model.get("raw_log_path")
    if explicit:
        return _root_path(explicit, "")
    logs = _raw_log_paths(limit=1)
    if logs and logs[0].get("exists"):
        return ROOT / logs[0]["name"]
    return brain_mod.raw_log_path(model)


def _safe_comms_file(name: str) -> pathlib.Path | None:
    """Resolve a log file under comms/ only — blocks path traversal."""
    raw = (name or "").strip().replace("\\", "/")
    if not raw or ".." in raw or raw.startswith("/"):
        return None
    base = (ROOT / "comms").resolve()
    path = (ROOT / "comms" / raw).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return None
    return path if path.is_file() else None


def _log_inventory(model: dict | None = None) -> dict:
    """Log artifacts on disk from current and prior runs."""
    model = model or _model_cfg()
    runtime = _runtime_path(model)
    raw_logs = _raw_log_paths()
    prompts_dir = ROOT / "comms" / "cli_prompts"
    prompts = []
    if prompts_dir.is_dir():
        prompts = sorted(prompts_dir.glob("*.prompt.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    last_raw = raw_logs[0] if raw_logs else {}
    return {
        "runtime": {**_stat(runtime), "name": runtime.name},
        "raw_logs": raw_logs,
        "cli_prompts": [{**_stat(p), "name": p.name} for p in prompts[:10]],
        "last_run": {
            "raw_log": last_raw.get("name", ""),
            "raw_mtime": last_raw.get("mtime", 0),
            "runtime_age_s": _stat(runtime).get("age_s"),
            "runtime_size": _stat(runtime).get("size", 0),
        },
    }


def _read_log_tail(*, kind: str, file: str = "", tail: int = 200) -> dict:
    tail = max(1, min(int(tail or 200), 2000))
    model = _model_cfg()
    if kind == "runtime":
        path = _runtime_path(model)
    elif kind == "raw":
        if file:
            path = (ROOT / file).resolve()
            try:
                path.relative_to(ROOT.resolve())
            except ValueError:
                return {"ok": False, "error": f"raw log not found: {file!r}"}
        else:
            path = _active_raw_log(model)
    elif kind == "cli_prompt":
        path = _safe_comms_file(f"cli_prompts/{file}" if file and "/" not in file else file)
        if path is None:
            return {"ok": False, "error": f"cli prompt not found: {file!r}"}
    else:
        return {"ok": False, "error": f"unknown log kind: {kind!r}"}

    if not path.exists():
        return {"ok": False, "error": f"log file missing: {path}", "path": str(path)}

    if path.suffix == ".ndjson" or kind == "raw":
        rows = brain_mod.read_raw_log_tail(path, max_lines=tail, max_bytes=2_000_000) if kind == "raw" else _tail_ndjson(path, max_lines=tail, max_bytes=2_000_000)
        return {
            "ok": True,
            "kind": kind,
            "path": str(path),
            "format": "ndjson" if kind == "raw" else "ndjson",
            "lines": len(rows),
            "tail": rows,
            "stat": _stat(path),
        }

    lines = _tail_lines(path, max_lines=tail, max_bytes=2_000_000)
    return {
        "ok": True,
        "kind": kind,
        "path": str(path),
        "format": "text",
        "lines": len(lines),
        "tail": lines,
        "stat": _stat(path),
    }


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ─── usage / compact state projection ───────────────────────────────────────

def _usage_rows(limit: int = 20000) -> list[dict]:
    path = _active_raw_log()
    rows = brain_mod.read_raw_log_tail(path, max_lines=limit, max_bytes=4_000_000)
    return [r for r in rows if r.get("phase") == "response"]


def _usage_summary() -> dict:
    rows = _usage_rows()
    now = time.time()
    lt = time.localtime(now)
    month_start = time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1))
    buckets = {
        "24h": lambda ts: ts >= now - 86400,
        "30d": lambda ts: ts >= now - 30 * 86400,
        "month": lambda ts: ts >= month_start,
        "all": lambda ts: True,
    }
    out = {name: {} for name in buckets}
    for row in rows:
        ts = _num(row.get("ts"), 0)
        transport = str(row.get("transport") or "unknown")
        usage, model, elapsed = brain_mod.usage_from_raw_response(row)
        model = model or str(row.get("model") or "")
        key = f"{transport} | {model}".strip()
        usage = usage or {}
        prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
        total = usage.get("total_tokens", _num(prompt) + _num(completion))
        reasoning = 0
        for details_key in ("completion_tokens_details", "output_tokens_details"):
            d = usage.get(details_key)
            if isinstance(d, dict):
                reasoning += _num(d.get("reasoning_tokens"), 0)
        cost = None
        if usage.get("cost_in_usd_ticks") is not None:
            cost = _num(usage.get("cost_in_usd_ticks")) / 10_000_000_000
        for name, pred in buckets.items():
            if not pred(ts):
                continue
            cur = out[name].setdefault(key, {
                "transport": transport, "model": model, "calls": 0, "exact_calls": 0,
                "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
                "total_tokens": 0, "cost_usd": 0.0, "elapsed_s": 0.0, "notes": set(),
            })
            cur["calls"] += 1
            if usage:
                cur["exact_calls"] += 1
            cur["prompt_tokens"] += int(_num(prompt, 0))
            cur["completion_tokens"] += int(_num(completion, 0))
            cur["reasoning_tokens"] += int(reasoning)
            cur["total_tokens"] += int(_num(total, 0))
            cur["cost_usd"] += _num(cost, 0.0)
            cur["elapsed_s"] += _num(elapsed, 0.0)
    for bucket in out.values():
        for cur in bucket.values():
            cur["notes"] = sorted(cur["notes"])
    return {"path": str(_active_raw_log()), "rows": len(rows), "buckets": out, "limits": _model_cfg().get("usage_limits", {})}


def _compact_state(state: dict) -> dict:
    plan = state.get("plan") if isinstance(state.get("plan"), list) else []
    history = state.get("history") if isinstance(state.get("history"), list) else []
    chain = state.get("reasoning_chain") if isinstance(state.get("reasoning_chain"), list) else []
    return {
        "goal": state.get("goal", ""),
        "node": state.get("_node", ""),
        "active_node": state.get("_active_node", state.get("_node", "")),
        "phase": state.get("_phase", ""),
        "transport": state.get("_transport", ""),
        "state_seq": state.get("_state_seq", 0),
        "saved_at": state.get("_saved_at", 0),
        "saved_at_iso": state.get("_saved_at_iso", ""),
        "pid": state.get("_pid", ""),
        "plan": plan[:30],
        "step": state.get("step", 0),
        "current_step": state.get("current_step", {}),
        "plan_complete": bool(state.get("plan_complete")),
        "satisfied": bool(state.get("satisfied")),
        "last_error": state.get("last_error", ""),
        "last_outcome": state.get("last_outcome", ""),
        "last_actions": state.get("last_actions", []),
        "verify_evidence": state.get("verify_evidence", ""),
        "verify_reason": state.get("verify_reason", ""),
        "history": history[-30:],
        "narration": (state.get("_narration") if isinstance(state.get("_narration"), list) else [])[-80:],
        "reasoning_chain": [
            {
                "circuit": x.get("circuit", "") if isinstance(x, dict) else "",
                "ts": x.get("ts", 0) if isinstance(x, dict) else 0,
                "reasoning": str(x.get("reasoning", ""))[:800] if isinstance(x, dict) else "",
                "parsed": x.get("parsed") if isinstance(x, dict) else None,
            }
            for x in chain[-20:]
        ],
        "screen_summary": _screen_summary(state),
    }


def _screen_summary(state: dict) -> dict:
    meta = state.get("screen_meta") if isinstance(state.get("screen_meta"), dict) else {}
    probe = meta.get("probe") if isinstance(meta.get("probe"), dict) else {}
    return {
        "focused_title": meta.get("focused_title") or state.get("post_action_title", ""),
        "elements": len(meta.get("elements") or []),
        "windows": len(meta.get("windows") or []),
        "raw_screen_chars": len(str(state.get("screen") or "")),
        "probe": {k: probe.get(k) for k in ("raw_nodes", "classified_nodes", "primary_found", "hover_scan_found")},
    }


def _normalize_wiring(wiring: dict) -> dict:
    model = wiring.setdefault("model", {})
    openai = model.get("openai") if isinstance(model.get("openai"), dict) else {}
    params = openai.get("parameters") if isinstance(openai.get("parameters"), dict) else {}
    for key in ("host", "model", "timeout"):
        if key in openai:
            model[key] = openai[key]
    for key in ("temperature", "temperature_bump", "top_p", "top_k", "repeat_penalty", "presence_penalty", "frequency_penalty", "max_tokens", "thinking"):
        if key in params:
            model[key] = params[key]
    model.setdefault("runtime_log_path", "comms/runtime.ndjson")
    model.setdefault("log_raw", True)
    if isinstance(model.get("file_proxy"), dict):
        model["file_proxy"].setdefault("request_path", "comms/request.json")
        model["file_proxy"].setdefault("response_path", "comms/response.json")
    return wiring


def _status() -> dict:
    wiring = _read_json(WIRING_PATH, {})
    model = wiring.get("model", {}) if isinstance(wiring.get("model"), dict) else {}
    state = _read_json(STATE_PATH, {})
    state_stat = _stat(STATE_PATH)
    runtime_path = _runtime_path(model)
    raw_path = _active_raw_log(model)
    runtime_rows = _tail_ndjson(runtime_path, max_lines=200, max_bytes=800_000)
    last_runtime = runtime_rows[-1] if runtime_rows else {}
    now = time.time()
    state_age = state_stat["age_s"] if state_stat["age_s"] is not None else None
    runtime_stat = _stat(runtime_path)
    runtime_age = runtime_stat["age_s"] if runtime_stat["age_s"] is not None else None
    phase = str(state.get("_phase", "") or "")
    active = bool(phase not in ("rest", "stopped", "interrupted", "max_ticks", "") or (last_runtime.get("event") in ("node_start", "node_signal")))
    stale = bool(state_age is None or state_age > 8 and not active)
    return {
        "now": now,
        "now_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "state": _compact_state(state),
        "model": {
            "transport": model.get("transport", ""),
            "label": (model.get(model.get("transport", ""), {}) or {}).get("label", model.get("transport", "")) if isinstance(model.get(model.get("transport", ""), {}), dict) else model.get("transport", ""),
            "known_transports": [k for k in ("openai", "xai_responses", "grok_build_api", "opencode", "grok_build", "file_proxy", "browser_ai") if k in model or k in ("file_proxy", "browser_ai")],
        },
        "files": {
            "state": state_stat,
            "wiring": _stat(WIRING_PATH),
            "runtime": runtime_stat,
            "raw_log": _stat(raw_path),
            "inventory": _log_inventory(model),
        },
        "runtime": runtime_rows[-120:],
        "last_runtime_event": last_runtime,
        "health": {
            "active": active,
            "stale": stale,
            "state_age_s": state_age,
            "runtime_age_s": runtime_age,
            "message": _health_message(active, stale, state_age, runtime_age, last_runtime),
        },
        "usage": _usage_summary(),
        "control": _read_control(),
    }


def _health_message(active: bool, stale: bool, state_age: float | None, runtime_age: float | None, last_event: dict) -> str:
    if active:
        return f"live: {last_event.get('event', 'state')}"
    if stale:
        return f"stale: state age {state_age:.1f}s" if isinstance(state_age, (int, float)) else "stale: no state file"
    return "current"


# ─── provider diagnostics ──────────────────────────────────────────────────

def _resolve_exe(name: str) -> str | None:
    """Match brain.py resolution: absolute paths first, then PATH lookup."""
    import shutil
    expanded = os.path.expandvars(os.path.expanduser(str(name or ""))).strip()
    if not expanded:
        return None
    p = pathlib.Path(expanded)
    if p.is_absolute() and p.exists():
        return str(p)
    names = [expanded]
    if os.name == "nt" and not p.suffix:
        names += [expanded + ext for ext in (".exe", ".cmd", ".bat", ".ps1")]
    for n in names:
        hit = shutil.which(n)
        if hit:
            return hit
    return None


def _provider_stats(provider: str) -> dict:
    model = _model_cfg()
    if provider == "opencode":
        cfg = model.get("opencode") if isinstance(model.get("opencode"), dict) else {}
        exe = _resolve_exe(str(cfg.get("exe") or "opencode"))
        if not exe:
            return {"ok": False, "error": f"OpenCode executable not found ({cfg.get('exe') or 'opencode'}). Set model.opencode.exe in wiring.", "candidates": []}
        cmd = [exe, "stats", "--days", "30", "--models", "10"]
    elif provider == "grok_build":
        cfg = model.get("grok_build") if isinstance(model.get("grok_build"), dict) else {}
        exe = _resolve_exe(str(cfg.get("exe") or "grok"))
        if not exe:
            return {"ok": False, "error": f"Grok executable not found ({cfg.get('exe') or 'grok'}).", "candidates": []}
        cmd = [exe, "models"]
    elif provider == "openai":
        cfg = model.get("openai") if isinstance(model.get("openai"), dict) else {}
        host = str(cfg.get("host") or model.get("host") or "http://localhost:1234").rstrip("/")
        url = host + "/v1/models"
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = resp.read(4000).decode("utf-8", errors="replace")
            return {"ok": True, "host": host, "url": url, "stdout": body[:2000]}
        except Exception as e:
            return {"ok": False, "error": f"LM Studio / openai host unreachable at {url}: {e}", "host": host}
    elif provider in ("xai_responses", "grok_build_api"):
        key_name = "grok_build_api" if provider == "grok_build_api" else "xai_responses"
        cfg = model.get(key_name) if isinstance(model.get(key_name), dict) else {}
        env_name = str(cfg.get("api_key_env") or "XAI_API_KEY")
        key = os.environ.get(env_name, "")
        return {
            "ok": bool(key),
            "api_key_env": env_name,
            "key_present": bool(key),
            "host": cfg.get("host", "https://api.x.ai"),
            "endpoint_path": cfg.get("endpoint_path", "/v1/responses"),
            "model": cfg.get("model", ""),
            "error": None if key else f"env {env_name} is not set",
        }
    elif provider == "file_proxy":
        fp = model.get("file_proxy") if isinstance(model.get("file_proxy"), dict) else {}
        req = _root_path(fp.get("request_path"), "comms/request.json")
        resp = _root_path(fp.get("response_path"), "comms/response.json")
        return {"ok": True, "request_path": str(req), "response_path": str(resp), "request": _stat(req), "response": _stat(resp)}
    else:
        return {"ok": False, "error": f"no probe for provider {provider!r}"}
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=20)
    except Exception as e:
        return {"ok": False, "error": f"{provider} stats failed: {e}", "cmd": cmd}
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    err = (proc.stderr or b"").decode("utf-8", errors="replace")
    return {"ok": proc.returncode == 0, "stdout": out, "stderr": err, "returncode": proc.returncode, "cmd": cmd}


def _rod_seen_in_raw(entries: list[dict]) -> bool:
    for row in entries:
        if row.get("phase") != "request":
            continue
        if row.get("rod_feedback"):
            return True
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        body = raw.get("body")
        if isinstance(body, dict):
            messages = body.get("messages")
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict) and "ROD_REASONING_CONTENT" in str(msg.get("content", "")):
                        return True
            if "ROD_REASONING_CONTENT" in str(body.get("input", "")) or "ROD_REASONING_CONTENT" in str(body.get("user", "")):
                return True
        argv = raw.get("argv")
        if isinstance(argv, list) and any("ROD_REASONING_CONTENT" in str(x) for x in argv):
            return True
        if "ROD_REASONING_CONTENT" in str(raw.get("prompt", "")):
            return True
    return False


def _brain_test(transport: str) -> dict:
    model = dict(_model_cfg())
    model["transport"] = transport
    model.pop("brain_test_timeout_s", None)
    model["max_brain_calls"] = int(model.get("rod_brain_calls") or ROD_BRAIN_CALLS)
    if transport == "browser_ai":
        return {"ok": False, "transport": transport, "error": "browser_ai brain node is a fail-hard stub"}
    started = time.time()
    raw_before = brain_mod.read_raw_log_tail(_active_raw_log(model))
    before_seq = max((int(r.get("seq") or 0) for r in raw_before), default=0)
    system = (
        "ROD test assistant. Call 1: emit brief reasoning about the user task. "
        "Call 2: commit ONLY one JSON object with no markdown fences."
    )
    user = (
        f"Workbench falsification for transport {transport}. "
        'On the final call output exactly: '
        '{"record_type":"workbench_rod_test","ok":true,"transport":"' + transport + '"}'
    )
    brain = brain_mod.Brain(model)
    try:
        content, parsed, reasoning = brain.think(system, user, parse_retries=0)
        entries = [e for e in brain_mod.read_raw_log_tail(_active_raw_log(model)) if int(e.get("seq") or 0) > before_seq]
        t_entries = [e for e in entries if e.get("transport") == transport]
        counts = brain_mod.count_raw_phases(t_entries, transport=transport)
        requests = [e for e in t_entries if e.get("phase") == "request"]
        parsed_ok = bool(
            parsed
            and parsed.get("record_type") == "workbench_rod_test"
            and parsed.get("ok") is True
            and str(parsed.get("transport", transport)) == transport
        )
        budget = model["max_brain_calls"]
        ok = bool(
            parsed_ok
            and counts["request"] == budget
            and counts["response"] == budget
            and brain.call_count() == budget
            and bool((reasoning or "").strip())
            and _rod_seen_in_raw(requests)
        )
        return {
            "ok": ok,
            "transport": transport,
            "rod_calls": counts["request"],
            "rod_responses": counts["response"],
            "brain_calls": brain.call_count(),
            "max_brain_calls": budget,
            "rod_feedback_in_request": _rod_seen_in_raw(requests),
            "reasoning_chars": len(reasoning or ""),
            "parsed": parsed,
            "content_preview": (content or "")[:600],
            "elapsed_s": round(time.time() - started, 3),
            "raw_log": str(_active_raw_log(model)),
            "raw_entries": len(t_entries),
        }
    except Exception as e:
        entries = [e for e in brain_mod.read_raw_log_tail(_active_raw_log(model)) if int(e.get("seq") or 0) > before_seq]
        t_entries = [e for e in entries if e.get("transport") == transport]
        counts = brain_mod.count_raw_phases(t_entries, transport=transport)
        return {
            "ok": False,
            "transport": transport,
            "error": f"{type(e).__name__}: {e}",
            "rod_calls": counts["request"],
            "rod_responses": counts["response"],
            "brain_calls": brain.call_count(),
            "max_brain_calls": model.get("max_brain_calls"),
            "elapsed_s": round(time.time() - started, 3),
            "raw_log": str(_active_raw_log(model)),
        }


# ─── HTML ──────────────────────────────────────────────────────────────────

# ─── HTTP API + static single-file UI ───────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Browser-side AbortController / refresh closed the socket. This is not an
            # organism failure; keep the workbench server quiet and alive.
            return

    def log_message(self, *_a):
        pass

    def do_OPTIONS(self):
        return self._send(204, b"", "text/plain")

    def _body(self) -> str:
        n = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(n).decode("utf-8") if n else ""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html", "/workbench.html"):
            html = WORKBENCH_HTML.read_text(encoding="utf-8") if WORKBENCH_HTML.exists() else "<h1>workbench.html missing</h1>"
            return self._send(200, html, "text/html; charset=utf-8")
        if path == "/api/status":
            return self._send(200, json.dumps(_status(), ensure_ascii=False, default=str))
        if path == "/api/state/raw":
            return self._send(200, json.dumps(_read_json(STATE_PATH, {}), ensure_ascii=False, default=str))
        if path == "/api/wiring":
            return self._send(200, json.dumps(_read_json(WIRING_PATH, {}), ensure_ascii=False, default=str))
        if path == "/api/control":
            return self._send(200, json.dumps(_read_control(), ensure_ascii=False, default=str))
        if path == "/api/usage":
            return self._send(200, json.dumps(_usage_summary(), ensure_ascii=False, default=str))
        if path == "/api/provider_stats":
            qs = parse_qs(parsed.query)
            provider = (qs.get("provider") or [""])[0]
            return self._send(200, json.dumps(_provider_stats(provider), ensure_ascii=False, default=str))
        if path == "/api/proxy":
            model = _model_cfg()
            fp = model.get("file_proxy", {})
            req = _read_json(_root_path(fp.get("request_path"), "comms/request.json"), {})
            pending = bool(req) and req.get("status") == "pending"
            prompt = ""
            if pending:
                msgs = req.get("messages", [])
                prompt = "\n\n".join(f"[{m.get('role')}]\n{m.get('content','')}" for m in msgs)
            return self._send(200, json.dumps({"pending": pending, "id": req.get("id"), "prompt": prompt}, ensure_ascii=False))
        if path == "/api/logs":
            return self._send(200, json.dumps(_log_inventory(), ensure_ascii=False, default=str))
        if path == "/api/logs/tail" or path == "/api/logs/session":
            qs = parse_qs(parsed.query)
            kind = (qs.get("kind") or ["session" if path == "/api/logs/session" else "runtime"])[0]
            file = (qs.get("file") or [""])[0]
            tail = (qs.get("tail") or ["200"])[0]
            return self._send(200, json.dumps(_read_log_tail(kind=kind, file=file, tail=tail), ensure_ascii=False, default=str))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        body = self._body()
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/control":
            try:
                payload = json.loads(body or "{}")
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            return self._send(200, json.dumps(_write_control(payload), ensure_ascii=False, default=str))
        if path == "/api/respond":
            model = _model_cfg()
            fp = model.get("file_proxy", {})
            req = _read_json(_root_path(fp.get("request_path"), "comms/request.json"), {})
            resp_path = _root_path(fp.get("response_path"), "comms/response.json")
            _write_json(resp_path, {"id": req.get("id"), "content": body})
            return self._send(200, '{"ok":true}')
        if path == "/api/goal":
            _write_json(GOAL_PATH, {"goal": body})
            return self._send(200, '{"ok":true}')
        if path == "/api/wiring":
            try:
                wiring = json.loads(body or "{}")
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            wiring = _normalize_wiring(wiring)
            _write_json(WIRING_PATH, wiring)
            return self._send(200, '{"ok":true}')
        if path == "/api/brain_test":
            try:
                payload = json.loads(body or "{}")
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            transport = str(payload.get("transport") or _model_cfg().get("transport") or "opencode")
            return self._send(200, json.dumps(_brain_test(transport), ensure_ascii=False, default=str))
        return self._send(404, json.dumps({"error": "not found"}))


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"workbench API on http://127.0.0.1:{PORT}", flush=True)
    print(f"UI: open http://127.0.0.1:{PORT}/ or file:///{WORKBENCH_HTML.as_posix()}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
