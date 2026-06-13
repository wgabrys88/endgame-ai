from __future__ import annotations

import json
import time
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

__all__ = [
    "call_llm", "set_backend", "close_backend",
    "consume_last_reply", "probe_host", "discover_hosts", "invalidate_host_cache",
]

_cached_host: str | None = None
_cached_model: str | None = None
_last_reply: Any = None


def set_backend(name: str) -> None:
    pass


def close_backend() -> None:
    pass


def consume_last_reply() -> Any:
    global _last_reply
    r = _last_reply
    _last_reply = None
    return r


def invalidate_host_cache(host: str | None = None) -> None:
    global _cached_host, _cached_model
    if host is None or _cached_host == host.rstrip("/"):
        _cached_host, _cached_model = None, None


def probe_host(host: str) -> str | None:
    return _fetch_model_for_host(host)


def discover_hosts(hosts: list[str] | None = None) -> list[str]:
    return [h.rstrip("/") for h in (hosts or config.LMS_HOSTS) if probe_host(h)]


def call_llm(system: str, user: str, role: str, *, max_tokens: int = 0,
             temperature: float | None = None) -> str:
    global _last_reply
    if max_tokens <= 0:
        max_tokens = config.BUDGET_PLANNER_OUT
    schema = _load_schema(role)
    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "top_p": config.LLM_TOP_P,
        "top_k": config.LLM_TOP_K,
        "max_tokens": max_tokens,
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
    text = ""
    for attempt in range(config.LMS_REQUEST_ATTEMPTS):
        try:
            text, usage = _call_lmstudio(body)
            break
        except (RuntimeError, ConnectionError, TimeoutError, OSError) as err:
            log.emit("llm_retry", {"attempt": attempt + 1, "error": str(err)[:200]})
            if attempt >= config.LMS_REQUEST_ATTEMPTS - 1:
                log.emit("llm_fallback", {"error": str(err)[:200]})
                text = json.dumps({"mode": "done", "sequence": [], "done_when": "LLM unavailable"})
                break
            time.sleep(min(2 ** attempt, 10))

    elapsed = time.time() - started
    _last_reply = {"role": role, "elapsed": elapsed}
    if getattr(config, "LOG_TOKEN_USAGE", True):
        log.emit("token_usage", {"role": role, "ms": int(elapsed * 1000)})
    return text


# --- LM Studio internals ---

def _fetch_model_for_host(host: str) -> str | None:
    host = host.rstrip("/")
    try:
        req = Request(f"{host}/v1/models", method="GET")
        with urlopen(req, timeout=config.LMS_MODEL_LIST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [str(m.get("id", "")) for m in data.get("data", []) if isinstance(m, dict)]
        models = [m for m in models if m]
        if not models:
            return None
        preferred = config.LMS_PREFERRED_MODEL.lower()
        if preferred:
            match = next((m for m in models if m.lower() == preferred), None) or next((m for m in models if preferred in m.lower()), None)
            return match or models[0]
        return models[0]
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


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
        hosts_tried.add(host)
        body["model"] = model
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        for attempt in range(config.LMS_REQUEST_ATTEMPTS):
            try:
                req = Request(f"{host}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(req, timeout=config.LMS_TIMEOUT) as resp:
                    raw = resp.read().decode("utf-8")
            except (HTTPError, URLError, TimeoutError, OSError) as e:
                last_error = str(e)
                if attempt < config.LMS_REQUEST_ATTEMPTS - 1:
                    time.sleep(config.LMS_RETRY_DELAY)
                    continue
                invalidate_host_cache(host)
                break
            result = json.loads(raw)
            choices = result.get("choices")
            if choices and isinstance(choices, list):
                text = str(choices[0]["message"]["content"])
                usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
                return text, usage
            last_error = f"LLM error: {raw[:200]}"
            invalidate_host_cache(host)
            break
    raise RuntimeError(last_error)


def _load_schema(role: str) -> dict[str, Any]:
    path = config.SCHEMAS_DIR / f"{role}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
