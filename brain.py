"""brain — ROD cognition plus hot-swappable stateless brain nodes.

The organism still has one cognition contract: each decision is two stateless calls,
and the second call receives ROD_REASONING_CONTENT before committing a typed JSON
record. What changed here is the transport boundary: concrete brains are now plain
Python node files in live_brains/ seeded from seed_brains/. Selecting a brain is a
wiring change, not a Python branch edit.

Fail-hard invariant: the selected brain node either returns text/reasoning or raises.
There is no fallback transport and no silent substitution.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
BRAIN_SEED_DIR = ROOT / "seed_brains"
BRAIN_DIR = ROOT / "live_brains"
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

BRAIN_ALIASES = {
    "openai": "openai",
    "lm_studio": "openai",
    "chat_completions": "openai",
    "xai_responses": "xai_responses",
    "grok_build_api": "grok_build_api",
    "grok_build": "grok_build",
    "grok_build_cli": "grok_build",
    "opencode": "opencode",
    "file_proxy": "file_proxy",
    "file_brain": "file_proxy",
    "browser_ai": "browser_ai",
}

# ─── seed/live brain node files ─────────────────────────────────────────────

def ensure_brain_nodes() -> None:
    """Copy seed brain nodes into the mutable live dir on first use."""
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    if not any(BRAIN_DIR.glob("*.py")) and BRAIN_SEED_DIR.exists():
        for f in BRAIN_SEED_DIR.glob("*.py"):
            shutil.copy2(f, BRAIN_DIR / f.name)


def brain_node_path(transport: str) -> pathlib.Path:
    name = BRAIN_ALIASES.get(str(transport or "openai"), str(transport or "openai"))
    return BRAIN_DIR / f"{name}.py"


# ─── JSON / reasoning extraction ────────────────────────────────────────────

def extract_json_object(text: str):
    """Return the model's committed JSON record, or None."""
    if not text:
        return None
    text = text.strip()
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1].strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for block in reversed(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S | re.I)):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
    candidates: list[str] = []
    depth = 0
    in_str = esc = False
    start = -1
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(text[start:i + 1])
    for span in reversed(candidates):
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            continue
    return None


def reasoning_from(content: str, reasoning_content: str) -> str:
    if reasoning_content and reasoning_content.strip():
        return reasoning_content.strip()
    m = re.search(r"<think>(.*?)</think>", content or "", flags=re.S)
    if m:
        return m.group(1).strip()
    if "</think>" in (content or ""):
        return content.rsplit("</think>", 1)[0].strip()
    return (content or "").strip()


# ─── filesystem / logging helpers ───────────────────────────────────────────

def _root_path(value: str | None, default: str) -> pathlib.Path:
    raw = os.path.expandvars(os.path.expanduser(str(value or default)))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def _atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _append_ndjson(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _read_text_lossy(raw: bytes) -> str:
    if not raw:
        return ""
    enc = "utf-16-le" if b"\x00" in raw[:80] else "utf-8"
    return _ANSI_RE.sub("", raw.decode(enc, errors="replace")).strip()


def _truncate(s: str, limit: int = 12000) -> str:
    s = str(s or "")
    return s if len(s) <= limit else s[:limit] + f"\n…[truncated {len(s) - limit} chars]"


_RUNTIME_SEQ = 0
_RUNTIME_LOCK = threading.Lock()
_RAW_LOG_PATH: pathlib.Path | None = None
_RAW_SEQ = 0
_RAW_LOCK = threading.Lock()


def raw_log_path(cfg: dict | None = None) -> pathlib.Path:
    global _RAW_LOG_PATH
    cfg = cfg or {}
    if _RAW_LOG_PATH is None:
        explicit = cfg.get("raw_log_path")
        if explicit:
            _RAW_LOG_PATH = _root_path(explicit, "")
        else:
            stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime())
            _RAW_LOG_PATH = ROOT / f"{stamp}.txt"
        _RAW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not _RAW_LOG_PATH.exists():
            _RAW_LOG_PATH.write_text("", encoding="utf-8")
    return _RAW_LOG_PATH


