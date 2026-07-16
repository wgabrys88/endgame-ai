import json
import os
import time
import urllib.error
import urllib.request

import core_bus as bus


def _build_body(cfg, messages, body_override, response_format):
    """The grok request body is wiring's transport_config.request, verbatim: the single
    source of truth. Per-call overrides (organ tuning, prompt_cache_key) are laid over it,
    the dynamic fields (input, text, tools) are filled, and every null-valued key — a
    field catalogued as available but not sent — is dropped before the wire."""
    body = bus.deep_merge(cfg["request"], body_override or {})
    body["input"] = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if m.get("role", "user") in {"system", "user", "assistant"}
    ]
    if isinstance(response_format, dict):
        if str(response_format.get("type", "json_schema")) == "json_object":
            body["text"] = {"format": {"type": "json_object"}}
        else:
            body["text"] = {"format": {
                "type": response_format.get("type", "json_schema"),
                "name": response_format.get("name", "record"),
                "schema": response_format.get("schema", {}),
                "strict": bool(response_format.get("strict", True)),
            }}
    web = cfg.get("web_search") or {}
    if isinstance(web, dict) and web.get("enabled"):
        tool = {"type": "web_search"}
        if web.get("allowed_domains"):
            tool["filters"] = {"allowed_domains": list(web["allowed_domains"])}
        elif web.get("excluded_domains"):
            tool["filters"] = {"excluded_domains": list(web["excluded_domains"])}
        body["tools"] = [tool]
    return bus.drop_nulls(body)


def call(messages, cfg, *, body_override=None, response_format=None):
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = _build_body(cfg, messages, body_override, response_format)
    url = str(cfg["url"])
    timeout = float(cfg["timeout"])
    max_retries = int(cfg["max_retries"])
    base_delay = float(cfg["retry_base_delay"])
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                obj = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = obj.get("output_text") or ""
            reasoning = ""
            if not content and isinstance(obj.get("output"), list):
                parts = []
                for item in obj["output"]:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "reasoning":
                        reasoning += "\n".join(str(c["text"]) for c in item.get("content", []) or [] if isinstance(c, dict) and c.get("text"))
                    else:
                        parts.extend(str(c["text"]) for c in item.get("content", []) or [] if isinstance(c, dict) and c.get("text"))
                content = "\n".join(parts)
            response_meta = {key: obj[key] for key in ("id", "model", "created_at", "completed_at", "status", "service_tier") if key in obj}
            return {"content": content, "reasoning": reasoning.strip(), "usage": obj.get("usage", {}), "response_meta": response_meta}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 503 and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise RuntimeError(f"xai transport HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise RuntimeError(f"xai transport URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc
    raise RuntimeError("xai transport exhausted retries")
