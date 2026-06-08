from __future__ import annotations
from config import TWO_INT, ZERO_INT
import hashlib
import json
from typing import Any, cast

from config import BASE_DIR, LESSON_ID_HEX_LENGTH, MAX_LESSONS

_PATH = BASE_DIR / "lessons.json"


class Lessons:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {"insights": []}
        if _PATH.exists():
            loaded: Any = json.loads(_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = cast(dict[str, Any], loaded)
        self._upgrade()

    def get_context(self) -> str:
        insights = [str(item) for item in self._list_field("insights") if str(item)]
        if not insights:
            return ""
        return "LEARNED INSIGHTS:\n" + "\n".join(f"- {i}" for i in insights)

    def add_lesson(self, lesson: str, *, role: str, issue_key: str, diagnosis: str, source_iteration: int) -> dict[str, Any] | None:
        cleaned = _clean_lesson(lesson)
        if not cleaned:
            return None
        insights = self._list_field("insights")
        if cleaned not in insights:
            insights.append(cleaned)
        entries = self._list_field("entries")
        lesson_id = _lesson_id(cleaned)
        for raw in entries:
            if isinstance(raw, dict):
                item = cast(dict[str, Any], raw)
                if item.get("id") == lesson_id:
                    return item
        entry: dict[str, Any] = {
            "id": lesson_id,
            "lesson": cleaned,
            "role": role,
            "issue_key": issue_key,
            "diagnosis": diagnosis,
            "source_iteration": source_iteration,
            "prompt_applied": False,
        }
        entries.append(entry)
        return entry

    def unapplied_prompt_entries(self, role: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in self._list_field("entries"):
            if not isinstance(raw, dict):
                continue
            item = cast(dict[str, Any], raw)
            if item.get("role") == role and not item.get("prompt_applied") and item.get("lesson"):
                result.append(item)
        return result

    def mark_prompt_applied(self, lesson_ids: list[str], mutation: dict[str, Any]) -> None:
        wanted = set(lesson_ids)
        for raw in self._list_field("entries"):
            if isinstance(raw, dict):
                item = cast(dict[str, Any], raw)
                if str(item.get("id", "")) in wanted:
                    item["prompt_applied"] = True
                    item["prompt_mutation_id"] = str(mutation.get("id", ""))
        self._list_field("prompt_mutations").append(mutation)

    def issue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for raw in self._list_field("entries"):
            if not isinstance(raw, dict):
                continue
            item = cast(dict[str, Any], raw)
            issue_key = str(item.get("issue_key", "")).strip()
            if issue_key:
                counts[issue_key] = counts.get(issue_key, ZERO_INT) + 1
        return counts

    def prompt_mutation_count(self, issue_key: str) -> int:
        count = ZERO_INT
        for raw in self._list_field("prompt_mutations"):
            if isinstance(raw, dict):
                item = cast(dict[str, Any], raw)
                if item.get("issue_key") == issue_key:
                    count += 1
        return count

    def tier3_already_triggered(self, issue_key: str) -> bool:
        for raw in self._list_field("tier3_escalations"):
            if isinstance(raw, dict):
                item = cast(dict[str, Any], raw)
                if item.get("issue_key") == issue_key:
                    return True
        return False

    def mark_tier3_triggered(self, issue_key: str, goal: str) -> None:
        self._list_field("tier3_escalations").append({"issue_key": issue_key, "goal": goal})

    def save(self) -> None:
        insights = self._list_field("insights")
        if len(insights) > MAX_LESSONS:
            self.data["insights"] = insights[-MAX_LESSONS:]
        entries = self._list_field("entries")
        if len(entries) > MAX_LESSONS:
            self.data["entries"] = entries[-MAX_LESSONS:]
        _PATH.write_text(json.dumps(self.data, indent=TWO_INT, ensure_ascii=False), encoding="utf-8")

    def _upgrade(self) -> None:
        insights = self._list_field("insights")
        entries = self._list_field("entries")
        existing_ids: set[str] = set()
        for raw in entries:
            if isinstance(raw, dict):
                item = cast(dict[str, Any], raw)
                lesson_id = str(item.get("id", ""))
                if lesson_id:
                    existing_ids.add(lesson_id)
        for lesson in insights:
            cleaned = _clean_lesson(str(lesson))
            lesson_id = _lesson_id(cleaned)
            if cleaned and lesson_id not in existing_ids:
                entries.append({
                    "id": lesson_id,
                    "lesson": cleaned,
                    "role": "",
                    "issue_key": "",
                    "diagnosis": "",
                    "source_iteration": ZERO_INT,
                    "prompt_applied": False,
                })
                existing_ids.add(lesson_id)
        self._list_field("prompt_mutations")
        self._list_field("tier3_escalations")

    def _list_field(self, key: str) -> list[Any]:
        raw = self.data.get(key)
        if isinstance(raw, list):
            return cast(list[Any], raw)
        replacement: list[Any] = []
        self.data[key] = replacement
        return replacement


def _clean_lesson(lesson: str) -> str:
    return " ".join(lesson.strip().split())


def _lesson_id(lesson: str) -> str:
    return hashlib.sha256(lesson.encode("utf-8", errors="surrogatepass")).hexdigest()[:LESSON_ID_HEX_LENGTH]
