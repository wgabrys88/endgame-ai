from __future__ import annotations
import json
import time
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    LMS_HOSTS, LMS_TIMEOUT, ACP_TIMEOUT, LLM_TEMPERATURE,
    LLM_TOP_P, LLM_TOP_K, LLM_REPEAT_PENALTY, LLM_PRESENCE_PENALTY,
    LLM_FREQUENCY_PENALTY, LLM_SEED, LLM_MAX_TOKENS, LLM_STOP, LLM_LOGIT_BIAS,
    SCHEMAS_DIR, LMS_MODEL_LIST_TIMEOUT,
    LMS_REQUEST_ATTEMPTS, LMS_RETRY_DELAY, LMS_ERROR_RETRY_DELAY,
)

__all__ = ["call_llm", "set_backend", "get_backend", "close_backend"]

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def get_backend() -> str:
    return _backend


def close_backend() -> None:
    if _backend == "acp":
        from acp_client import close_pool
        close_pool()


def call_llm(system: str, user: str, role: str, *, max_tokens: int = LLM_MAX_TOKENS, temperature: float | None = None) -> str:
    schema = _load_schema(role)
    temp = temperature if temperature is not None else LLM_TEMPERATURE
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": schema,
        "temperature": temp,
        "top_p": LLM_TOP_P,
        "top_k": LLM_TOP_K,
        "max_tokens": max_tokens,
        "stream": False,
        "stop": LLM_STOP,
        "presence_penalty": LLM_PRESENCE_PENALTY,
        "frequency_penalty": LLM_FREQUENCY_PENALTY,
        "logit_bias": LLM_LOGIT_BIAS,
        "repeat_penalty": LLM_REPEAT_PENALTY,
        "seed": LLM_SEED,
    }
    if _backend == "lmstudio":
        return _call_lmstudio(body)
    if _backend == "acp":
        return _call_acp(body)
    raise ValueError(f"unknown backend: {_backend}")


def _load_schema(role: str) -> dict[str, Any]:
    path = SCHEMAS_DIR / f"{role}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host and _cached_model:
        return _cached_host, _cached_model
    for host in LMS_HOSTS:
        try:
            req = Request(f"{host}/v1/models", method="GET")
            with urlopen(req, timeout=LMS_MODEL_LIST_TIMEOUT) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            if models and isinstance(models, list):
                model_id = str(cast(list[Any], models)[0].get("id", ""))
                if model_id:
                    _cached_host, _cached_model = host, model_id
                    return host, model_id
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, IndexError):
            continue
    raise ConnectionError("no LM Studio host reachable")


def _call_lmstudio(body: dict[str, Any]) -> str:
    global _cached_host, _cached_model
    host, model = _resolve_host_model()
    body["model"] = model
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(LMS_REQUEST_ATTEMPTS):
        try:
            req = Request(f"{host}/v1/chat/completions", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=LMS_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            if attempt < LMS_REQUEST_ATTEMPTS - 1:
                time.sleep(LMS_RETRY_DELAY)
                continue
            raise RuntimeError(str(e)) from e
        result: dict[str, Any] = json.loads(raw)
        choices = result.get("choices")
        if choices and isinstance(choices, list):
            return str(cast(list[Any], choices)[0]["message"]["content"])
        if attempt < LMS_REQUEST_ATTEMPTS - 1:
            _cached_host, _cached_model = None, None
            host, model = _resolve_host_model()
            body["model"] = model
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            time.sleep(LMS_ERROR_RETRY_DELAY)
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
    return prompt_once(prompt, timeout=ACP_TIMEOUT)