def _next_raw_seq() -> int:
    global _RAW_SEQ
    with _RAW_LOCK:
        _RAW_SEQ += 1
        return _RAW_SEQ


def log_raw_entry(cfg: dict | None, entry: dict) -> None:
    cfg = cfg or {}
    if cfg.get("log_raw", True) is False:
        return
    try:
        row = dict(entry)
        row.setdefault("ts", time.time())
        row.setdefault("iso", time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()))
        _append_ndjson(raw_log_path(cfg), row)
    except Exception:
        pass


def count_raw_phases(entries: list[dict], *, transport: str | None = None) -> dict[str, int]:
    out = {"request": 0, "response": 0}
    for row in entries:
        if transport and row.get("transport") != transport:
            continue
        if row.get("phase") in out:
            out[row["phase"]] += 1
    return out


def read_raw_log_tail(path: pathlib.Path | None = None, *, max_lines: int = 5000,
                      max_bytes: int = 4_000_000) -> list[dict]:
    rows: list[dict] = []
    path = path or raw_log_path()
    if not path.exists():
        return rows
    for line in _tail_text_lines(path, max_lines=max_lines, max_bytes=max_bytes):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _tail_text_lines(path: pathlib.Path, max_lines: int = 200, max_bytes: int = 600_000) -> list[str]:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(max(0, size - max_bytes))
                f.readline()
            raw = f.read()
    except OSError:
        return []
    return raw.decode("utf-8", errors="replace").splitlines()[-max_lines:]


def _redact_headers(headers: dict) -> dict:
    out = dict(headers or {})
    if "Authorization" in out:
        out["Authorization"] = "<redacted>"
    return out


def runtime_log_path(cfg: dict | None = None) -> pathlib.Path:
    cfg = cfg or {}
    return _root_path(cfg.get("runtime_log_path"), "comms/runtime.ndjson")


def log_runtime_event(cfg: dict | None, event: str, **payload: Any) -> None:
    global _RUNTIME_SEQ
    cfg = cfg or {}
    if cfg.get("log_runtime", True) is False:
        return
    try:
        with _RUNTIME_LOCK:
            _RUNTIME_SEQ += 1
            seq = _RUNTIME_SEQ
        _append_ndjson(runtime_log_path(cfg), {
            "seq": seq,
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "event": event,
            **payload,
        })
    except Exception:
        pass


# ─── usage / structured response helpers ───────────────────────────────────

def _first_usage(obj: Any) -> dict | None:
    if isinstance(obj, dict):
        usage = obj.get("usage")
        if isinstance(usage, dict):
            return usage
        token_keys = {"prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"}
        if token_keys & set(obj.keys()):
            return {k: v for k, v in obj.items() if k.endswith("tokens") or k.endswith("_tokens") or k == "cost_in_usd_ticks"}
        for v in obj.values():
            u = _first_usage(v)
            if u:
                return u
    elif isinstance(obj, list):
        for v in obj:
            u = _first_usage(v)
            if u:
                return u
    return None


def usage_from_raw_response(entry: dict) -> tuple[dict | None, str, float | None]:
    raw = entry.get("raw") if isinstance(entry.get("raw"), dict) else {}
    model = str(raw.get("model") or entry.get("model") or "")
    elapsed = entry.get("elapsed_s")
    try:
        elapsed = float(elapsed) if elapsed is not None else None
    except (TypeError, ValueError):
        elapsed = None
    usage = None
    for key in ("body", "response"):
        if usage is None and isinstance(raw.get(key), dict):
            usage = _first_usage(raw[key])
            model = model or str(raw[key].get("model") or "")
    if usage is None and isinstance(raw.get("stdout"), str) and raw.get("stdout").strip():
        _, _, usage, _ = _parse_json_or_ndjson(str(raw.get("stdout")))
    return usage, model, elapsed


