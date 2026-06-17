"""LLM client for LM Studio with schema enforcement."""
from __future__ import annotations
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

RECORD_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "circuit_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "record_type": {
                    "type": "string",
                    "enum": ["task", "action", "verdict", "diagnosis", "mutation"],
                },
                "data": {"type": "object"},
            },
            "required": ["record_type", "data"],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True)
class LLMResult:
    text: str
    reasoning: str = ""


class LLMClient:
    def __init__(self, host: str = "http://localhost:1234", timeout: int = 600,
                 temperature: float = 0.12, max_tokens: int = 1536,
                 max_concurrent: int = 1):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._gate = threading.Semaphore(max(1, max_concurrent))
        self._model: str | None = None

    def _resolve_model(self) -> str:
        if self._model:
            return self._model
        try:
            req = Request(f"{self.host}/v1/models", method="GET")
            with urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._model = next((m["id"] for m in data.get("data", []) if "id" in m), "")
        except (HTTPError, URLError, TimeoutError, OSError):
            self._model = ""
        return self._model or ""

    def call(self, system: str, user: str, *, max_tokens: int = 0,
             temperature: float | None = None, raw: bool = False) -> LLMResult:
        body: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,
        }
        model = self._resolve_model()
        if model:
            body["model"] = model
        if not raw:
            body["response_format"] = RECORD_SCHEMA
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        for attempt in range(3):
            try:
                with self._gate:
                    req = Request(f"{self.host}/v1/chat/completions", data=payload,
                                  headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(req, timeout=self.timeout) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                choices = result.get("choices", [])
                if choices:
                    content = str(choices[0].get("message", {}).get("content", ""))
                    text, reasoning = self._extract_thinking(content)
                    return LLMResult(text=text, reasoning=reasoning)
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
