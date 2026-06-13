from __future__ import annotations

import json
import msvcrt
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

__all__ = [
    "LLMReply", "call_llm", "call_llm_reply", "estimate_tokens",
    "effective_completion_cap", "set_backend", "get_backend", "close_backend",
    "get_last_reply", "consume_last_reply",
    "probe_host", "discover_hosts", "invalidate_host_cache",
]

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None
_last_reply: LLMReply | None = None


@dataclass(slots=True)
class LLMReply:
    text: str
    backend: str
    role: str
    prompt_tokens_est: int
    completion_tokens_est: int
    total_tokens_est: int
    prompt_tokens_actual: int | None
    completion_tokens_actual: int | None
    total_tokens_actual: int | None
    max_tokens_requested: int
    max_tokens_effective: int
    context_limit: int
    warning: str = ""
    usage_raw: dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    elapsed_sec: float = 0.0

    def token_event(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "role": self.role,
            "prompt_est": self.prompt_tokens_est,
            "completion_est": self.completion_tokens_est,
            "total_est": self.total_tokens_est,
            "prompt_actual": self.prompt_tokens_actual,
            "completion_actual": self.completion_tokens_actual,
            "total_actual": self.total_tokens_actual,
            "max_requested": self.max_tokens_requested,
            "max_effective": self.max_tokens_effective,
            "context_limit": self.context_limit,
            "warning": self.warning,
            "elapsed_sec": round(self.elapsed_sec, 3),
        }


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def get_backend() -> str:
    return _backend


def close_backend() -> None:
    if _backend == "acp":
        from acp_client import close_pool
        close_pool()


def get_last_reply() -> LLMReply | None:
    return _last_reply


def consume_last_reply() -> LLMReply | None:
    global _last_reply
    reply = _last_reply
    _last_reply = None
    return reply


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chars_per_token = float(getattr(config, "TOKEN_EST_CHARS_PER_TOKEN", 3.8))
    word_multiplier = float(getattr(config, "TOKEN_EST_WORDS_MULTIPLIER", 1.35))
    by_chars = int((len(text) / max(chars_per_token, 0.1)) + 0.999)
    by_words = int((len(text.split()) * word_multiplier) + 0.999)
    return max(1, by_chars, by_words)


def effective_completion_cap(
    prompt_tokens_est: int,
    requested_max_tokens: int,
    context_limit: int | None = None,
    safety_margin: int | None = None,
) -> tuple[int, str]:
    limit = int(context_limit if context_limit is not None else getattr(config, "LLM_MAX_TOKENS", 200000))
    margin = int(safety_margin if safety_margin is not None else getattr(config, "TOKEN_CONTEXT_SAFETY_MARGIN", 1024))
    requested = max(0, int(requested_max_tokens))
    room = max(0, limit - int(prompt_tokens_est) - max(0, margin))
    effective = min(requested, room)
    min_completion = int(getattr(config, "TOKEN_MIN_COMPLETION", 256))
    if effective < min_completion:
        return effective, f"token admission low room={room} requested={requested} min={min_completion}"
    warn_pct = float(getattr(config, "TOKEN_WARNING_PCT", 0.85))
    used_pct = int(prompt_tokens_est) / max(limit, 1)
    if used_pct >= warn_pct:
        return effective, f"prompt estimate {prompt_tokens_est}/{limit} tokens ({used_pct:.1%})"
    if effective < requested:
        return effective, f"completion cap clamped from {requested} to {effective}"
    return effective, ""


def call_llm(system: str, user: str, role: str, *, max_tokens: int = config.LLM_MAX_TOKENS,
             temperature: float | None = None) -> str:
    return call_llm_reply(system, user, role, max_tokens=max_tokens, temperature=temperature).text


def call_llm_reply(system: str, user: str, role: str, *, max_tokens: int = config.LLM_MAX_TOKENS,
                   temperature: float | None = None) -> LLMReply:
    return _call_llm_reply_with_retry(system, user, role, max_tokens=max_tokens, temperature=temperature)


