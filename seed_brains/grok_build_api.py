"""Grok Build 0.1 through xAI Responses API, as a separate wireable brain node."""
host = str(cfg.get("host", "https://api.x.ai")).rstrip("/")
path = str(cfg.get("endpoint_path", "/v1/responses"))
model = str(cfg.get("model", "grok-build-0.1"))
payload = {
    "model": model,
    "input": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ],
    "store": bool(cfg.get("store", False)),
}
for key in (
    "temperature", "top_p", "max_output_tokens", "parallel_tool_calls", "reasoning",
    "text", "tools", "tool_choice", "metadata", "service_tier", "include", "user",
):
    if key == "temperature":
        payload[key] = temperature
    elif key in cfg:
        payload[key] = cfg[key]
headers = {"Content-Type": "application/json"}
api_key = cfg.get("api_key") or os.environ.get(str(cfg.get("api_key_env", "XAI_API_KEY")))
if not api_key:
    raise RuntimeError("grok_build_api brain: missing API key; set XAI_API_KEY or model.grok_build_api.api_key_env")
headers["Authorization"] = f"Bearer {api_key}"
url = host + path
brain._log_raw(seq, "request", "grok_build_api", {
    "url": url,
    "model": model,
    "headers": _redact_headers(headers),
    "body": payload,
}, rod_feedback="ROD_REASONING_CONTENT" in user)
started = time.time()
req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
try:
    with urllib.request.urlopen(req, timeout=brain._timeout(cfg)) as r:
        resp = json.loads(r.read().decode("utf-8", errors="replace"))
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"grok_build_api brain: HTTP {e.code}: {body[:1000]}")
except Exception as e:
    raise RuntimeError(f"grok_build_api brain: {e}")
content, reasoning = _xai_response_text(resp)
brain._log_raw(seq, "response", "grok_build_api", {"model": model, "body": resp},
               elapsed_s=round(time.time() - started, 3))
