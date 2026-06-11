from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

import config

MAX_ENTRIES = 200
MIN_USEFUL_SCORE = 5


def _load() -> list[dict[str, Any]]:
    p = config.LESSONS_PATH
    if not p.exists():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"action": "", "result": line, "score": 5, "ts": 0})
    return entries


def _save(entries: list[dict[str, Any]]) -> None:
    entries = entries[-MAX_ENTRIES:]
    config.LESSONS_PATH.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


def record(lesson: str, action: str = "", score: int = 7) -> None:
    entries = _load()
    entries.append({
        "action": action[:200],
        "result": lesson[:300],
        "score": max(1, min(10, score)),
        "ts": time.time(),
    })
    if len(entries) > MAX_ENTRIES:
        entries.sort(key=lambda e: e.get("score", 5))
        entries = entries[len(entries) - MAX_ENTRIES:]
        entries.sort(key=lambda e: e.get("ts", 0))
    _save(entries)


def relevant(keyword: str = "", n: int = 5) -> list[dict[str, Any]]:
    entries = _load()
    if not entries:
        return []
    if keyword:
        kw = keyword.lower()
        scored = []
        for e in entries:
            text = f"{e.get('action','')} {e.get('result','')}".lower()
            match = sum(1 for w in kw.split() if w in text)
            if match > 0:
                scored.append((match * e.get("score", 5), e))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:n]]
    return sorted(entries, key=lambda e: e.get("score", 5), reverse=True)[:n]


def recent(n: int = 5) -> list[dict[str, Any]]:
    entries = _load()
    return entries[-n:]


def format_for_context(keyword: str = "", n: int = 5) -> str:
    items = relevant(keyword, n) if keyword else recent(n)
    if not items:
        return ""
    lines = []
    for e in items:
        s = e.get("score", 5)
        r = e.get("result", "")
        lines.append(f"  [{s}/10] {r}")
    return "LESSONS:\n" + "\n".join(lines)