def _call_llm_reply_with_retry(system: str, user: str, role: str, *, max_tokens: int = config.LLM_MAX_TOKENS,
                               temperature: float | None = None) -> LLMReply:
    global _last_reply
    schema = _load_schema(role)
    prompt_est = _estimate_request_tokens(system, user, schema)
    context_limit = int(getattr(config, "LLM_MAX_TOKENS", 200000))
    effective_max, warning = effective_completion_cap(prompt_est, max_tokens, context_limit)
    min_completion = int(getattr(config, "TOKEN_MIN_COMPLETION", 256))
    if warning:
        log.emit("token_warning", {"role": role, "backend": _backend, "warning": warning,
                                   "prompt_est": prompt_est, "max_effective": effective_max})
    if effective_max < min_completion:
        raise RuntimeError(f"token admission denied: {warning}")

    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "top_p": config.LLM_TOP_P,
        "top_k": config.LLM_TOP_K,
        "max_tokens": effective_max,
        "stream": False,
        "stop": config.LLM_STOP,
        "presence_penalty": config.LLM_PRESENCE_PENALTY,
        "frequency_penalty": config.LLM_FREQUENCY_PENALTY,
        "logit_bias": config.LLM_LOGIT_BIAS,
        "repeat_penalty": config.LLM_REPEAT_PENALTY,
        "seed": config.LLM_SEED,
    }
    if schema:
        body["response_format"] = schema
    started = time.time()
    max_retries = getattr(config, "LLM_RETRY_ATTEMPTS", 3)
    text, usage = "", {}
    for _retry_i in range(max_retries):
        try:
            if _backend == "lmstudio":
                text, usage = _call_lmstudio(body)
            elif _backend == "acp":
                text, usage = _call_acp(body), {}
            else:
                raise ValueError(f"unknown backend: {_backend}")
            break
        except (RuntimeError, ConnectionError, TimeoutError, OSError) as _err:
            log.emit("llm_retry", {"attempt": _retry_i + 1, "error": str(_err)[:200]})
            if _retry_i >= max_retries - 1:
                log.emit("llm_fallback", {"error": str(_err)[:200]})
                text = json.dumps({"mode": "done", "sequence": [], "done_when": "LLM unavailable - fallback"})
                usage = {}
                break
            time.sleep(min(2 ** _retry_i, 10))

    completion_est = estimate_tokens(text)
    usage_prompt, usage_completion, usage_total = _usage_numbers(usage)
    reply = LLMReply(
        text=text,
        backend=_backend,
        role=role,
        prompt_tokens_est=prompt_est,
        completion_tokens_est=completion_est,
        total_tokens_est=prompt_est + completion_est,
        prompt_tokens_actual=usage_prompt,
        completion_tokens_actual=usage_completion,
        total_tokens_actual=usage_total,
        max_tokens_requested=int(max_tokens),
        max_tokens_effective=effective_max,
        context_limit=context_limit,
        warning=warning,
        usage_raw=usage,
        started_at=started,
        elapsed_sec=time.time() - started,
    )
    _last_reply = reply
    if getattr(config, "LOG_TOKEN_USAGE", True):
        log.emit("token_usage", {
            "role": reply.role,
            "total": reply.total_tokens_actual or reply.total_tokens_est,
            "prompt": reply.prompt_tokens_actual or reply.prompt_tokens_est,
            "completion": reply.completion_tokens_actual or reply.completion_tokens_est,
            "ms": int(reply.elapsed_sec * 1000),
        })
    return reply


def _estimate_request_tokens(system: str, user: str, schema: dict[str, Any]) -> int:
    schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":")) if schema else ""
    # Estimate the actual content passed to the backend, including schema instructions.
    return estimate_tokens(system) + estimate_tokens(user) + estimate_tokens(schema_text)


def _usage_numbers(usage: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    if not isinstance(usage, dict) or not usage:
        return None, None, None
    prompt = _as_int(usage.get("prompt_tokens"))
    completion = _as_int(usage.get("completion_tokens"))
    total = _as_int(usage.get("total_tokens"))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return prompt, completion, total


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_schema(role: str) -> dict[str, Any]:
    path = config.SCHEMAS_DIR / f"{role}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def invalidate_host_cache(host: str | None = None) -> None:
    global _cached_host, _cached_model
    if host is None or _cached_host == host.rstrip("/"):
        _cached_host, _cached_model = None, None


def _pick_model(models: list[str]) -> str:
    preferred = str(getattr(config, "LMS_PREFERRED_MODEL", "")).strip().lower()
    if not models:
        return ""
    model_id = models[0]
    if preferred:
        exact = next((m for m in models if m.lower() == preferred), "")
        partial = next((m for m in models if preferred in m.lower()), "")
        model_id = exact or partial or model_id
    return model_id


def _fetch_model_for_host(host: str) -> str | None:
    host = host.rstrip("/")
    try:
        req = Request(f"{host}/v1/models", method="GET")
        with urlopen(req, timeout=config.LMS_MODEL_LIST_TIMEOUT) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        raw_models = data.get("data", [])
        if not isinstance(raw_models, list) or not raw_models:
            return None
        models = [str(cast(dict[str, Any], m).get("id", "")) for m in raw_models if isinstance(m, dict)]
        models = [m for m in models if m]
        return _pick_model(models) or None
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, IndexError):
        return None