def _event_text_piece(obj: dict) -> tuple[str, str]:
    typ = str(obj.get("type") or obj.get("event") or obj.get("role") or "").lower()
    val = None
    for key in ("data", "text", "content", "delta", "output"):
        if isinstance(obj.get(key), str):
            val = obj[key]
            break
    if val is None:
        part = obj.get("part")
        if isinstance(part, dict):
            if isinstance(part.get("text"), str):
                val = part["text"]
                typ = typ or str(part.get("type") or "").lower()
            elif isinstance(part.get("content"), str):
                val = part["content"]
                typ = typ or str(part.get("type") or "").lower()
        msg = obj.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            val = msg["content"]
            typ = typ or str(msg.get("role") or "").lower()
    if not isinstance(val, str) or not val:
        return "", ""
    if any(x in typ for x in ("thought", "reason", "thinking")):
        return "", val
    if any(x in typ for x in ("text", "assistant", "message", "output", "completion", "answer")):
        return val, ""
    if typ in ("", "data", "chunk"):
        return val, ""
    return "", ""


def _walk_collect(obj: Any, content: list[str], reasoning: list[str]) -> None:
    if isinstance(obj, dict):
        c, r = _event_text_piece(obj)
        if c:
            content.append(c)
        if r:
            reasoning.append(r)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _walk_collect(v, content, reasoning)
    elif isinstance(obj, list):
        for v in obj:
            _walk_collect(v, content, reasoning)


def _parse_json_or_ndjson(text: str) -> tuple[str, str, dict | None, list[Any]]:
    objs: list[Any] = []
    if not text.strip():
        return "", "", None, objs
    try:
        objs.append(json.loads(text))
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                objs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if not objs:
        return text.strip(), "", None, objs
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    for obj in objs:
        _walk_collect(obj, content_parts, reasoning_parts)
    usage = next((u for u in (_first_usage(obj) for obj in objs) if u), None)
    content = "".join(content_parts).strip()
    reasoning = "".join(reasoning_parts).strip()
    if not content:
        for obj in objs:
            if isinstance(obj, dict):
                for key in ("result", "response", "answer", "text"):
                    if isinstance(obj.get(key), str) and obj[key].strip():
                        content = obj[key].strip()
                        break
            if content:
                break
    return (content or text.strip()), reasoning, usage, objs


def _xai_response_text(resp: dict) -> tuple[str, str]:
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"], ""
    parts: list[str] = []
    reasoning: list[str] = []
    for item in resp.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "reasoning":
            for s in item.get("summary", []) or []:
                if isinstance(s, dict) and isinstance(s.get("text"), str):
                    reasoning.append(s["text"])
        for c in item.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") in ("output_text", "text") and isinstance(c.get("text"), str):
                parts.append(c["text"])
    return "\n".join(parts).strip(), "\n".join(reasoning).strip()


# ─── CLI helpers shared by CLI brain nodes ──────────────────────────────────

def _candidate_executables(name: str) -> list[str]:
    expanded = os.path.expandvars(os.path.expanduser(str(name or ""))).strip()
    if not expanded:
        return []
    p = pathlib.Path(expanded)
    if p.is_absolute() or any(sep in expanded for sep in ("/", "\\")):
        return [str(p)]
    names = [expanded]
    if os.name == "nt" and not pathlib.Path(expanded).suffix:
        names += [expanded + ext for ext in (".exe", ".cmd", ".bat", ".ps1")]
    found: list[str] = []
    for n in names:
        hit = shutil.which(n)
        if hit and hit not in found:
            found.append(hit)
    return found or [expanded]


def _resolve_executable(name: str, transport: str) -> str:
    candidates = _candidate_executables(name)
    for c in candidates:
        if pathlib.Path(c).is_absolute() and pathlib.Path(c).exists():
            return c
        hit = shutil.which(c)
        if hit:
            return hit
    raise FileNotFoundError(f"{transport} brain executable not found: {name!r}; candidates={candidates}")


def _redact_argv(cmd: list[str], prompt_values: set[str]) -> list[str]:
    out: list[str] = []
    for arg in cmd:
        if arg in prompt_values:
            out.append(f"<prompt:{len(arg)} chars>")
        elif any(arg.endswith(secret) and secret for secret in prompt_values):
            out.append("<prompt>")
        else:
            out.append(arg)
    return out


