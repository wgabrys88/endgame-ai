"""LM Studio / OpenAI-compatible chat completions brain node."""
host = str(cfg.get("host", "http://localhost:1234")).rstrip("/")
path = str(cfg.get("endpoint_path", "/v1/chat/completions"))
payload = {
    "model": cfg.get("model", "local-model"),
    "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ],
    "temperature": temperature,
    "max_tokens": cfg.get("max_tokens", 2048),
    "stream": False,
}
for key in (
    "top_p", "top_k", "min_p", "repeat_penalty", "presence_penalty", "frequency_penalty",
    "stop", "seed", "thinking", "response_format", "logit_bias", "n", "user",
):
    if key in cfg:
        payload[key] = cfg[key]
headers = {"Content-Type": "application/json"}
api_key = cfg.get("api_key") or os.environ.get(str(cfg.get("api_key_env", "")))
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
url = host + path
brain._log_raw(seq, "request", "openai", {
    "url": url,
    "model": payload.get("model"),
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
    raise RuntimeError(f"openai brain: HTTP {e.code}: {body[:1000]}")
except Exception as e:
    raise RuntimeError(f"openai brain: {e}")
brain._log_raw(seq, "response", "openai", {"model": payload.get("model"), "body": resp},
               elapsed_s=round(time.time() - started, 3))
msg = (resp.get("choices") or [{}])[0].get("message", {})
content = msg.get("content", "") or ""
reasoning = msg.get("reasoning_content", "") or msg.get("reasoning", "") or ""
