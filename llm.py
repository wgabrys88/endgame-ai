from __future__ import annotations
from config import ZERO_INT, ONE_INT, TWO_INT
import json
import subprocess
import time
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (LMS_HOSTS, LMS_TIMEOUT, ACP_TIMEOUT, LLM_TEMPERATURE,
                    LLM_TOP_P, LLM_TOP_K, LLM_REPEAT_PENALTY, LLM_PRESENCE_PENALTY,
                    LLM_FREQUENCY_PENALTY, LLM_SEED, LLM_MAX_TOKENS, LLM_STOP, LLM_LOGIT_BIAS, SCHEMAS_DIR,
                    LOG_NO_ITERATION, LMS_MODEL_LIST_TIMEOUT, LMS_MODEL_RELOAD_TIMEOUT,
                    LMS_MODEL_RELOAD_DELAY, LMS_REQUEST_ATTEMPTS, LMS_RETRY_DELAY,
                    LMS_ERROR_RETRY_DELAY, HTTP_ERROR_STATUS_MIN)
from log import log

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


def call_llm(system: str, user: str, role: str, *, max_tokens: int = LLM_MAX_TOKENS, iteration: int = LOG_NO_ITERATION, context_ref: dict[str, Any] | None = None) -> str:
    schema: dict[str, Any] = _load_schema(role)
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": schema,
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
        "top_k": LLM_TOP_K,
        "max_tokens": max_tokens,
        "stream": False,
        "stop": LLM_STOP,
        "presence_penalty": LLM_PRESENCE_PENALTY,
        "frequency_penalty": LLM_FREQUENCY_PENALTY,
        "logit_bias": LLM_LOGIT_BIAS,
        "repeat_penalty": LLM_REPEAT_PENALTY,
        "seed": LLM_SEED if LLM_SEED is not None else None,
    }
    if _backend == "lmstudio":
        return _call_lmstudio(body, role, iteration, context_ref)
    if _backend == "acp":
        return _call_acp(body, role, iteration, context_ref)
    raise ValueError(f"unknown backend: {_backend}")


def _load_schema(role: str) -> dict[str, Any]:
    path = SCHEMAS_DIR / f"{role}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _http_json(url: str, timeout: float) -> dict[str, Any]:
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"http {e.code}: {body}") from e
    except (URLError, TimeoutError, OSError) as e:
        raise RuntimeError(str(e)) from e
    parsed: object = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(raw)
    return cast(dict[str, Any], parsed)


def _http_post_json(url: str, payload: bytes, timeout: float) -> tuple[str, int]:
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = response.getcode()
    except HTTPError as e:
        raw = e.read().decode("utf-8")
        return raw, e.code
    except (URLError, TimeoutError, OSError) as e:
        raise RuntimeError(str(e)) from e
    return raw, status


def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host is not None and _cached_model is not None:
        return _cached_host, _cached_model
    for host in LMS_HOSTS:
        try:
            data = _http_json(f"{host}/v1/models", LMS_MODEL_LIST_TIMEOUT)
            model_id = _first_model_id(data)
            if model_id:
                _cached_host = host
                _cached_model = model_id
                return host, model_id
            _try_reload_model(host)
            data2 = _http_json(f"{host}/v1/models", LMS_MODEL_LIST_TIMEOUT)
            model_id2 = _first_model_id(data2)
            if model_id2:
                _cached_host = host
                _cached_model = model_id2
                return host, model_id2
        except (RuntimeError, OSError, json.JSONDecodeError, KeyError, IndexError, ValueError):
            continue
    raise ConnectionError("no LM Studio host reachable")


def _first_model_id(data: dict[str, Any]) -> str:
    models = data.get("data")
    if not isinstance(models, list):
        return ""
    if not models:
        return ""
    first = cast(list[Any], models)[ZERO_INT]
    if not isinstance(first, dict):
        return ""
    model_id = cast(dict[str, Any], first).get("id")
    if not isinstance(model_id, str):
        return ""
    return model_id


def _try_reload_model(host: str) -> None:
    subprocess.run(["lms", "load", _cached_model or "gemma-4-e2b-it"], capture_output=True, timeout=LMS_MODEL_RELOAD_TIMEOUT)
    time.sleep(LMS_MODEL_RELOAD_DELAY)


