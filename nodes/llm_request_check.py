"""Relay slot: check for an external LLM request file."""
path = runtime.ROOT / wiring.get("runtime", {}).get("llm_request_path", "comms/llm_proxy/request.json")
if path.exists():
    req = json.loads(path.read_text(encoding="utf-8"))
    patch = {"llm_request": req}
    signals = ["request_ready"]
else:
    patch = {}
    signals = ["idle"]
