"""LLM backend — LM Studio + ACP. No token admission control (128K context is enough)."""
from __future__ import annotations

import json
import os
import time
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None
_last_reply: str | None = None


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def close_backend() -> None:
    if _backend == "acp":
        from acp_client import close_pool
        close_pool()


def consume_last_reply() -> str | None:
    global _last_reply
    r = _last_reply
    _last_reply = None
    return r


def invalidate_host_cache(host: str | None = None) -> None:
    """No-op — host is resolved once at startup."""
    pass


def probe_host(host: str) -> str | None:
    return _fetch_model(host)


def discover_hosts(hosts: list[str] | None = None) -> list[str]:
    return [h.rstrip("/") for h in (hosts or config.LMS_HOSTS) if _fetch_model(h)]


def call_llm(system: str, user: str, role: str, *, max_tokens: int = 0, temperature: float | None = None) -> str:
    global _last_reply
    schema = _load_schema(role)
    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    body: dict[str, Any] = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temp, "top_p": config.LLM_TOP_P, "top_k": config.LLM_TOP_K,
        "max_tokens": max_tokens or config.BUDGET.get(role, config.LLM_MAX_TOKENS),
        "stream": False, "stop": config.LLM_STOP,
        "presence_penalty": config.LLM_PRESENCE_PENALTY,
        "frequency_penalty": config.LLM_FREQUENCY_PENALTY,
        "logit_bias": config.LLM_LOGIT_BIAS,
        "repeat_penalty": config.LLM_REPEAT_PENALTY,
        "seed": config.LLM_SEED,
    }
    if schema:
        body["response_format"] = schema

    for attempt in range(3):
        try:
            match _backend:
                case "lmstudio":
                    text = _call_lmstudio(body)
                case "acp":
                    text = _call_acp(body)
                case _:
                    raise ValueError(f"unknown backend: {_backend}")
            _last_reply = text
            return text
        except (RuntimeError, ConnectionError, TimeoutError, OSError) as err:
            log.emit("llm_retry", {"attempt": attempt + 1, "error": str(err)[:200]})
            if attempt >= 2:
                log.emit("llm_fallback", {"error": str(err)[:200]})
                text = json.dumps({"mode": "done", "sequence": [], "done_when": "LLM unavailable"})
                _last_reply = text
                return text
            time.sleep(min(2 ** attempt, 10))
    return ""


# --- LM Studio ---

def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host is not None:
        return _cached_host, _cached_model or ""
    # Resolve once — never re-probe
    for host in config.LMS_HOSTS:
        model = _fetch_model(host)
        if model:
            _cached_host, _cached_model = host.rstrip("/"), model
            return _cached_host, _cached_model
    # Host configured but model list failed — use it anyway (LM Studio may not have loaded yet)
    _cached_host = config.LMS_HOSTS[0].rstrip("/") if config.LMS_HOSTS else ""
    _cached_model = ""
    return _cached_host, _cached_model


def _fetch_model(host: str) -> str | None:
    host = host.rstrip("/")
    try:
        req = Request(f"{host}/v1/models", method="GET")
        with urlopen(req, timeout=config.LMS_MODEL_LIST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [str(m.get("id", "")) for m in data.get("data", []) if isinstance(m, dict)]
        models = [m for m in models if m]
        if not models:
            return None
        pref = config.LMS_PREFERRED_MODEL.lower()
        return next((m for m in models if m.lower() == pref), None) or next((m for m in models if pref in m.lower()), None) or models[0]
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _call_lmstudio(body: dict[str, Any]) -> str:
    last_err = "no host"
    host, model = _resolve_host_model()
    if model:
        body["model"] = model
        if not config.active_model_profile():
            activated, changed = config.apply_model_profile(model)
            if changed:
                log.emit("model_profile", {"model": model, "profile": activated})
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for i in range(config.LMS_REQUEST_ATTEMPTS):
        try:
            req = Request(f"{host}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=config.LMS_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices")
            if choices and isinstance(choices, list):
                return str(choices[0]["message"]["content"])
            last_err = f"no choices: {str(result)[:200]}"
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            last_err = str(e)
            if i < config.LMS_REQUEST_ATTEMPTS - 1:
                time.sleep(config.LMS_RETRY_DELAY)
    raise RuntimeError(last_err)


# --- ACP (sequential — one call at a time across all agent processes) ---

_acp_lock_path = config.BASE_DIR / ".acp.lock"


def _call_acp(body: dict[str, Any]) -> str:
    import msvcrt
    from acp_client import prompt_once
    msgs = body.get("messages", [])
    sys_c = next((m["content"] for m in msgs if m["role"] == "system"), "")
    usr_c = next((m["content"] for m in msgs if m["role"] == "user"), "")
    schema = body.get("response_format", {})
    schema_def = json.dumps(schema.get("json_schema", {}).get("schema", {}), indent=2) if schema else "{}"
    prompt = f"{sys_c}\n\nOutput ONLY valid JSON matching:\n{schema_def}\n\n---\n{usr_c}\n---\nJSON only."
    # Cross-process sequential lock — only one ACP call at a time
    _acp_lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(_acp_lock_path, "a+") as lf:
        while True:
            try:
                msvcrt.locking(lf.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except (OSError, IOError):
                time.sleep(0.5 + (hash(os.getpid()) % 10) * 0.1)
        try:
            return prompt_once(prompt, timeout=config.ACP_TIMEOUT)
        finally:
            try:
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
            except (OSError, IOError):
                pass


def _load_schema(role: str) -> dict[str, Any]:
    path = config.SCHEMAS_DIR / f"{role}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
