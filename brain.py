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
  - comms/runtime.ndjson is the compact live event stream used by the workbench.
  - comms/session-*.log is the raw request/response journal for forensic debugging.
  - comms/brain_usage.ndjson is the structured usage ledger.
  - comms/brain_io.ndjson is optional raw transport JSON and is OFF by default.

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
_SESSION_LOG_PATH: pathlib.Path | None = None
_SESSION_SEQ = 0
_SESSION_LOCK = threading.Lock()


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


def _session_log_path(cfg: dict) -> pathlib.Path:
    """One raw request/response journal per process, across brain swaps."""
    global _SESSION_LOG_PATH
    if _SESSION_LOG_PATH is None:
        explicit = cfg.get("session_log_path")
        if explicit:
            _SESSION_LOG_PATH = _root_path(explicit, "comms/session.log")
        else:
            stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime())
            base = cfg.get("session_log_dir") or "comms"
            _SESSION_LOG_PATH = _root_path(None, f"{base}/session-{stamp}.log")
    return _SESSION_LOG_PATH


def _append_session(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


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
        self.io_log = _root_path(self.cfg.get("brain_io_log_path"), "comms/brain_io.ndjson")
        self.usage_log = _root_path(self.cfg.get("usage_log_path"), "comms/brain_usage.ndjson")
        self.session_log = _session_log_path(self.cfg)

    def transport(self) -> str:
        return self.cfg.get("transport", "openai")

    # ── raw session journal ────────────────────────────────────────────────
    def _log_request(self, transport: str, system: str, user: str, temperature: float) -> int:
        global _SESSION_SEQ
        if not self.cfg.get("log_session", True):
            return -1
        try:
            with _SESSION_LOCK:
                _SESSION_SEQ += 1
                seq = _SESSION_SEQ
            ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            model = self.cfg.get(transport, {}).get("model") if isinstance(self.cfg.get(transport), dict) else None
            model = model or self.cfg.get("model", "")
            block = (
                f"\n===== REQUEST #{seq} | {ts} | transport={transport} | model={model} "
                f"| temperature={temperature} =====\n"
                f"----- SYSTEM -----\n{system}\n"
                f"----- USER -----\n{user}\n"
                f"===== END REQUEST #{seq} =====\n"
            )
            _append_session(self.session_log, block)
            return seq
        except Exception:
            return -1

    def _log_response(self, seq: int, transport: str, started: float,
                      content: str = "", reasoning: str = "", error: str = "") -> None:
        if not self.cfg.get("log_session", True):
            return
        try:
            ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            elapsed = time.time() - started
            head = (
                f"\n===== RESPONSE #{seq} | {ts} | transport={transport} "
                f"| elapsed_s={elapsed:.2f}{' | ERROR' if error else ''} =====\n"
            )
            body = (f"----- ERROR -----\n{error}\n" if error else "")
            if reasoning:
                body += f"----- REASONING -----\n{reasoning}\n"
            if content or not error:
                body += f"----- CONTENT -----\n{content}\n"
            tail = f"===== END RESPONSE #{seq} =====\n"
            _append_session(self.session_log, head + body + tail)
        except Exception:
            pass

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
        t = self.transport()
        seq = self._log_request(t, system, user, temperature)
        started = time.time()
        log_runtime_event(self.cfg, "brain_request", transport=t, request_seq=seq,
                          model=self._provider_cfg(t).get("model", self.cfg.get("model", "")),
                          prompt_chars=len(system) + len(user), temperature=temperature)
        try:
            if t == "file_proxy":
                content, reasoning = self._file_proxy(system, user), ""
            elif t == "opencode":
                content, reasoning = self._opencode(system, user, temperature)
            elif t in ("grok_build", "grok_build_cli"):
                content, reasoning = self._grok_build_cli(system, user, temperature)
            elif t in ("xai_responses", "grok_build_api"):
                content, reasoning = self._xai_responses(system, user, temperature)
            elif t == "browser_ai":
                content, reasoning = self._browser_ai(system, user), ""
            else:
                content, reasoning = self._openai(system, user, temperature)
        except Exception as e:
            self._log_response(seq, t, started, error=f"{type(e).__name__}: {e}")
            log_runtime_event(self.cfg, "brain_error", transport=t, request_seq=seq,
                              elapsed_s=round(time.time() - started, 3), error=f"{type(e).__name__}: {e}")
            raise
        elapsed = time.time() - started
        self._log_response(seq, t, started, content=content, reasoning=reasoning)
        log_runtime_event(self.cfg, "brain_response", transport=t, request_seq=seq,
                          elapsed_s=round(elapsed, 3), content_chars=len(content or ""),
                          reasoning_chars=len(reasoning or ""), content_preview=_truncate(content, 600))
        return content, reasoning

    def _record_io(self, transport: str, direction: str, payload: dict):
        if self.cfg.get("log_brain_io", False):
            _append_ndjson(self.io_log, {"ts": time.time(), "transport": transport, "direction": direction, **payload})

    def _record_usage(self, transport: str, model: str | None, usage: dict | None, extra: dict | None = None):
        row = {"ts": time.time(), "transport": transport, "model": model or "", "usage": usage or {}, **(extra or {})}
        _append_ndjson(self.usage_log, row)
        extra_row = dict(extra or {})
        extra_row.setdefault("exact_usage", bool(usage))
        log_runtime_event(self.cfg, "usage", transport=transport, model=model or "",
                          usage=usage or {}, **extra_row)

    # ── OpenAI-compatible chat completions ─────────────────────────────────
    def _openai(self, system: str, user: str, temperature: float) -> tuple[str, str]:
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
        self._record_io("openai", "request", {"url": host + path, "model": payload.get("model"), "payload": payload})
        req = urllib.request.Request(host + path, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout(cfg)) as r:
                raw = r.read().decode("utf-8", errors="replace")
                resp = json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"openai transport: HTTP {e.code}: {body[:1000]}")
        except Exception as e:
            raise RuntimeError(f"openai transport: {e}")
        self._record_io("openai", "response_raw", {"model": payload.get("model"), "response": resp})
        self._record_usage("openai", str(payload.get("model")), resp.get("usage"), {"exact_usage": bool(resp.get("usage"))})
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "") or msg.get("reasoning", "")
        self._record_io("openai", "response", {"model": payload.get("model"), "content_preview": content[:1000]})
        return content, reasoning

    # ── xAI Responses API direct path ──────────────────────────────────────
    def _xai_responses(self, system: str, user: str, temperature: float) -> tuple[str, str]:
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
        self._record_io("xai_responses", "request", {"url": host + path, "model": model, "payload": {**payload, "input": payload["input"][:12000]}})
        req = urllib.request.Request(host + path, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout(cfg)) as r:
                raw = r.read().decode("utf-8", errors="replace")
                resp = json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"xai_responses transport: HTTP {e.code}: {body[:1000]}")
        except Exception as e:
            raise RuntimeError(f"xai_responses transport: {e}")
        content, reasoning = _xai_response_text(resp)
        if not content:
            raise RuntimeError("xai_responses transport: empty response text")
        usage = resp.get("usage") if isinstance(resp.get("usage"), dict) else None
        self._record_io("xai_responses", "response_raw", {"model": model, "response": resp})
        self._record_usage("xai_responses", model, usage, {"exact_usage": bool(usage), "cost_usd": _cost_usd(usage)})
        self._record_io("xai_responses", "response", {"model": model, "content_preview": content[:1000]})
        return content, reasoning

    # ── file proxy ─────────────────────────────────────────────────────────
    def _file_proxy(self, system: str, user: str) -> str:
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
        self._record_io("file_proxy", "request", {"request_path": str(req_path), "payload": request_obj})
        log_runtime_event(self.cfg, "file_proxy_pending", id=rid, request_path=str(req_path))
        poll = max(0.05, int(cfg.get("poll_interval_ms", 1000)) / 1000.0)
        deadline = time.time() + self._timeout()
        while time.time() < deadline:
            if resp_path.exists():
                try:
                    resp = json.loads(resp_path.read_text(encoding="utf-8") or "{}")
                except json.JSONDecodeError:
                    time.sleep(poll)
                    continue
                if resp.get("id") in (None, "", rid):
                    content = _proxy_content(resp)
                    self._record_io("file_proxy", "response_raw", {"response_path": str(resp_path), "response": resp})
                    usage = _first_usage(resp)
                    self._record_usage("file_proxy", str(self.cfg.get("model", "file_proxy")), usage, {"exact_usage": bool(usage)})
                    try:
                        shutil.move(str(resp_path), str(archive / f"response.{rid}.json"))
                    except OSError:
                        pass
                    log_runtime_event(self.cfg, "file_proxy_answered", id=rid, response_chars=len(content))
                    return content
            time.sleep(poll)
        raise TimeoutError(f"file_proxy transport timed out waiting for {resp_path}")

    # ── OpenCode CLI stateless run ─────────────────────────────────────────
    def _opencode(self, system: str, user: str, temperature: float) -> tuple[str, str]:
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
            cmd += ["--file", str(temp_path)]
            cmd.append("Read the attached prompt file as the complete stateless instruction. Return only the requested final answer.")
        else:
            raise ValueError(f"opencode prompt_mode must be 'file' or 'argv', got {prompt_mode!r}")

        cmd += [str(x) for x in (cfg.get("extra_args") or [])]
        try:
            return self._run_cli_transport("opencode", cmd, str(model or ""), cfg, prompt_values=prompt_values)
        finally:
            if temp_path and not cfg.get("keep_prompt_files", False):
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    # ── Grok Build CLI stateless headless call ─────────────────────────────
    def _grok_build_cli(self, system: str, user: str, temperature: float) -> tuple[str, str]:
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
        return self._run_cli_transport("grok_build", cmd, str(model), cfg, prompt_values={prompt})

    def _run_cli_transport(self, name: str, cmd: list[str], model: str, cfg: dict,
                           prompt_values: set[str] | None = None) -> tuple[str, str]:
        started = time.time()
        prompt_values = prompt_values or set()
        redacted_cmd = _redact_argv(cmd, prompt_values)
        self._record_io(name, "request", {"argv": redacted_cmd, "model": model,
                                           "prompt_chars": sum(len(x) for x in prompt_values)})
        log_runtime_event(self.cfg, "cli_start", transport=name, model=model, argv=redacted_cmd,
                          prompt_chars=sum(len(x) for x in prompt_values))
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
        self._record_io(name, "response_raw", {"argv": redacted_cmd, "returncode": proc.returncode,
                                                "elapsed_s": elapsed, "stdout": stdout, "stderr": stderr})
        log_runtime_event(self.cfg, "cli_exit", transport=name, model=model, returncode=proc.returncode,
                          elapsed_s=round(elapsed, 3), stdout_preview=_truncate(stdout, 800),
                          stderr_preview=_truncate(stderr, 800))
        if proc.returncode != 0:
            raise RuntimeError(f"{name} transport: exit {proc.returncode}: {stderr[:1000] or stdout[:1000]}")
        content, reasoning, usage, _objs = _parse_json_or_ndjson(stdout)
        if not content:
            raise RuntimeError(f"{name} transport: empty response")
        self._record_usage(name, model, usage, {
            "exact_usage": bool(usage),
            "elapsed_s": elapsed,
            "note": "usage parsed from CLI stdout" if usage else "CLI did not expose per-call token usage in stdout",
        })
        self._record_io(name, "response", {"model": model, "content_preview": content[:1000],
                                            "reasoning_preview": reasoning[:1000]})
        return content, reasoning

    def _browser_ai(self, system: str, user: str) -> str:
        import actions
        if not hasattr(actions, "browser_ai_handoff"):
            raise RuntimeError("browser_ai transport: actions.browser_ai_handoff not available; use file_proxy")
        prompt = system + "\n\n" + user
        out = actions.browser_ai_handoff(self.cfg.get("browser_ai", {}), prompt)
        if str(out).upper().startswith("FAILED"):
            raise RuntimeError(f"browser_ai transport: {out}")
        return str(out).replace("browser_ai_response:", "", 1).strip()


def _proxy_content(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    choices = resp.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            return str(msg.get("content") or msg.get("reasoning_content") or "")
    return str(resp.get("content") or resp.get("response") or resp.get("text") or "")
