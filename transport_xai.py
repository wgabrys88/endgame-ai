"""[transport_xai] — Thou shalt serialize wiring's request unto POST /v1/responses."""
import json
import os
import urllib.error
import urllib.request

import core_bus as bus


def _build_body(cfg, messages, body_override, response_format):
    """The body is wiring's [request] base, laid over by the caller's [body_override]
    (an organ tuning), with the dynamic fields filled and every null-valued key
    dropped. Null in an override explicitly unsets a base field."""
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
    return bus.drop_nulls(body)


def call(messages, cfg, *, body_override=None, response_format=None):
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = _build_body(cfg, messages, body_override, response_format)
    url = str(cfg["url"])
    timeout = float(cfg["timeout"])
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
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
        return {"content": content, "reasoning": reasoning.strip()}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"xai transport HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"xai transport URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc
