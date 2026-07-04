from __future__ import annotations

import json
import os
import pathlib
import time


def _root_path(value):
    p = pathlib.Path(os.path.expandvars(os.path.expanduser(str(value))))
    return p if p.is_absolute() else pathlib.Path(__file__).resolve().parent / p


def call(messages, cfg):
    req_path = _root_path(cfg.get("request_path") or "comms/request.json")
    resp_path = _root_path(cfg.get("response_path") or "comms/response.json")
    req_path.parent.mkdir(parents=True, exist_ok=True)
    request = {"messages": messages, "created_at": time.time(), "transport": "file_proxy"}
    tmp = req_path.with_suffix(req_path.suffix + ".tmp")
    tmp.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, req_path)
    if resp_path.exists():
        resp_path.unlink()
    timeout = float(cfg.get("timeout") or 60)
    interval = float(cfg.get("poll_interval") or 0.25)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if resp_path.exists():
            try:
                obj = json.loads(resp_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"file_proxy response is malformed JSON: {resp_path}: {exc}") from exc
            content = obj.get("content")
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(f"file_proxy response missing non-empty content: {resp_path}")
            reasoning = obj.get("reasoning", "")
            if reasoning is not None and not isinstance(reasoning, str):
                raise RuntimeError("file_proxy response reasoning must be a string when present")
            return {"content": content, "reasoning": reasoning or "", "response_path": str(resp_path)}
        time.sleep(interval)
    raise RuntimeError(f"file_proxy timed out waiting for {resp_path}; no fallback was attempted")
