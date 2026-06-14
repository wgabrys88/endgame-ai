"""LLM backend — LM Studio + ACP (runtime only; no benchmark CLI)."""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None
_llm_gate = threading.Semaphore(max(1, config.LLM_MAX_CONCURRENT))
_prompt_fingerprints: dict[str, str] = {}
_prompt_meta_lock = threading.Lock()

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{[\s\S]*\}")


@dataclass(frozen=True)
class LLMResult:
    """Parsed LLM output — JSON/text plus optional reasoning trace."""
    text: str
    reasoning: str = ""
    reasoning_tokens: int = 0
    completion_tokens: int = 0


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def extract_thinking(raw: str) -> tuple[str, str]:
    """Split inline thinking blocks and optional JSON preamble from visible content."""
    thinks: list[str] = []

    def _capture(match: re.Match[str]) -> str:
        thinks.append(match.group(1).strip())
        return ""

    text = _THINK_RE.sub(_capture, raw).strip()
    reasoning = "\n\n".join(t for t in thinks if t)
    if not reasoning and text and not text.lstrip().startswith("{"):
        brace = text.find("{")
        if brace > 0:
            preamble = text[:brace].strip()
            if len(preamble) >= 20:
                reasoning = preamble
                text = text[brace:].strip()
    return text, reasoning


def extract_json(raw: str) -> str:
    """Strip Nemotron thinking traces and return the first JSON object."""
    text, _ = extract_thinking(raw)
    text = text.strip()
    if text.startswith("{"):
        try:
            obj, _end = json.JSONDecoder().raw_decode(text)
            return json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    m = _JSON_RE.search(text)
    if not m:
        return text
    try:
        obj, _end = json.JSONDecoder().raw_decode(m.group(0))
        return json.dumps(obj, ensure_ascii=False)
    except json.JSONDecodeError:
        return m.group(0)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _cap_reasoning(text: str) -> str:
    limit = int(config.LLM_REASONING_LOG_MAX)
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit]


def _usage_meta(usage: Any) -> tuple[int, int]:
    if not isinstance(usage, dict):
        return 0, 0
    completion = int(usage.get("completion_tokens", 0) or 0)
    details = usage.get("completion_tokens_details") or {}
    reasoning = 0
    if isinstance(details, dict):
        reasoning = int(details.get("reasoning_tokens", 0) or 0)
    return reasoning, completion


def _parse_lmstudio_message(msg: dict[str, Any], usage: Any, *, want_json: bool) -> LLMResult:
    raw_content = str(msg.get("content") or "")
    api_reasoning = str(
        msg.get("reasoning_content") or msg.get("reasoning") or ""
    ).strip()
    text, inline_reasoning = extract_thinking(raw_content)
    reasoning = api_reasoning or inline_reasoning
    if want_json:
        text = extract_json(text if text else raw_content)
        if not text.strip():
            for candidate in (reasoning, raw_content):
                if not candidate:
                    continue
                recovered = extract_json(candidate)
                if recovered.strip().startswith("{"):
                    text = recovered
                    break
    reasoning_tokens, completion_tokens = _usage_meta(usage)
    return LLMResult(
        text=text,
        reasoning=reasoning,
        reasoning_tokens=reasoning_tokens,
        completion_tokens=completion_tokens,
    )


@contextlib.contextmanager
def _global_llm_lock():
    """Cross-process lock so LLM_MAX_CONCURRENT applies colony-wide."""
    path = config.LMS_GLOBAL_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt
            acquired = False
            while not acquired:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    acquired = True
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


def _trace_prompt(cache_key: str, system: str, user: str) -> None:
    if not config.LMS_TRACE_PROMPTS or not cache_key:
        return
    sys_fp = _sha(system)
    usr_fp = _sha(user)
    with _prompt_meta_lock:
        prev = _prompt_fingerprints.get(cache_key)
        if prev is None:
            _prompt_fingerprints[cache_key] = sys_fp
        elif prev != sys_fp:
            log.emit("prompt_drift", {"cache_key": cache_key, "prev": prev, "curr": sys_fp})
            _prompt_fingerprints[cache_key] = sys_fp
    log.emit(
        "prompt_signature",
        {"cache_key": cache_key, "system_fp": sys_fp, "user_fp": usr_fp,
         "system_chars": len(system), "user_chars": len(user)},
    )


def _emit_llm_response(role: str, cache_key: str, result: LLMResult) -> None:
    payload: dict[str, Any] = {
        "role": role,
        "cache_key": cache_key or role,
        "has_reasoning": bool(result.reasoning),
        "reasoning_chars": len(result.reasoning),
        "reasoning_tokens": result.reasoning_tokens,
        "completion_tokens": result.completion_tokens,
        "output_chars": len(result.text),
    }
    if result.reasoning:
        payload["reasoning"] = _cap_reasoning(result.reasoning)
    log.emit("llm.response", payload)


