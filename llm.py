"""LLM client for LM Studio. Config from prompts/model.json."""
from __future__ import annotations
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LLMResult:
    text: str
    reasoning: str = ""


response_count: int = 0
response_limit: int | None = None
shutdown_requested: bool = False


def set_response_limit(n: int | None) -> None:
    global response_count, response_limit, shutdown_requested
    response_limit = n
    response_count = 0
    shutdown_requested = False


def _tick_response() -> None:
    global response_count, shutdown_requested
    response_count += 1
    if response_limit is not None and response_count >= response_limit:
        shutdown_requested = True


class LLMClient:
    def __init__(self, prompts_dir: Path):
        self._config = self._load_json(prompts_dir / "model.json", required=True)
        if "host" not in self._config:
            raise ValueError("model.json must define host")
        if "timeout" not in self._config:
            raise ValueError("model.json must define timeout")
        self._host = str(self._config.pop("host")).rstrip("/")
        self._timeout = int(self._config.pop("timeout"))
        self._gate = threading.Semaphore(1)
        self._model: str | None = None

    @staticmethod
    def _load_json(path: Path, required: bool = False) -> dict[str, Any]:
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Required config missing: {path}")
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _resolve_model(self) -> str:
        if self._model:
            return self._model
        try:
            req = Request(f"{self._host}/v1/models", method="GET")
            with urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._model = next((m["id"] for m in data.get("data", []) if "id" in m), "")
        except (HTTPError, URLError, TimeoutError, OSError):
            self._model = ""
        return self._model or ""

    def call(self, system: str, user: str) -> LLMResult:
        if shutdown_requested:
            return LLMResult(text="", reasoning="shutdown: response limit reached")
        body: dict[str, Any] = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            **self._config,
        }
        model = self._resolve_model()
        if model:
            body["model"] = model
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        for attempt in range(3):
            try:
                with self._gate:
                    req = Request(f"{self._host}/v1/chat/completions", data=payload,
                                  headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(req, timeout=self._timeout) as resp:
                        raw_bytes = resp.read()
                result = json.loads(raw_bytes.decode("utf-8"))
                choices = result.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    # LM Studio: content = answer, reasoning_content = model thinking (nemotron etc.)
                    content = str(msg.get("content") or "")
                    reasoning = str(msg.get("reasoning_content") or "")
                    out = LLMResult(text=content, reasoning=reasoning)
                    _tick_response()
                    return out
                raise RuntimeError("no choices")
            except (HTTPError, URLError, TimeoutError, OSError) as e:
                if attempt >= 2:
                    out = LLMResult(text="", reasoning=f"LLM error: {e}")
                    _tick_response()
                    return out
                time.sleep(min(2 ** attempt, 10))
        out = LLMResult(text="")
        _tick_response()
        return out