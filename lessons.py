"""Lessons — scored JSONL memory. Plugins decay old entries."""
from __future__ import annotations
import json
import time
from typing import Any
import config

MAX_ENTRIES = 200


def _load() -> list[dict[str, Any]]:
    if not config.LESSONS_PATH.exists():
        return []
    entries = []
    for line in config.LESSONS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({"result": line.strip(), "score": 5, "ts": 0})
    return entries


def _save(entries: list[dict[str, Any]]) -> None:
    config.LESSONS_PATH.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries[-MAX_ENTRIES:]) + "\n", encoding="utf-8")


def record(lesson: str, action: str = "", score: int = 7) -> None:
    entries = _load()
    entries.append({"action": action[:200], "result": lesson[:300], "score": max(1, min(10, score)), "ts": time.time()})
    if len(entries) > MAX_ENTRIES:
        entries.sort(key=lambda e: e.get("score", 5))
        entries = entries[-MAX_ENTRIES:]
    _save(entries)