@dataclass(frozen=True)
class LLMCallParams:
    """Explicit generation params — safe for parallel benchmark slots."""
    temperature: float
    top_p: float
    top_k: int
    max_tokens: int
    repeat_penalty: float
    seed: int
    thinking_enabled: bool
    thinking_budget: int
    api_schema: bool
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop: tuple[str, ...] = ()
    logit_bias: dict[str, float] = field(default_factory=dict)


def _params_from_config(role: str, *, overrides: dict[str, Any] | None = None) -> LLMCallParams:
    overrides = overrides or {}
    return LLMCallParams(
        temperature=float(overrides.get("temperature", config.LLM_TEMPERATURE)),
        top_p=float(overrides.get("top_p", config.LLM_TOP_P)),
        top_k=int(overrides.get("top_k", config.LLM_TOP_K)),
        max_tokens=int(overrides.get("max_tokens", config.BUDGET.get(role, config.LLM_MAX_TOKENS))),
        repeat_penalty=float(overrides.get("repeat_penalty", config.LLM_REPEAT_PENALTY)),
        seed=int(overrides.get("seed", config.LLM_SEED)),
        thinking_enabled=bool(overrides.get("thinking_enabled", config.LLM_THINKING_ENABLED)),
        thinking_budget=int(overrides.get(
            "thinking_budget",
            config.THINKING_BUDGET.get(role, config.LLM_THINKING_BUDGET) or 0,
        )),
        api_schema=bool(overrides.get("api_schema", config.LLM_API_SCHEMA)),
        presence_penalty=float(overrides.get("presence_penalty", config.LLM_PRESENCE_PENALTY)),
        frequency_penalty=float(overrides.get("frequency_penalty", config.LLM_FREQUENCY_PENALTY)),
        stop=tuple(overrides.get("stop", config.LLM_STOP) or ()),
        logit_bias=dict(overrides.get("logit_bias", config.LLM_LOGIT_BIAS) or {}),
    )


def _build_llm_body(
    system: str,
    user: str,
    params: LLMCallParams,
    schema: dict | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": params.temperature,
        "top_p": params.top_p,
        "top_k": params.top_k,
        "max_tokens": params.max_tokens,
        "stream": False,
        "stop": list(params.stop),
        "presence_penalty": params.presence_penalty,
        "frequency_penalty": params.frequency_penalty,
        "repeat_penalty": params.repeat_penalty,
        "seed": params.seed,
    }
    if params.logit_bias:
        body["logit_bias"] = params.logit_bias
    if schema and params.api_schema:
        body["response_format"] = schema
    if params.thinking_enabled:
        body["enable_thinking"] = True
        if params.thinking_budget > 0:
            body["thinking_budget"] = params.thinking_budget
    return body


def call_llm(system: str, user: str, role: str, *, max_tokens: int = 0,
             temperature: float | None = None, schema: dict | None = None,
             cache_key: str = "") -> LLMResult:
    """Call LLM and return parsed text plus captured reasoning trace."""
    overrides: dict[str, Any] = {}
    if temperature is not None:
        overrides["temperature"] = temperature
    if max_tokens:
        overrides["max_tokens"] = max_tokens
    params = _params_from_config(role, overrides=overrides)
    body = _build_llm_body(system, user, params, schema)
    out_tokens = params.max_tokens
    think_budget = params.thinking_budget
    temp = params.temperature

    _trace_prompt(cache_key or role, system, user)
    log.emit("llm.request", {
        "role": role,
        "cache_key": cache_key or role,
        "thinking": bool(config.LLM_THINKING_ENABLED),
        "thinking_budget": think_budget if config.LLM_THINKING_ENABLED else 0,
        "max_tokens": out_tokens,
        "temperature": temp,
        "top_p": config.LLM_TOP_P,
        "top_k": config.LLM_TOP_K,
        "repeat_penalty": config.LLM_REPEAT_PENALTY,
        "seed": config.LLM_SEED,
        "concurrent_gate": int(config.LLM_MAX_CONCURRENT),
        "global_lock": bool(config.LMS_USE_GLOBAL_LOCK),
        "system_chars": len(system),
        "user_chars": len(user),
        "has_schema": bool(schema),
        "api_schema": bool(schema and config.LLM_API_SCHEMA),
    })

    for attempt in range(3):
        try:
            with _llm_gate:
                lock_ctx = _global_llm_lock() if config.LMS_USE_GLOBAL_LOCK else contextlib.nullcontext()
                with lock_ctx:
                    match _backend:
                        case "lmstudio":
                            result = _call_lmstudio(body, want_json=bool(schema))
                        case "acp":
                            result = _call_acp(body, want_json=bool(schema))
                        case _:
                            raise ValueError(f"unknown backend: {_backend}")
            _emit_llm_response(role, cache_key or role, result)
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
        models = [m["id"] for m in data.get("data", []) if "id" in m]
        return models[0] if models else None
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
                    return _parse_lmstudio_message(msg, result.get("usage"), want_json=want_json)
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

