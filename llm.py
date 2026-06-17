"""LLM client for LM Studio. Config from prompts/model.json, schema from prompts/schema.json."""
from __future__ import annotations
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_log = logging.getLogger("endgame.llm")

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class LLMResult:
    text: str
    reasoning: str = ""


class LLMClient:
    def __init__(self, prompts_dir: Path):
        self._config = self._load_json(prompts_dir / "model.json")
        self._schema = self._load_json(prompts_dir / "schema.json")
        self._host = str(self._config.pop("host", "http://localhost:1234")).rstrip("/")
        self._timeout = int(self._config.pop("timeout", 600))
        self._gate = threading.Semaphore(1)
        self._model: str | None = None

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

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

    def call(self, system: str, user: str, *, max_tokens: int = 0) -> LLMResult:
        body: dict[str, Any] = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            **self._config,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        model = self._resolve_model()
        if model:
            body["model"] = model
        if self._schema:
            body["response_format"] = self._schema
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        _log.debug(">>> REQUEST\n%s", json.dumps(body, indent=2, ensure_ascii=False))
        for attempt in range(3):
            try:
                with self._gate:
                    _t0 = time.time()
                    req = Request(f"{self._host}/v1/chat/completions", data=payload,
                                  headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(req, timeout=self._timeout) as resp:
                        raw_bytes = resp.read()
                        result = json.loads(raw_bytes.decode("utf-8"))
                _log.debug("<<< RESPONSE [%.1fs]\n%s", time.time() - _t0, raw_bytes.decode("utf-8", errors="replace"))
                choices = result.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = str(msg.get("content", ""))
                    # LM Studio exposes reasoning_content for thinking models (gemma-4, etc.)
                    reasoning = str(msg.get("reasoning_content", ""))
                    # Fallback: if content is empty but reasoning has the answer, use it
                    if not content.strip() and reasoning.strip():
                        content = reasoning
                        reasoning = ""
                    # Fallback: extract <think> tags if reasoning_content not present
                    if not reasoning:
                        content, reasoning = self._extract_thinking(content)
                    return LLMResult(text=content, reasoning=reasoning)
                raise RuntimeError("no choices")
            except (HTTPError, URLError, TimeoutError, OSError) as e:
                if attempt >= 2:
                    return LLMResult(text="", reasoning=f"LLM error: {e}")
                time.sleep(min(2 ** attempt, 10))
        return LLMResult(text="")

    @staticmethod
    def _extract_thinking(raw: str) -> tuple[str, str]:
        thinks: list[str] = []

        def _cap(m: re.Match[str]) -> str:
            thinks.append(m.group(1).strip())
            return ""

        text = _THINK_RE.sub(_cap, raw).strip()
        reasoning = "\n\n".join(t for t in thinks if t)
        return text, reasoning
