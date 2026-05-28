from __future__ import annotations
import json
from typing import Any

from config import BASE_DIR

_PATH = BASE_DIR / "lessons.json"
MAX_LESSONS = 7


class Lessons:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {"insights": []}
        if _PATH.exists():
            self._data = json.loads(_PATH.read_text(encoding="utf-8"))

    def get_context(self) -> str:
        insights = self._data.get("insights", [])
        if not insights:
            return ""
        return "LEARNED INSIGHTS:\n" + "\n".join(f"- {i}" for i in insights)

    def _save(self) -> None:
        insights = self._data.get("insights", [])
        if len(insights) > MAX_LESSONS:
            self._data["insights"] = insights[-MAX_LESSONS:]
        _PATH.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")