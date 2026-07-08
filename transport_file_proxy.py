import json
import os
import time

import core_brain as brain
import core_wiring as wiring


def _atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def call(messages, cfg):
    req_path = wiring.root_path(cfg["request_path"])
    resp_path = wiring.root_path(cfg["response_path"])
    if resp_path.exists():
        resp_path.unlink()
    _atomic_json(req_path, {
        "schema": "endgame-ai.file-proxy.request.v2",
        "created_at": time.time(),
        "transport": "transport_file_proxy",
        "messages": brain.summarize_messages_for_log(messages),
        "expected_record_type": cfg.get("expected_record_type"),
        "response_format": cfg.get("response_format"),
        "prompt_cache_key": cfg.get("prompt_cache_key"),
        "stable_prefix": cfg.get("stable_prefix"),
        "expected_response": {"record_type": "string", "data": "object", "reasoning": "string"},
    })
    deadline = time.time() + float(cfg["timeout"])
    while time.time() < deadline:
        if resp_path.exists():
            obj = json.loads(resp_path.read_text(encoding="utf-8"))
            if not isinstance(obj.get("record_type"), str) or not isinstance(obj.get("data"), dict):
                raise RuntimeError(f"file_proxy response must be direct bus record: {resp_path}")
            reasoning = obj.get("reasoning", "")
            if reasoning is not None and not isinstance(reasoning, str):
                raise RuntimeError("file_proxy response reasoning must be string")
            obj["reasoning"] = reasoning or ""
            return {"content": json.dumps(obj, ensure_ascii=False), "reasoning": obj["reasoning"], "response_path": str(resp_path)}
        time.sleep(float(cfg["poll_interval"]))
    raise RuntimeError(f"file_proxy timed out waiting for {resp_path}; no fallback was attempted")
