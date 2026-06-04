from __future__ import annotations
import json
import subprocess
import time
from typing import Any

from config import (LMS_HOSTS, LMS_TIMEOUT, ACP_TIMEOUT, LLM_TEMPERATURE,
                    LLM_TOP_P, LLM_MAX_TOKENS, SCHEMAS_DIR)

__all__ = ["call_llm", "set_backend", "get_backend"]

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def get_backend() -> str:
    return _backend


def call_llm(system: str, user: str, role: str, *, max_tokens: int = LLM_MAX_TOKENS) -> str:
    schema: dict[str, Any] = _load_schema(role)
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": schema,
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
        "max_tokens": max_tokens,
        "stream": False,
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
    if _cached_host is not None and _cached_model is not None:
        return _cached_host, _cached_model
    for host in LMS_HOSTS:
        try:
            r = subprocess.run(
                ["curl.exe", "-s", "--max-time", "3", f"{host}/v1/models"],
                capture_output=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                data: dict[str, Any] = json.loads(r.stdout)
                if data.get("data"):
                    model_id: str = data["data"][0]["id"]
                    _cached_host = host
                    _cached_model = model_id
                    return host, model_id
                _try_reload_model(host)
                r2 = subprocess.run(
                    ["curl.exe", "-s", "--max-time", "30", f"{host}/v1/models"],
                    capture_output=True, timeout=35)
                if r2.returncode == 0 and r2.stdout.strip():
                    data2: dict[str, Any] = json.loads(r2.stdout)
                    if data2.get("data"):
                        model_id2: str = data2["data"][0]["id"]
                        _cached_host = host
                        _cached_model = model_id2
                        return host, model_id2
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, KeyError, IndexError):
            continue
    raise ConnectionError("no LM Studio host reachable")


def _try_reload_model(host: str) -> None:
    subprocess.run(["lms", "load", _cached_model or "gemma-4-e2b-it"], capture_output=True, timeout=60)
    time.sleep(5)


def _call_lmstudio(body: dict[str, Any]) -> str:
    global _cached_host, _cached_model
    host, model = _resolve_host_model()
    body["model"] = model
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        proc = subprocess.Popen(
            ["curl.exe", "-sN", "-X", "POST", f"{host}/v1/chat/completions",
             "-H", "Content-Type: application/json", "-d", "@-",
             "--max-time", str(LMS_TIMEOUT)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        assert proc.stdout is not None
        assert proc.stderr is not None
        proc.stdin.write(payload)
        proc.stdin.close()
        while proc.poll() is None:
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        stdout_bytes = proc.stdout.read()
        stderr_bytes = proc.stderr.read()
        proc.stdout.close()
        proc.stderr.close()
        if proc.returncode != 0:
            if attempt < 2:
                time.sleep(2)
                continue
            raise RuntimeError(f"curl failed: {stderr_bytes.decode()}")
        raw = stdout_bytes.decode("utf-8")
        if not raw.strip():
            if attempt < 2:
                time.sleep(2)
                continue
            raise ValueError("empty LLM response")
        result: dict[str, Any] = json.loads(raw)
        if "choices" not in result or not result["choices"]:
            error_msg: str = result.get("error", {}).get("message", str(result))
            if "no models loaded" in error_msg.lower() or "No models loaded" in error_msg:
                _cached_host = None
                _cached_model = None
                if attempt < 2:
                    _try_reload_model(host)
                    host, model = _resolve_host_model()
                    body["model"] = model
                    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
                    continue
            if attempt < 2:
                time.sleep(3)
                continue
            raise RuntimeError(f"LLM error: {error_msg}")
        return result["choices"][0]["message"]["content"]
    raise RuntimeError("LLM call failed after 3 attempts")


def _call_acp(body: dict[str, Any]) -> str:
    from acp_client import prompt_once
    msgs: list[dict[str, str]] = body.get("messages", [])
    sys_content: str = next((m["content"] for m in msgs if m["role"] == "system"), "")
    user_content: str = next((m["content"] for m in msgs if m["role"] == "user"), "")
    schema: dict[str, Any] = body.get("response_format", {})
    schema_def: str = json.dumps(schema.get("json_schema", {}).get("schema", {}), indent=2)
    prompt = (
        f"{sys_content}\n\n"
        f"Output ONLY a valid JSON object matching this schema. No other text.\n\nSchema:\n{schema_def}\n\n"
        f"---\n{user_content}\n---\n\n"
        f"Respond with the JSON object only."
    )
    return prompt_once(prompt, timeout=ACP_TIMEOUT)
