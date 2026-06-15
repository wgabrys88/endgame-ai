"""LLM backend — LM Studio + ACP."""
from __future__ import annotations
import contextlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None
_llm_gate = threading.Semaphore(max(1, config.LLM_MAX_CONCURRENT))

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{[\s\S]*\}")


@dataclass(frozen=True)
class LLMResult:
    text: str
    reasoning: str = ""
    reasoning_tokens: int = 0
    completion_tokens: int = 0


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def extract_thinking(raw: str) -> tuple[str, str]:
    thinks: list[str] = []
    def _cap(m: re.Match[str]) -> str:
        thinks.append(m.group(1).strip()); return ""
    text = _THINK_RE.sub(_cap, raw).strip()
    reasoning = "\n\n".join(t for t in thinks if t)
    if not reasoning and text and not text.lstrip().startswith("{"):
        brace = text.find("{")
        if brace > 0 and len(text[:brace].strip()) >= 20:
            reasoning = text[:brace].strip()
            text = text[brace:].strip()
    return text, reasoning


def extract_json(raw: str) -> str:
    text, _ = extract_thinking(raw)
    text = text.strip()
    if text.startswith("{"):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text)
            return json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    m = _JSON_RE.search(text)
    if not m:
        return text
    try:
        obj, _ = json.JSONDecoder().raw_decode(m.group(0))
        return json.dumps(obj, ensure_ascii=False)
    except json.JSONDecodeError:
        return m.group(0)


def _parse_message(msg: dict[str, Any], usage: Any, *, want_json: bool) -> LLMResult:
    raw = str(msg.get("content") or "")
    api_reasoning = str(msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
    text, inline_reasoning = extract_thinking(raw)
    reasoning = api_reasoning or inline_reasoning
    if want_json:
        text = extract_json(text if text else raw)
        if not text.strip().startswith("{"):
            for candidate in (reasoning, raw):
                if candidate:
                    recovered = extract_json(candidate)
                    if recovered.strip().startswith("{"):
                        text = recovered; break
    r_tok, c_tok = 0, 0
    if isinstance(usage, dict):
        c_tok = int(usage.get("completion_tokens", 0) or 0)
        details = usage.get("completion_tokens_details") or {}
        if isinstance(details, dict):
            r_tok = int(details.get("reasoning_tokens", 0) or 0)
    return LLMResult(text=text, reasoning=reasoning, reasoning_tokens=r_tok, completion_tokens=c_tok)


@contextlib.contextmanager
def _global_lock():
    path = config.LMS_GLOBAL_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1); break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def call_llm(system: str, user: str, role: str, *, max_tokens: int = 0,
             temperature: float | None = None, schema: dict | None = None,
             cache_key: str = "") -> LLMResult:
    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    tokens = max_tokens or config.BUDGET.get(role, config.LLM_MAX_TOKENS)
    body: dict[str, Any] = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temp, "top_p": config.LLM_TOP_P, "top_k": config.LLM_TOP_K,
        "max_tokens": tokens, "stream": False, "stop": config.LLM_STOP,
        "presence_penalty": config.LLM_PRESENCE_PENALTY,
        "frequency_penalty": config.LLM_FREQUENCY_PENALTY,
        "repeat_penalty": config.LLM_REPEAT_PENALTY, "seed": config.LLM_SEED,
    }
    if schema and config.LLM_API_SCHEMA:
        body["response_format"] = schema
    if config.LLM_THINKING_ENABLED:
        body["enable_thinking"] = True
        tb = config.THINKING_BUDGET.get(role, config.LLM_THINKING_BUDGET)
        if tb > 0:
            body["thinking_budget"] = tb

    log.emit("llm.request", {"role": role, "max_tokens": tokens, "temperature": temp})

    for attempt in range(3):
        try:
            with _llm_gate:
                lock = _global_lock() if config.LMS_USE_GLOBAL_LOCK else contextlib.nullcontext()
                with lock:
                    if _backend == "acp":
                        result = _call_acp(body, want_json=bool(schema))
                    else:
                        result = _call_lmstudio(body, want_json=bool(schema))
            log.emit("llm.response", {"role": role, "output_chars": len(result.text),
                                       "reasoning_chars": len(result.reasoning)})
            return result
        except (RuntimeError, ConnectionError, TimeoutError, OSError) as err:
            log.emit("llm_retry", {"attempt": attempt + 1, "error": str(err)[:200]})
            if attempt >= 2:
                log.emit("llm_fail", {"error": str(err)[:200]})
                return LLMResult(text="", reasoning=f"LLM unavailable: {str(err)[:200]}")
            time.sleep(min(2 ** attempt, 10))
    return LLMResult(text="")


# --- LM Studio ---

def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host is not None:
        return _cached_host, _cached_model or ""
    for host in config.LMS_HOSTS:
        model = _fetch_model(host)
        if model:
            _cached_host, _cached_model = host.rstrip("/"), model
            if not config.active_model_profile():
                activated, changed = config.apply_model_profile(model)
                if changed:
                    log.emit("model_profile", {"model": model, "profile": activated})
            return _cached_host, _cached_model
    _cached_host = config.LMS_HOSTS[0].rstrip("/") if config.LMS_HOSTS else ""
    _cached_model = ""
    return _cached_host, _cached_model


def _fetch_model(host: str) -> str | None:
    try:
        req = Request(f"{host.rstrip('/')}/v1/models", method="GET")
        with urlopen(req, timeout=config.LMS_MODEL_LIST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return next((m["id"] for m in data.get("data", []) if "id" in m), None)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _call_lmstudio(body: dict[str, Any], *, want_json: bool) -> LLMResult:
    host, model = _resolve_host_model()
    if model:
        body["model"] = model
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for i in range(config.LMS_REQUEST_ATTEMPTS):
        try:
            req = Request(f"{host}/v1/chat/completions", data=payload,
                         headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=config.LMS_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices")
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                if isinstance(msg, dict):
                    return _parse_message(msg, result.get("usage"), want_json=want_json)
            raise RuntimeError(f"no choices: {str(result)[:200]}")
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            if i < config.LMS_REQUEST_ATTEMPTS - 1:
                time.sleep(config.LMS_RETRY_DELAY)
            else:
                raise RuntimeError(str(e)) from e
    return LLMResult(text="")


# --- ACP ---

def _call_acp(body: dict[str, Any], *, want_json: bool) -> LLMResult:
    from acp_client import prompt_once
    msgs = body.get("messages", [])
    sys_c = next((m["content"] for m in msgs if m["role"] == "system"), "")
    usr_c = next((m["content"] for m in msgs if m["role"] == "user"), "")
    schema = body.get("response_format", {})
    schema_def = json.dumps(schema.get("json_schema", {}).get("schema", {}), indent=2) if schema else "{}"
    prompt = f"{sys_c}\n\nOutput ONLY valid JSON matching:\n{schema_def}\n\n---\n{usr_c}\n---\nJSON only."

    import msvcrt
    lock_path = config.BASE_DIR / ".acp.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        try:
            raw = prompt_once(prompt)
        finally:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)
    text, reasoning = extract_thinking(raw)
    if want_json:
        text = extract_json(text if text else raw)
    return LLMResult(text=text, reasoning=reasoning)
