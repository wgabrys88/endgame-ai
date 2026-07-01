from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def call(messages, cfg):
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("xai_responses selected but XAI_API_KEY is missing; no fallback was attempted")
    url = str(cfg.get("url") or "https://api.x.ai/v1/responses")
    text = "\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in messages)
    payload = {"model": cfg.get("model") or "grok-4", "input": text}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(cfg.get("timeout") or 60)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"xai_responses HTTP {exc.code}: {err}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"xai_responses URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc
    obj = json.loads(body)
    content = obj.get("output_text") or ""
    if not content and isinstance(obj.get("output"), list):
        parts = []
        for item in obj["output"]:
            if isinstance(item, dict):
                for c in item.get("content", []) or []:
                    if isinstance(c, dict) and c.get("text"):
                        parts.append(str(c["text"]))
        content = "\n".join(parts)
    return {"content": content, "reasoning": "", "body": obj}