def probe_host(host: str) -> str | None:
    """Return loaded model id when host responds, else None."""
    return _fetch_model_for_host(host)


def discover_hosts(hosts: list[str] | None = None) -> list[str]:
    """Hosts that respond to /v1/models, in candidate order."""
    healthy: list[str] = []
    for host in hosts or config.LMS_HOSTS:
        if probe_host(host):
            healthy.append(host.rstrip("/"))
    return healthy


def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host and _cached_model:
        return _cached_host, _cached_model
    for host in config.LMS_HOSTS:
        model_id = _fetch_model_for_host(host)
        if model_id:
            _cached_host, _cached_model = host.rstrip("/"), model_id
            return _cached_host, _cached_model
    raise ConnectionError("no LM Studio host reachable")


def _host_lock_path(host: str) -> Path:
    safe = host.rstrip("/").replace("://", "_").replace(":", "_").replace("/", "_")
    return config.BASE_DIR / "runtime" / f"llm_lock_{safe}.lock"


def _acquire_host_lock(host: str, timeout: float) -> Any:
    """Acquire an advisory per-host lock so only one process talks to the LLM at a time."""
    path = _host_lock_path(host)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR)
    start = time.time()
    while True:
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return fd
        except OSError:
            if time.time() - start > timeout:
                os.close(fd)
                raise TimeoutError(f"could not acquire LLM lock for {host}")
            time.sleep(0.25)


def _release_host_lock(fd: Any) -> None:
    try:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    os.close(fd)


def _call_lmstudio(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    hosts_tried: set[str] = set()
    last_error = "no LM Studio host reachable"
    while len(hosts_tried) < max(1, len(config.LMS_HOSTS)):
        host, model = _resolve_host_model()
        host = host.rstrip("/")
        if host in hosts_tried:
            invalidate_host_cache(host)
            if len(hosts_tried) >= len(config.LMS_HOSTS):
                break
            continue
        activated, changed = config.apply_model_profile(model)
        if changed:
            log.emit("model_profile", {"model": model, "profile": activated})
        hosts_tried.add(host)
        body["model"] = model
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        lock_fd: Any = None
        for attempt in range(config.LMS_REQUEST_ATTEMPTS):
            try:
                lock_fd = _acquire_host_lock(host, timeout=config.LMS_TIMEOUT)
                try:
                    req = Request(
                        f"{host}/v1/chat/completions",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(req, timeout=config.LMS_TIMEOUT) as resp:
                        raw = resp.read().decode("utf-8")
                finally:
                    _release_host_lock(lock_fd)
                    lock_fd = None
            except (HTTPError, URLError, TimeoutError, OSError) as e:
                last_error = str(e)
                if attempt < config.LMS_REQUEST_ATTEMPTS - 1:
                    time.sleep(config.LMS_RETRY_DELAY)
                    continue
                invalidate_host_cache(host)
                break
            result: dict[str, Any] = json.loads(raw)
            choices = result.get("choices")
            if choices and isinstance(choices, list):
                text = str(cast(list[Any], choices)[0]["message"]["content"])
                usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
                return text, cast(dict[str, Any], usage)
            last_error = f"LLM error: {raw[:200]}"
            if attempt < config.LMS_REQUEST_ATTEMPTS - 1:
                invalidate_host_cache(host)
                host, model = _resolve_host_model()
                host = host.rstrip("/")
                body["model"] = model
                payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
                time.sleep(config.LMS_ERROR_RETRY_DELAY)
                continue
            invalidate_host_cache(host)
            break
    raise RuntimeError(last_error)


def _call_acp(body: dict[str, Any]) -> str:
    from acp_client import prompt_once
    msgs: list[dict[str, str]] = body.get("messages", [])
    sys_content = next((m["content"] for m in msgs if m["role"] == "system"), "")
    user_content = next((m["content"] for m in msgs if m["role"] == "user"), "")
    schema: dict[str, Any] = body.get("response_format", {})
    schema_def = json.dumps(schema.get("json_schema", {}).get("schema", {}), indent=2)
    prompt = (
        f"{sys_content}\n\n"
        f"Output ONLY a valid JSON object matching this schema. No other text.\n\nSchema:\n{schema_def}\n\n"
        f"---\n{user_content}\n---\n\n"
        f"Respond with the JSON object only."
    )
    return prompt_once(prompt, timeout=config.ACP_TIMEOUT)
