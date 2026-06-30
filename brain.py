"""brain — stateless cognition transports with one typed-record contract.

Transports selected by wiring model.transport:
  - openai        : OpenAI-compatible /v1/chat/completions (LM Studio by default)
  - xai_responses : xAI /v1/responses
  - opencode      : OpenCode CLI documented non-interactive `opencode run`
  - grok_build    : Grok Build CLI headless `grok -p`
  - file_proxy    : request.json -> response.json handoff
  - browser_ai    : optional browser-hosted AI handoff through desktop verbs

ROD remains unchanged: every decision is two stateless calls. Call 1 provides reasoning;
Call 2 receives ROD_REASONING_CONTENT and commits the typed JSON record.

Logging discipline:
  - <timestamp>.txt in workspace root is the single forensic raw brain log (one JSON line per entry).
  - Raw request/response bytes are captured at each transport boundary and appended with seq/ts/phase.
  - comms/runtime.ndjson is a slim organism lifecycle stream only (node_start, narration — not brain I/O).
  - state.json is live snapshot truth; forensic logs are never polled as live state.

No silent fallbacks: if the selected transport is unavailable, the call raises with a
specific falsifiable reason.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


# ─── JSON / reasoning extraction ────────────────────────────────────────────

def extract_json_object(text: str):
    """Return the model's committed JSON record, or None.

    Reasoning models inline thinking and close it with </think>, then emit JSON. That
    thinking contains brace-laden prose, so drop everything up to the final </think>,
    then return the LAST balanced top-level {...} that parses.
    """
    if not text:
        return None
    text = text.strip()
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1].strip()
    # Strip simple markdown fences around the whole answer.
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
    """Call-1 reasoning: dedicated field, else inline <think>, else content."""
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
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n…[truncated {len(s) - limit} chars]"


_RUNTIME_SEQ = 0
_RUNTIME_LOCK = threading.Lock()
_RAW_LOG_PATH: pathlib.Path | None = None
_RAW_SEQ = 0
_RAW_LOCK = threading.Lock()


def raw_log_path(cfg: dict | None = None) -> pathlib.Path:
    """One append-only raw brain log per process, created at first brain call."""
    global _RAW_LOG_PATH
    cfg = cfg or {}
    if _RAW_LOG_PATH is None:
        explicit = cfg.get("raw_log_path")
        if explicit:
            p = _root_path(explicit, "")
            _RAW_LOG_PATH = p
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
    """Append one raw log line. Logging must never change organism behavior."""
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
    """Count request/response rows in raw log entries (optionally per transport)."""
    out = {"request": 0, "response": 0}
    for row in entries:
        if transport and row.get("transport") != transport:
            continue
        phase = row.get("phase")
        if phase in out:
            out[phase] += 1
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


def usage_from_raw_response(entry: dict) -> tuple[dict | None, str, float | None]:
    """Derive usage dict, model name, and elapsed_s from one raw response log entry."""
    raw = entry.get("raw") if isinstance(entry.get("raw"), dict) else {}
    transport = str(entry.get("transport") or "")
    model = str(raw.get("model") or entry.get("model") or "")
    elapsed = entry.get("elapsed_s")
    try:
        elapsed = float(elapsed) if elapsed is not None else None
    except (TypeError, ValueError):
        elapsed = None

    usage = None
    body = raw.get("body")
    if isinstance(body, dict):
        usage = _first_usage(body)
        if not model:
            model = str(body.get("model") or "")
    resp = raw.get("response")
    if usage is None and isinstance(resp, dict):
        usage = _first_usage(resp)
        if not model:
            model = str(resp.get("model") or "")

    if usage is None and isinstance(raw.get("stdout"), str) and raw.get("stdout").strip():
        _, _, usage, _ = _parse_json_or_ndjson(str(raw.get("stdout")))

    if elapsed is None:
        try:
            elapsed = float(raw.get("elapsed_s"))
        except (TypeError, ValueError):
            elapsed = None
    return usage, model, elapsed


def _redact_headers(headers: dict) -> dict:
    out = dict(headers or {})
    if "Authorization" in out:
        out["Authorization"] = "<redacted>"
    return out


def runtime_log_path(cfg: dict | None = None) -> pathlib.Path:
    cfg = cfg or {}
    return _root_path(cfg.get("runtime_log_path"), "comms/runtime.ndjson")


def log_runtime_event(cfg: dict | None, event: str, **payload: Any) -> None:
    """Append one compact event. This file is the workbench's live event stream."""
    global _RUNTIME_SEQ
    cfg = cfg or {}
    if cfg.get("log_runtime", True) is False:
        return
    try:
        with _RUNTIME_LOCK:
            _RUNTIME_SEQ += 1
            seq = _RUNTIME_SEQ
        row = {
            "seq": seq,
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "event": event,
            **payload,
        }
        _append_ndjson(runtime_log_path(cfg), row)
    except Exception:
        # Logging must never change organism behavior.
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


