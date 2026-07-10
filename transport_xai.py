import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


def call(messages, cfg):
    api_key = os.environ.get("XAI_API_KEY") or cfg.get("api_key")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = {
        "model": str(cfg["model"]),
        "input": [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages if m.get("role", "user") in {"system", "user", "assistant"}],
        "temperature": cfg.get("temperature", 0.2),
        "truncation": str(cfg.get("truncation") or "disabled"),
    }
    if cfg.get("prompt_cache_key"):
        payload["prompt_cache_key"] = str(cfg["prompt_cache_key"])
    if "store" in cfg:
        payload["store"] = bool(cfg["store"])
    if isinstance(cfg.get("metadata"), dict):
        payload["metadata"] = cfg["metadata"]
    if cfg.get("max_output_tokens") is not None:
        payload["max_output_tokens"] = int(cfg["max_output_tokens"])
    if isinstance(cfg.get("include"), list):
        payload["include"] = list(cfg["include"])
    fmt = cfg.get("response_format")
    if isinstance(fmt, dict):
        if str(fmt.get("type", "json_schema")) == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        else:
            payload["text"] = {"format": {"type": fmt.get("type", "json_schema"), "name": fmt.get("name", "record"), "schema": fmt.get("schema", {}), "strict": bool(fmt.get("strict", True))}}
    reasoning_cfg = cfg.get("reasoning") or {}
    effort = cfg.get("reasoning_effort") or reasoning_cfg.get("effort")
    if effort or str(cfg["model"]).startswith("grok-4.3"):
        payload["reasoning"] = {"effort": str(effort or ("low" if reasoning_cfg.get("enabled") else "none"))}
    web = cfg.get("web_search") or {}
    if isinstance(web, dict) and web.get("enabled"):
        tool: dict[str, Any] = {"type": "web_search"}
        if web.get("allowed_domains"):
            tool["filters"] = {"allowed_domains": list(web["allowed_domains"])}
        elif web.get("excluded_domains"):
            tool["filters"] = {"excluded_domains": list(web["excluded_domains"])}
        payload["tools"] = [tool]
    max_retries = int(cfg.get("max_retries", 3))
    base_delay = float(cfg.get("retry_base_delay", 1.0))
    for attempt in range(max_retries):
        req = urllib.request.Request(str(cfg["url"]), data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=float(cfg.get("timeout") or 120)) as resp:
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
    # Final fallback to file_proxy if configured
    if cfg.get("fallback_to_file_proxy"):
        raise RuntimeError("xai transport exhausted retries; falling back to file_proxy (caller must handle)")
    raise RuntimeError("xai transport exhausted retries")