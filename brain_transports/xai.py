from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import urllib.error
import urllib.request


def _resolve_executable(value):
    raw = os.path.expandvars(os.path.expanduser(str(value or "grok")))
    p = pathlib.Path(raw)
    if p.exists():
        return str(p)
    found = shutil.which(raw)
    if found:
        return found
    raise RuntimeError(f"grok executable missing: {raw}; no fallback was attempted")


def call(messages, cfg):
    """Unified xAI transport supporting:
    - mode="api": xAI Responses API (default, uses grok-build-0.1 or grok-4)
    - mode="cli": grok CLI headless (grok -p --output-format json)
    """
    mode = cfg.get("mode", "api")
    
    if mode == "cli":
        return _call_cli(messages, cfg)
    else:
        return _call_api(messages, cfg)


def _call_api(messages, cfg):
    """Call xAI Responses API at https://api.x.ai/v1/responses"""
    api_key = os.environ.get("XAI_API_KEY") or cfg.get("api_key")
    if not api_key:
        raise RuntimeError("xai transport (api mode): XAI_API_KEY missing; no fallback was attempted")
    
    url = str(cfg.get("url") or "https://api.x.ai/v1/responses")
    model = str(cfg.get("model") or "grok-build-0.1")
    
    # Convert messages to input format
    input_data = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            input_data.append({"role": "system", "content": content})
        elif role == "user":
            input_data.append({"role": "user", "content": content})
        elif role == "assistant":
            input_data.append({"role": "assistant", "content": content})
    
    payload = {
        "model": model,
        "input": input_data,
        "temperature": cfg.get("temperature", 0.2),
        "truncation": str(cfg.get("truncation") or "disabled"),
    }
    if cfg.get("top_p") is not None:
        payload["top_p"] = float(cfg["top_p"])
    if cfg.get("parallel_tool_calls") is not None:
        payload["parallel_tool_calls"] = bool(cfg["parallel_tool_calls"])
    if cfg.get("tool_choice") is not None:
        payload["tool_choice"] = cfg["tool_choice"]
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
    response_format = cfg.get("response_format")
    if isinstance(response_format, dict):
        fmt_type = str(response_format.get("type", "json_schema"))
        if fmt_type == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        else:
            payload["text"] = {
                "format": {
                    "type": fmt_type,
                    "name": response_format.get("name", "record"),
                    "schema": response_format.get("schema", {}),
                    "strict": bool(response_format.get("strict", True)),
                }
            }

    reasoning_cfg = cfg.get("reasoning") or {}
    effort = cfg.get("reasoning_effort") or reasoning_cfg.get("effort")
    if effort or model.startswith("grok-4.3"):
        payload["reasoning"] = {"effort": str(effort or ("low" if reasoning_cfg.get("enabled") else "none"))}

    web_search_cfg = cfg.get("web_search") or {}
    if isinstance(web_search_cfg, dict) and web_search_cfg.get("enabled"):
        tool = {"type": "web_search"}
        allowed = web_search_cfg.get("allowed_domains")
        excluded = web_search_cfg.get("excluded_domains")
        if allowed:
            domains = [str(item) for item in allowed][:5]
            tool["filters"] = {"allowed_domains": domains}
        elif excluded:
            domains = [str(item) for item in excluded][:5]
            tool["filters"] = {"excluded_domains": domains}
        if web_search_cfg.get("enable_image_understanding") is not None:
            tool["enable_image_understanding"] = bool(web_search_cfg.get("enable_image_understanding"))
        if web_search_cfg.get("enable_image_search") is not None:
            tool["enable_image_search"] = bool(web_search_cfg.get("enable_image_search"))
        payload["tools"] = [tool]
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    
    timeout = float(cfg.get("timeout") or 120)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"xai transport (api) HTTP {exc.code}: {err}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"xai transport (api) URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc
    
    obj = json.loads(body)
    content = obj.get("output_text") or ""
    reasoning = ""
    if not content and isinstance(obj.get("output"), list):
        parts = []
        for item in obj["output"]:
            if isinstance(item, dict):
                if item.get("type") == "reasoning":
                    for c in item.get("content", []) or []:
                        if isinstance(c, dict) and c.get("text"):
                            reasoning += str(c["text"]) + "\n"
                    continue
                for c in item.get("content", []) or []:
                    if isinstance(c, dict) and c.get("text"):
                        parts.append(str(c["text"]))
        content = "\n".join(parts)
    
    return {"content": content, "reasoning": reasoning.strip(), "usage": obj.get("usage", {}), "body": obj}


def _call_cli(messages, cfg):
    """Call grok CLI in headless mode: grok -p "prompt" --output-format json"""
    exe = _resolve_executable(cfg.get("executable") or "grok")
    
    # Convert messages to single prompt
    prompt_parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            prompt_parts.append(f"[SYSTEM]\n{content}")
        elif role == "user":
            prompt_parts.append(f"[USER]\n{content}")
        elif role == "assistant":
            prompt_parts.append(f"[ASSISTANT]\n{content}")
        else:
            prompt_parts.append(f"[{role.upper()}]\n{content}")
    prompt = "\n\n".join(prompt_parts)
    
    args = ["-p", "--output-format", "json", "--no-auto-update"]
    extra_args = cfg.get("extra_args")
    if extra_args:
        args.extend(extra_args)
    
    cp = subprocess.run(
        [exe, *args, prompt],
        capture_output=True,
        text=True,
        timeout=float(cfg.get("timeout") or 120)
    )
    
    if cp.returncode != 0:
        raise RuntimeError(f"grok CLI exited {cp.returncode}: {cp.stderr.strip()[:2000]}")
    
    text = cp.stdout.strip()
    try:
        obj = json.loads(text)
        content = obj.get("content") or obj.get("message") or text
        reasoning = obj.get("reasoning") or ""
    except json.JSONDecodeError:
        content = text
        reasoning = ""
    
    return {"content": content, "reasoning": reasoning, "stdout": cp.stdout, "stderr": cp.stderr}