def _event_text_piece(obj: dict) -> tuple[str, str]:
    """Return (content_piece, reasoning_piece) from known/unknown JSON event shapes.

    Tested-in-session with the attached Grok Build stream: type=thought/data chunks are
    reasoning, type=text/data chunks are final content. OpenCode --format json uses JSON
    events too, so this also accepts assistant/message/output-like chunks.
    """
    typ = str(obj.get("type") or obj.get("event") or obj.get("role") or "").lower()
    val = None
    for key in ("data", "text", "content", "delta", "output"):
        if isinstance(obj.get(key), str):
            val = obj[key]
            break
    if val is None:
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
    # Role-free final JSON event chunks sometimes expose only data/content. Treat as
    # content unless it is clearly metadata.
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
    """Parse a full JSON response or an NDJSON event stream.

    Returns (final_content, reasoning, usage, parsed_objects). If parsing fails, the raw
    text is returned as content. This is intentional: plain text CLI output is valid.
    """
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

    usage = None
    for obj in objs:
        usage = _first_usage(obj)
        if usage:
            break

    content = "".join(content_parts).strip()
    reasoning = "".join(reasoning_parts).strip()
    if not content:
        # Some CLIs emit one final object containing a conventional answer field.
        for obj in objs:
            if isinstance(obj, dict):
                for key in ("result", "response", "answer"):
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


def _cost_usd(usage: dict | None) -> float | None:
    if not isinstance(usage, dict):
        return None
    ticks = usage.get("cost_in_usd_ticks")
    try:
        return float(ticks) / 10_000_000_000 if ticks is not None else None
    except (TypeError, ValueError):
        return None


# ─── CLI helpers ────────────────────────────────────────────────────────────

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
    hint = ""
    if transport == "opencode":
        hint = " Install OpenCode or set model.opencode.exe to opencode.cmd/opencode.exe/full path."
    raise FileNotFoundError(f"{transport} transport executable not found: {name!r}; candidates={candidates}.{hint}")


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
    """Return subprocess args/shell. Batch shims need cmd.exe on Windows."""
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


# ─── Brain ──────────────────────────────────────────────────────────────────

class Brain:
    def __init__(self, model_cfg: dict):
        self.cfg = dict(model_cfg or {})
        self._calls_made = 0

    def transport(self) -> str:
        return self.cfg.get("transport", "openai")

    def _model_name(self, transport: str) -> str:
        block = self.cfg.get(transport) if isinstance(self.cfg.get(transport), dict) else {}
        return str(block.get("model") or self.cfg.get("model") or "")

    def _enforce_call_budget(self) -> None:
        """Hard stop by brain-call counter — not wall-clock time."""
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
        """One ROD decision. Returns (content, parsed_record_or_None, reasoning)."""
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

    # ── config helpers ─────────────────────────────────────────────────────
    def _provider_cfg(self, name: str) -> dict:
        merged = dict(self.cfg)
        specific = self.cfg.get(name) if isinstance(self.cfg.get(name), dict) else {}
        merged.update(specific)
        params = specific.get("parameters") if isinstance(specific.get("parameters"), dict) else {}
        merged.update(params)
        return merged

    def _param(self, key: str, default: Any) -> Any:
        t = self.transport()
        cfg = self._provider_cfg(t if t in ("openai", "opencode", "grok_build", "xai_responses") else "openai")
        return cfg.get(key, self.cfg.get(key, default))

    def _timeout(self, cfg: dict | None = None) -> float:
        cfg = cfg or self.cfg
        try:
            return float(cfg.get("timeout", self.cfg.get("timeout", 900)))
        except (TypeError, ValueError):
            return 900.0

    # ── transport dispatch ─────────────────────────────────────────────────
    def _call(self, system: str, user: str, temperature: float) -> tuple[str, str]:
        self._enforce_call_budget()
        self._calls_made += 1
        t = self.transport()
        seq = _next_raw_seq()
        started = time.time()
        try:
            if t == "file_proxy":
                content, reasoning = self._file_proxy(system, user, seq), ""
            elif t == "opencode":
                content, reasoning = self._opencode(system, user, temperature, seq)
            elif t in ("grok_build", "grok_build_cli"):
                content, reasoning = self._grok_build_cli(system, user, temperature, seq)
            elif t in ("xai_responses", "grok_build_api"):
                content, reasoning = self._xai_responses(system, user, temperature, seq)
            elif t == "browser_ai":
                content, reasoning = self._browser_ai(system, user, seq), ""
            else:
                content, reasoning = self._openai(system, user, temperature, seq)
        except Exception as e:
            self._log_raw(seq, "response", t, {"error": f"{type(e).__name__}: {e}"},
                          elapsed_s=round(time.time() - started, 3))
            raise
        return content, reasoning

    # ── OpenAI-compatible chat completions ─────────────────────────────────
    def _openai(self, system: str, user: str, temperature: float, seq: int) -> tuple[str, str]:
        cfg = self._provider_cfg("openai")
        host = str(cfg.get("host", "http://localhost:1234")).rstrip("/")
        path = str(cfg.get("endpoint_path", "/v1/chat/completions"))
        payload = {
            "model": cfg.get("model", "local-model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": cfg.get("max_tokens", self.cfg.get("max_tokens", 2048)),
            "stream": False,
        }
        for key in (
            "top_p", "top_k", "min_p", "repeat_penalty", "presence_penalty", "frequency_penalty",
            "stop", "seed", "thinking", "response_format", "logit_bias", "n", "user"
        ):
            if key in cfg:
                payload[key] = cfg[key]
        headers = {"Content-Type": "application/json"}
        api_key = cfg.get("api_key") or os.environ.get(str(cfg.get("api_key_env", "")))
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        url = host + path
        self._log_raw(seq, "request", "openai", {
            "url": url, "model": payload.get("model"), "headers": _redact_headers(headers), "body": payload,
        }, rod_feedback="ROD_REASONING_CONTENT" in user)
        started = time.time()
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout(cfg)) as r:
                raw_text = r.read().decode("utf-8", errors="replace")
                resp = json.loads(raw_text)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"openai transport: HTTP {e.code}: {body[:1000]}")
        except Exception as e:
            raise RuntimeError(f"openai transport: {e}")
        self._log_raw(seq, "response", "openai", {"model": payload.get("model"), "body": resp},
                      elapsed_s=round(time.time() - started, 3))
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "") or msg.get("reasoning", "")
        return content, reasoning

    # ── xAI Responses API direct path ──────────────────────────────────────
    def _xai_responses(self, system: str, user: str, temperature: float, seq: int) -> tuple[str, str]:
        cfg = self._provider_cfg("xai_responses")
        host = str(cfg.get("host", "https://api.x.ai")).rstrip("/")
        path = str(cfg.get("endpoint_path", "/v1/responses"))
        model = str(cfg.get("model", "grok-build-0.1"))
        payload: dict[str, Any] = {
            "model": model,
            "input": "SYSTEM:\n" + system + "\n\nUSER:\n" + user,
            "store": bool(cfg.get("store", False)),
        }
        for key in (
            "temperature", "top_p", "max_output_tokens", "parallel_tool_calls", "reasoning",
            "text", "tools", "tool_choice", "metadata", "service_tier", "user"
        ):
            if key == "temperature":
                payload[key] = temperature
            elif key in cfg:
                payload[key] = cfg[key]
        headers = {"Content-Type": "application/json"}
        api_key = cfg.get("api_key") or os.environ.get(str(cfg.get("api_key_env", "XAI_API_KEY")))
        if not api_key:
            raise RuntimeError("xai_responses transport: missing API key; set XAI_API_KEY or model.xai_responses.api_key_env")
        headers["Authorization"] = f"Bearer {api_key}"
        url = host + path
        self._log_raw(seq, "request", "xai_responses", {
            "url": url, "model": model, "headers": _redact_headers(headers), "body": payload,
        }, rod_feedback="ROD_REASONING_CONTENT" in user)
        started = time.time()
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout(cfg)) as r:
                raw_text = r.read().decode("utf-8", errors="replace")
                resp = json.loads(raw_text)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"xai_responses transport: HTTP {e.code}: {body[:1000]}")
        except Exception as e:
            raise RuntimeError(f"xai_responses transport: {e}")
        content, reasoning = _xai_response_text(resp)
        if not content:
            raise RuntimeError("xai_responses transport: empty response text")
        self._log_raw(seq, "response", "xai_responses", {"model": model, "body": resp},
                      elapsed_s=round(time.time() - started, 3))
        return content, reasoning

    # ── file proxy ─────────────────────────────────────────────────────────
    def _file_proxy(self, system: str, user: str, seq: int) -> str:
        cfg = self.cfg.get("file_proxy", {})
        req_path = _root_path(cfg.get("request_path"), "comms/request.json")
        resp_path = _root_path(cfg.get("response_path"), "comms/response.json")
        archive = _root_path(cfg.get("archive_dir"), "comms/archive")
        for p in (req_path.parent, archive):
            p.mkdir(parents=True, exist_ok=True)
        rid = f"egai-{int(time.time()*1000)}-{os.getpid()}-{threading.get_ident() % 100000}"
        request_obj = {
            "id": rid, "status": "pending", "created_at": time.time(),
            "transport": "file_proxy", "model": self.cfg.get("model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "system": system, "user": user,
        }
        _atomic_write_json(req_path, request_obj)
        self._log_raw(seq, "request", "file_proxy", {"request_path": str(req_path), "body": request_obj},
                      rod_feedback="ROD_REASONING_CONTENT" in user)
        started = time.time()
        poll = max(0.05, int(cfg.get("poll_interval_ms", 1000)) / 1000.0)
        deadline = started + self._timeout()
        while time.time() < deadline:
            if resp_path.exists():
                try:
                    resp = json.loads(resp_path.read_text(encoding="utf-8") or "{}")
                except json.JSONDecodeError:
                    time.sleep(poll)
                    continue
                if resp.get("id") in (None, "", rid):
                    content = _proxy_content(resp)
                    self._log_raw(seq, "response", "file_proxy",
                                  {"response_path": str(resp_path), "body": resp, "id": rid},
                                  elapsed_s=round(time.time() - started, 3))
                    try:
                        shutil.move(str(resp_path), str(archive / f"response.{rid}.json"))
                    except OSError:
                        pass
                    return content
            time.sleep(poll)
        raise TimeoutError(f"file_proxy transport timed out waiting for {resp_path}")

    # ── OpenCode CLI stateless run ─────────────────────────────────────────
    def _opencode(self, system: str, user: str, temperature: float, seq: int) -> tuple[str, str]:
        cfg = self._provider_cfg("opencode")
        exe = _resolve_executable(str(cfg.get("exe") or "opencode"), "opencode")
        model = cfg.get("model")
        prompt = system + "\n\n" + user
        cmd = [exe, "run"]
        if cfg.get("command"):
            cmd += ["--command", str(cfg["command"])]
        if model:
            cmd += ["--model", str(model)]
        if cfg.get("agent"):
            cmd += ["--agent", str(cfg["agent"])]
        if cfg.get("format"):
            cmd += ["--format", str(cfg["format"])]
        if cfg.get("variant"):
            cmd += ["--variant", str(cfg["variant"])]
        if cfg.get("thinking", False):
            cmd += ["--thinking"]
        if cfg.get("attach"):
            cmd += ["--attach", str(cfg["attach"])]
        if cfg.get("dir"):
            cmd += ["--dir", str(cfg["dir"])]
        if cfg.get("skip_permissions", False):
            cmd += ["--dangerously-skip-permissions"]
        for f in cfg.get("files", []) or []:
            cmd += ["--file", str(f)]

        prompt_values = {prompt}
        prompt_mode = str(cfg.get("prompt_mode", "file")).lower()
        temp_path: pathlib.Path | None = None
        if prompt_mode == "argv":
            cmd.append(prompt)
        elif prompt_mode == "file":
            temp_path = _make_prompt_file("opencode", prompt)
            # OpenCode requires a positional message AND -f attachments. Message before --file;
            # a long trailing positional is misread as another file path (see runtime.ndjson 6/29).
            cmd.append(str(cfg.get("file_message") or "Follow the attached prompt."))
            cmd += ["--file", str(temp_path)]
        else:
            raise ValueError(f"opencode prompt_mode must be 'file' or 'argv', got {prompt_mode!r}")

        cmd += [str(x) for x in (cfg.get("extra_args") or [])]
        try:
            return self._run_cli_transport("opencode", cmd, str(model or ""), cfg, seq, prompt_values=prompt_values)
        finally:
            if temp_path and not cfg.get("keep_prompt_files", False):
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    # ── Grok Build CLI stateless headless call ─────────────────────────────
    def _grok_build_cli(self, system: str, user: str, temperature: float, seq: int) -> tuple[str, str]:
        cfg = self._provider_cfg("grok_build")
        exe = _resolve_executable(str(cfg.get("exe") or "grok"), "grok_build")
        model = cfg.get("model", "grok-build")
        prompt = system + "\n\n" + user
        cmd = [exe, "-p", prompt]
        if model:
            cmd += ["-m", str(model)]
        if cfg.get("output_format"):
            cmd += ["--output-format", str(cfg["output_format"])]
        if cfg.get("cwd_flag") and cfg.get("dir"):
            cmd += [str(cfg["cwd_flag"]), str(cfg["dir"])]
        cmd += [str(x) for x in (cfg.get("extra_args") or [])]
        return self._run_cli_transport("grok_build", cmd, str(model), cfg, seq, prompt_values={prompt})

    def _run_cli_transport(self, name: str, cmd: list[str], model: str, cfg: dict, seq: int,
                           prompt_values: set[str] | None = None) -> tuple[str, str]:
        started = time.time()
        prompt_values = prompt_values or set()
        redacted_cmd = _redact_argv(cmd, prompt_values)
        self._log_raw(seq, "request", name, {
            "argv": redacted_cmd, "model": model, "prompt_chars": sum(len(x) for x in prompt_values),
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
                timeout=self._timeout(cfg),
                cwd=str(_root_path(cfg.get("cwd"), ".")) if cfg.get("cwd") else None,
                env=env,
            )
        except Exception as e:
            raise RuntimeError(f"{name} transport: {e}")
        stdout = _read_text_lossy(proc.stdout or b"")
        stderr = _read_text_lossy(proc.stderr or b"")
        elapsed = time.time() - started
        self._log_raw(seq, "response", name, {
            "argv": redacted_cmd, "model": model, "returncode": proc.returncode,
            "stdout": _truncate(stdout, 200_000), "stderr": _truncate(stderr, 20_000),
        }, elapsed_s=round(elapsed, 3))
        if proc.returncode != 0:
            raise RuntimeError(f"{name} transport: exit {proc.returncode}: {stderr[:1000] or stdout[:1000]}")
        content, reasoning, _usage, _objs = _parse_json_or_ndjson(stdout)
        if not content:
            raise RuntimeError(f"{name} transport: empty response")
        return content, reasoning

    def _browser_ai(self, system: str, user: str, seq: int) -> str:
        import actions
        if not hasattr(actions, "browser_ai_handoff"):
            raise RuntimeError("browser_ai transport: actions.browser_ai_handoff not available; use file_proxy")
        prompt = system + "\n\n" + user
        self._log_raw(seq, "request", "browser_ai", {"prompt": prompt},
                      rod_feedback="ROD_REASONING_CONTENT" in prompt)
        started = time.time()
        out = actions.browser_ai_handoff(self.cfg.get("browser_ai", {}), prompt)
        if str(out).upper().startswith("FAILED"):
            raise RuntimeError(f"browser_ai transport: {out}")
        text = str(out).replace("browser_ai_response:", "", 1).strip()
        self._log_raw(seq, "response", "browser_ai", {"text": text}, elapsed_s=round(time.time() - started, 3))
        return text


def _proxy_content(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    choices = resp.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            return str(msg.get("content") or msg.get("reasoning_content") or "")
    return str(resp.get("content") or resp.get("response") or resp.get("text") or "")
