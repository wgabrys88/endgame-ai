from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

__all__ = [
    "LLMReply", "call_llm", "call_llm_reply", "estimate_tokens",
    "effective_completion_cap", "set_backend", "get_backend", "close_backend",
    "get_last_reply", "consume_last_reply",
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
        "response_format": schema,
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
    started = time.time()
    if _backend == "lmstudio":
        text, usage = _call_lmstudio(body)
    elif _backend == "acp":
        text, usage = _call_acp(body), {}
    else:
        raise ValueError(f"unknown backend: {_backend}")

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
    log.emit("token_usage", reply.token_event())
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


def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host and _cached_model:
        return _cached_host, _cached_model
    preferred = str(getattr(config, "LMS_PREFERRED_MODEL", "")).strip().lower()
    for host in config.LMS_HOSTS:
        try:
            req = Request(f"{host}/v1/models", method="GET")
            with urlopen(req, timeout=config.LMS_MODEL_LIST_TIMEOUT) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            raw_models = data.get("data", [])
            if not isinstance(raw_models, list) or not raw_models:
                continue
            models = [str(cast(dict[str, Any], m).get("id", "")) for m in raw_models if isinstance(m, dict)]
            models = [m for m in models if m]
            if not models:
                continue
            model_id = models[0]
            if preferred:
                exact = next((m for m in models if m.lower() == preferred), "")
                partial = next((m for m in models if preferred in m.lower()), "")
                model_id = exact or partial or model_id
            _cached_host, _cached_model = host, model_id
            return host, model_id
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, IndexError):
            continue
    raise ConnectionError("no LM Studio host reachable")


def _call_lmstudio(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    global _cached_host, _cached_model
    host, model = _resolve_host_model()
    body["model"] = model
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(config.LMS_REQUEST_ATTEMPTS):
        try:
            req = Request(f"{host}/v1/chat/completions", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=config.LMS_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            if attempt < config.LMS_REQUEST_ATTEMPTS - 1:
                time.sleep(config.LMS_RETRY_DELAY)
                continue
            raise RuntimeError(str(e)) from e
        result: dict[str, Any] = json.loads(raw)
        choices = result.get("choices")
        if choices and isinstance(choices, list):
            text = str(cast(list[Any], choices)[0]["message"]["content"])
            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            return text, cast(dict[str, Any], usage)
        if attempt < config.LMS_REQUEST_ATTEMPTS - 1:
            _cached_host, _cached_model = None, None
            host, model = _resolve_host_model()
            body["model"] = model
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            time.sleep(config.LMS_ERROR_RETRY_DELAY)
            continue
        raise RuntimeError(f"LLM error: {raw}")
    raise RuntimeError("LLM call failed after retries")


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