def _call_lmstudio(body: dict[str, Any], role: str, iteration: int, context_ref: dict[str, Any] | None) -> str:
    global _cached_host, _cached_model
    host, model = _resolve_host_model()
    body["model"] = model
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(LMS_REQUEST_ATTEMPTS):
        request_log: dict[str, Any] = {"role": role, "attempt": attempt, "host": host, "model": model, "max_tokens": body.get("max_tokens"), "temperature": body.get("temperature")}
        if context_ref is not None:
            request_log["context"] = context_ref
        log(iteration, "llm.request", "lmstudio chat completion request", request_log)
        try:
            raw, status = _http_post_json(f"{host}/v1/chat/completions", payload, LMS_TIMEOUT)
        except RuntimeError as e:
            log(iteration, "llm.transport.error", "lmstudio http failure", {"role": role, "attempt": attempt, "error": str(e)})
            if attempt < LMS_REQUEST_ATTEMPTS - ONE_INT:
                time.sleep(LMS_RETRY_DELAY)
                continue
            raise
        response_log: dict[str, Any] = {"role": role, "attempt": attempt, "status": status, "body_chars": len(raw)}
        if status < HTTP_ERROR_STATUS_MIN:
            try:
                parsed_preview: dict[str, Any] = json.loads(raw)
                usage = parsed_preview.get("usage", {})
                if isinstance(usage, dict):
                    response_log["usage"] = usage
            except json.JSONDecodeError:
                pass
        else:
            response_log["body"] = raw
        log(iteration, "llm.response.raw", "lmstudio raw response", response_log)
        if status >= HTTP_ERROR_STATUS_MIN:
            if attempt < LMS_REQUEST_ATTEMPTS - ONE_INT:
                time.sleep(LMS_ERROR_RETRY_DELAY)
                continue
            raise RuntimeError(f"LM Studio HTTP {status}: {raw}")
        if not raw.strip():
            if attempt < LMS_REQUEST_ATTEMPTS - ONE_INT:
                time.sleep(LMS_RETRY_DELAY)
                continue
            raise ValueError("empty LLM response")
        result: dict[str, Any] = json.loads(raw)
        log(iteration, "llm.response.parsed", "lmstudio parsed response", {"role": role, "attempt": attempt, "response": result})
        if "choices" not in result or not result["choices"]:
            err_raw = result.get("error", result)
            if isinstance(err_raw, dict):
                err_dict = cast(dict[str, Any], err_raw)
                error_msg = str(err_dict.get("message", err_raw))
            else:
                error_msg = str(err_raw)
            if "no models loaded" in error_msg.lower() or "No models loaded" in error_msg:
                _cached_host = None
                _cached_model = None
                if attempt < LMS_REQUEST_ATTEMPTS - ONE_INT:
                    _try_reload_model(host)
                    host, model = _resolve_host_model()
                    body["model"] = model
                    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
                    continue
            if attempt < LMS_REQUEST_ATTEMPTS - ONE_INT:
                time.sleep(LMS_ERROR_RETRY_DELAY)
                continue
            raise RuntimeError(f"LLM error: {error_msg}")
        return result["choices"][ZERO_INT]["message"]["content"]
    raise RuntimeError("LLM call failed after 3 attempts")


def _call_acp(body: dict[str, Any], role: str, iteration: int, context_ref: dict[str, Any] | None) -> str:
    from acp_client import prompt_once
    msgs: list[dict[str, str]] = body.get("messages", [])
    sys_content: str = next((m["content"] for m in msgs if m["role"] == "system"), "")
    user_content: str = next((m["content"] for m in msgs if m["role"] == "user"), "")
    schema: dict[str, Any] = body.get("response_format", {})
    schema_def: str = json.dumps(schema.get("json_schema", {}).get("schema", {}), indent=TWO_INT)
    prompt = (
        f"{sys_content}\n\n"
        f"Output ONLY a valid JSON object matching this schema. No other text.\n\nSchema:\n{schema_def}\n\n"
        f"---\n{user_content}\n---\n\n"
        f"Respond with the JSON object only."
    )
    request_log: dict[str, Any] = {"role": role, "prompt_chars": len(prompt)}
    if context_ref is not None:
        request_log["context"] = context_ref
    log(iteration, "llm.request", "acp prompt request", request_log)
    response = prompt_once(prompt, timeout=ACP_TIMEOUT)
    log(iteration, "llm.response.raw", "acp raw response", {"role": role, "response": response})
    return response
