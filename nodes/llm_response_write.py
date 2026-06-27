"""Relay slot: write an external LLM response from memory/state."""
rt = wiring.get("runtime", {})
path = runtime.ROOT / rt.get("llm_response_path", "comms/llm_proxy/response.json")
content = state.get("llm_response") or (state.get("memory", {}) or {}).get(rt.get("llm_response_memory_key", "llm_response"), "")
if content:
    atomic_write_json(path, {"content": content, "created_at": time.time()}, indent=2)
    patch = {"llm_response_written": str(path)}
    signals = ["response_written"]
else:
    patch = {"last_error": "no llm_response content"}
    signals = ["response_missing"]
