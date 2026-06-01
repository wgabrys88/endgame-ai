from __future__ import annotations
import json
from typing import Any

from config import BASE_DIR

_PATH = BASE_DIR / "lessons.json"


class Lessons:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {"insights": []}
        if _PATH.exists():
            self.data = json.loads(_PATH.read_text(encoding="utf-8"))

    def get_context(self) -> str:
        insights = self.data.get("insights", [])
        if not insights:
            return ""
        return "LEARNED INSIGHTS:\n" + "\n".join(f"- {i}" for i in insights)

    def save(self) -> None:
        from config import MAX_LESSONS
        insights = self.data.get("insights", [])
        if len(insights) > MAX_LESSONS:
            self.data["insights"] = insights[-MAX_LESSONS:]
        _PATH.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")