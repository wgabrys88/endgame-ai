import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_logs")
_PAIRS_PER_FILE = 4


def _current_log_file() -> str:
    os.makedirs(_LOG_DIR, exist_ok=True)
    existing = sorted(f for f in os.listdir(_LOG_DIR) if re.fullmatch(r"llm_\d{6}\.txt", f))
    if existing:
        latest = os.path.join(_LOG_DIR, existing[-1])
        pairs = sum(1 for _ in open(latest, encoding="utf-8") if _.startswith("=== RESPONSE"))
        if pairs < _PAIRS_PER_FILE:
            return latest
        return os.path.join(_LOG_DIR, f"llm_{int(existing[-1][4:10]) + 1:06d}.txt")
    return os.path.join(_LOG_DIR, "llm_000001.txt")


def _log_block(kind: str, obj: Any) -> None:
    path = _current_log_file()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"=== {kind} @ {stamp} ===\n")
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
        fh.write("\n\n")


def call(messages, cfg):
    api_key = os.environ.get("XAI_API_KEY") or cfg.get("api_key")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = {
        "model": str(cfg["model"]),
        "input": [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages if m.get("role", "user") in {"system", "user", "assistant"}],
        "temperature": cfg.get("temperature", 0.2),
        "truncation": str(cfg.get("truncation") or "disabled"),
        "store": True,
    }
    if cfg.get("prompt_cache_key"):
        payload["prompt_cache_key"] = str(cfg["prompt_cache_key"])
    if cfg.get("max_output_tokens") is not None:
        payload["max_output_tokens"] = int(cfg["max_output_tokens"])
    fmt = cfg.get("response_format")
    if isinstance(fmt, dict):
        if str(fmt.get("type", "json_schema")) == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        else:
            payload["text"] = {"format": {"type": fmt.get("type", "json_schema"), "name": fmt.get("name", "record"), "schema": fmt.get("schema", {}), "strict": bool(fmt.get("strict", True))}}
    reasoning_cfg = cfg.get("reasoning") or {}
    payload["reasoning"] = {"effort": str(cfg.get("reasoning_effort") or reasoning_cfg.get("effort") or "high")}
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
    _log_block("REQUEST", payload)
    for attempt in range(max_retries):
        req = urllib.request.Request(str(cfg["url"]), data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=float(cfg.get("timeout") or 120)) as resp:
                obj = json.loads(resp.read().decode("utf-8", errors="replace"))
            _log_block("RESPONSE", obj)
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