def _windows_shell_cmd(cmd: list[str]) -> tuple[Any, bool]:
    if os.name == "nt" and cmd:
        suffix = pathlib.Path(cmd[0]).suffix.lower()
        if suffix in (".cmd", ".bat", ".ps1"):
            return subprocess.list2cmdline(cmd), True
    return cmd, False


def _make_prompt_file(name: str, prompt: str) -> pathlib.Path:
    d = ROOT / "comms" / "cli_prompts"
    d.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=f"{name}-", suffix=".prompt.txt", dir=str(d), text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(prompt)
    return pathlib.Path(path)


def _run_cli_transport(brain: "Brain", name: str, cmd: list[str], model: str, cfg: dict, seq: int,
                       prompt_values: set[str] | None = None) -> tuple[str, str]:
    started = time.time()
    prompt_values = prompt_values or set()
    redacted_cmd = _redact_argv(cmd, prompt_values)
    brain._log_raw(seq, "request", name, {
        "argv": redacted_cmd,
        "model": model,
        "prompt_chars": sum(len(x) for x in prompt_values),
    }, rod_feedback=any("ROD_REASONING_CONTENT" in p for p in prompt_values))
    env = os.environ.copy()
    for k, v in (cfg.get("env") or {}).items():
        env[str(k)] = str(v)
    run_args, shell = _windows_shell_cmd(cmd)
    try:
        proc = subprocess.run(
            run_args,
            shell=shell,
            capture_output=True,
            timeout=brain._timeout(cfg),
            cwd=str(_root_path(cfg.get("cwd"), ".")) if cfg.get("cwd") else None,
            env=env,
        )
    except Exception as e:
        raise RuntimeError(f"{name} brain: {e}")
    stdout = _read_text_lossy(proc.stdout or b"")
    stderr = _read_text_lossy(proc.stderr or b"")
    brain._log_raw(seq, "response", name, {
        "argv": redacted_cmd,
        "model": model,
        "returncode": proc.returncode,
        "stdout": _truncate(stdout, 200_000),
        "stderr": _truncate(stderr, 20_000),
    }, elapsed_s=round(time.time() - started, 3))
    if proc.returncode != 0:
        raise RuntimeError(f"{name} brain: exit {proc.returncode}: {stderr[:1000] or stdout[:1000]}")
    content, reasoning, _usage, _objs = _parse_json_or_ndjson(stdout)
    return content, reasoning


# ─── Brain runtime ──────────────────────────────────────────────────────────

