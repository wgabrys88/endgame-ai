import json
import time

import core_brain as brain
import core_wiring as wiring


def call(messages, cfg):
    req_path = wiring.root_path(cfg["request_path"])
    resp_path = wiring.root_path(cfg["response_path"])
    if resp_path.exists():
        resp_path.unlink()
    wiring.atomic_write_json(req_path, {
        "schema": "endgame-ai.file-proxy.request.v2",
        "created_at": time.time(),
        "transport": "transport_file_proxy",
        "messages": brain.summarize_messages_for_log(messages),
        "expected_record_type": cfg.get("expected_record_type"),
        "response_format": cfg.get("response_format"),
        "prompt_cache_key": cfg.get("prompt_cache_key"),
        "stable_prefix": cfg.get("stable_prefix"),
        "plain_text": bool(cfg.get("plain_text")),
        "expected_response": ({"content": "string", "reasoning": "string"} if cfg.get("plain_text") else {"record_type": "string", "data": "object", "reasoning": "string"}),
    })
    deadline = time.time() + float(cfg["timeout"])
    while time.time() < deadline:
        if resp_path.exists():
            obj = json.loads(resp_path.read_text(encoding="utf-8"))
            reasoning = obj.get("reasoning", "")
            if reasoning is not None and not isinstance(reasoning, str):
                raise RuntimeError("file_proxy response reasoning must be string")
            if cfg.get("plain_text"):
                content = obj.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError(f"file_proxy plain-text response requires non-empty content: {resp_path}")
                return {"content": content, "reasoning": reasoning or "", "response_path": str(resp_path)}
            if not isinstance(obj.get("record_type"), str) or not isinstance(obj.get("data"), dict):
                raise RuntimeError(f"file_proxy response must be direct bus record: {resp_path}")
            obj["reasoning"] = reasoning or ""
            return {"content": json.dumps(obj, ensure_ascii=False), "reasoning": obj["reasoning"], "response_path": str(resp_path)}
        time.sleep(float(cfg["poll_interval"]))
    raise RuntimeError(f"file_proxy timed out waiting for {resp_path}; no fallback was attempted")
