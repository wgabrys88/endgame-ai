from __future__ import annotations

import json
import urllib.error
import urllib.request


def call(messages, cfg):
    base_url = str(cfg.get("base_url") or "http://localhost:1234").rstrip("/")
    path = str(cfg.get("path") or "/v1/chat/completions")
    url = base_url + path
    payload = {
        "model": cfg.get("model") or "local-model",
        "messages": messages,
        "temperature": cfg.get("temperature", 0.2),
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = "Bearer " + str(cfg["api_key"])
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    timeout = float(cfg.get("timeout") or 60)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"openai transport HTTP {exc.code} from {url}: {err_body}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        msg = str(reason)
        if "10061" in msg or "Connection refused" in msg or "actively refused" in msg:
            raise RuntimeError(
                "openai transport selected, but the OpenAI-compatible server is not reachable at "
                f"{base_url}. On Windows, WinError 10061 usually means LM Studio Local Server "
                "is not running/listening on port 1234. Start LM Studio's local server or "
                "intentionally change wiring.json model.transport. No fallback was attempted. "
                f"Original error: {reason}"
            ) from exc
        raise RuntimeError(f"openai transport URL error calling {url}: {reason}; no fallback was attempted") from exc
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"openai transport returned non-JSON body from {url}: {body[:1000]}") from exc
    choices = obj.get("choices") if isinstance(obj, dict) else None
    if not choices:
        raise RuntimeError(f"openai transport response missing choices: {obj}")
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
    return {"content": content, "reasoning": reasoning, "body": obj}