class Brain:
    def __init__(self, model_cfg: dict):
        ensure_brain_nodes()
        self.cfg = dict(model_cfg or {})
        self._calls_made = 0

    def transport(self) -> str:
        return str(self.cfg.get("transport", "openai"))

    def _node_name(self, transport: str | None = None) -> str:
        return BRAIN_ALIASES.get(str(transport or self.transport()), str(transport or self.transport()))

    def _model_name(self, transport: str) -> str:
        block = self.cfg.get(transport) if isinstance(self.cfg.get(transport), dict) else {}
        alias = self._node_name(transport)
        if not block and isinstance(self.cfg.get(alias), dict):
            block = self.cfg.get(alias)
        return str(block.get("model") or self.cfg.get("model") or "")

    def _provider_cfg(self, name: str | None = None) -> dict:
        key = self._node_name(name or self.transport())
        merged = dict(self.cfg)
        specific = self.cfg.get(key) if isinstance(self.cfg.get(key), dict) else {}
        merged.update(specific)
        params = specific.get("parameters") if isinstance(specific.get("parameters"), dict) else {}
        merged.update(params)
        return merged

    def _param(self, key: str, default: Any) -> Any:
        cfg = self._provider_cfg()
        return cfg.get(key, self.cfg.get(key, default))

    def _timeout(self, cfg: dict | None = None) -> float:
        cfg = cfg or self.cfg
        raw = cfg.get("timeout", self.cfg.get("timeout", 900))
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 900.0
        if value <= 0:
            # urllib uses timeout=0 as non-blocking sockets on Windows; that produced
            # WinError 10035 in the supplied run. Zero is invalid for this fail-hard loop.
            value = float(self.cfg.get("timeout", 900) or 900)
            if value <= 0:
                value = 900.0
        return value

    def _enforce_call_budget(self) -> None:
        limit = self.cfg.get("max_brain_calls")
        if limit is None:
            return
        try:
            cap = int(limit)
        except (TypeError, ValueError):
            return
        if cap > 0 and self._calls_made >= cap:
            raise RuntimeError(
                f"brain call budget exceeded ({self._calls_made} >= {cap}); "
                "raise max_brain_calls or stop the run"
            )

    def call_count(self) -> int:
        return self._calls_made

    def _log_raw(self, seq: int, phase: str, transport: str, raw: Any, **extra: Any) -> None:
        log_raw_entry(self.cfg, {
            "seq": seq,
            "phase": phase,
            "transport": transport,
            "model": self._model_name(transport),
            "raw": raw,
            **extra,
        })

    def think(self, system: str, user: str, parse_retries: int = 2) -> tuple[str, dict | None, str]:
        base = self._param("temperature", 0.3)
        bump = self._param("temperature_bump", 0.15)
        content, parsed, reasoning = "", None, ""
        for attempt in range(parse_retries + 1):
            temp = base if attempt == 0 else min(1.0, float(base) + float(bump) * attempt)
            c1, r1 = self._call(system, user, temp)
            reasoning = reasoning_from(c1, r1)
            rod_user = user + "\n\nROD_REASONING_CONTENT:\n" + (reasoning or "(none)")
            content, r2 = self._call(system, rod_user, temp)
            parsed = extract_json_object(content)
            if parsed:
                break
            log_runtime_event(self.cfg, "parse_retry", transport=self.transport(), attempt=attempt + 1,
                              content_preview=_truncate(content, 1000), response_reasoning_chars=len(r2 or ""))
        return content, parsed, reasoning

    def _call(self, system: str, user: str, temperature: float) -> tuple[str, str]:
        self._enforce_call_budget()
        self._calls_made += 1
        transport = self.transport()
        node = self._node_name(transport)
        path = brain_node_path(transport)
        if not path.exists():
            raise FileNotFoundError(f"no brain node for transport {transport!r} at {path}")
        seq = _next_raw_seq()
        started = time.time()
        ns: dict[str, Any] = {
            "brain": self,
            "cfg": self._provider_cfg(node),
            "system": system,
            "user": user,
            "temperature": temperature,
            "seq": seq,
            "transport": transport,
            "node_name": node,
            "content": "",
            "reasoning": "",
            "json": json,
            "os": os,
            "pathlib": pathlib,
            "re": re,
            "shutil": shutil,
            "subprocess": subprocess,
            "threading": threading,
            "time": time,
            "urllib": urllib,
            "_root_path": _root_path,
            "_atomic_write_json": _atomic_write_json,
            "_redact_headers": _redact_headers,
            "_resolve_executable": _resolve_executable,
            "_make_prompt_file": _make_prompt_file,
            "_run_cli_transport": _run_cli_transport,
            "_parse_json_or_ndjson": _parse_json_or_ndjson,
            "_xai_response_text": _xai_response_text,
            "_proxy_content": _proxy_content,
        }
        try:
            src = path.read_text(encoding="utf-8")
            exec(compile(src, str(path), "exec"), ns)
            content = str(ns.get("content") or "")
            reasoning = str(ns.get("reasoning") or "")
            if not content and not reasoning:
                raise RuntimeError(f"{transport} brain returned empty content and empty reasoning")
            return content, reasoning
        except Exception as e:
            self._log_raw(seq, "response", transport, {"error": f"{type(e).__name__}: {e}"},
                          elapsed_s=round(time.time() - started, 3))
            raise


def _proxy_content(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    choices = resp.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            return str(msg.get("content") or msg.get("reasoning_content") or "")
    return str(resp.get("content") or resp.get("response") or resp.get("text") or "")
