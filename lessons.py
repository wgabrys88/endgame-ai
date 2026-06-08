from __future__ import annotations
from config import TWO_INT, ZERO_INT
import hashlib
import json
from typing import Any

from config import BASE_DIR, LESSON_ID_HEX_LENGTH, MAX_LESSONS

_PATH = BASE_DIR / "lessons.json"


class Lessons:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {"insights": []}
        if _PATH.exists():
            self.data = json.loads(_PATH.read_text(encoding="utf-8"))
        self._upgrade()

    def get_context(self) -> str:
        insights = self.data.get("insights", [])
        if not insights:
            return ""
        return "LEARNED INSIGHTS:\n" + "\n".join(f"- {i}" for i in insights)

    def add_lesson(self, lesson: str, *, role: str, issue_key: str, diagnosis: str, source_iteration: int) -> dict[str, Any] | None:
        cleaned = _clean_lesson(lesson)
        if not cleaned:
            return None
        insights = self.data.setdefault("insights", [])
        if cleaned not in insights:
            insights.append(cleaned)
        entries = self.data.setdefault("entries", [])
        lesson_id = _lesson_id(cleaned)
        for raw in entries:
            if isinstance(raw, dict) and raw.get("id") == lesson_id:
                return raw
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
        entries = self.data.get("entries", [])
        if not isinstance(entries, list):
            return []
        return [
            item for item in entries
            if isinstance(item, dict)
            and item.get("role") == role
            and not item.get("prompt_applied")
            and item.get("lesson")
        ]

    def mark_prompt_applied(self, lesson_ids: list[str], mutation: dict[str, Any]) -> None:
        wanted = set(lesson_ids)
        for item in self.data.get("entries", []):
            if isinstance(item, dict) and item.get("id") in wanted:
                item["prompt_applied"] = True
                item["prompt_mutation_id"] = mutation.get("id", "")
        self.data.setdefault("prompt_mutations", []).append(mutation)

    def issue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.data.get("entries", []):
            if not isinstance(item, dict):
                continue
            issue_key = str(item.get("issue_key", "")).strip()
            if issue_key:
                counts[issue_key] = counts.get(issue_key, ZERO_INT) + 1
        return counts

    def prompt_mutation_count(self, issue_key: str) -> int:
        count = ZERO_INT
        for item in self.data.get("prompt_mutations", []):
            if isinstance(item, dict) and item.get("issue_key") == issue_key:
                count += 1
        return count

    def tier3_already_triggered(self, issue_key: str) -> bool:
        for item in self.data.get("tier3_escalations", []):
            if isinstance(item, dict) and item.get("issue_key") == issue_key:
                return True
        return False

    def mark_tier3_triggered(self, issue_key: str, goal: str) -> None:
        self.data.setdefault("tier3_escalations", []).append({"issue_key": issue_key, "goal": goal})

    def save(self) -> None:
        insights = self.data.get("insights", [])
        if len(insights) > MAX_LESSONS:
            self.data["insights"] = insights[-MAX_LESSONS:]
        entries = self.data.get("entries", [])
        if isinstance(entries, list) and len(entries) > MAX_LESSONS:
            self.data["entries"] = entries[-MAX_LESSONS:]
        _PATH.write_text(json.dumps(self.data, indent=TWO_INT, ensure_ascii=False), encoding="utf-8")

    def _upgrade(self) -> None:
        insights = self.data.setdefault("insights", [])
        entries = self.data.setdefault("entries", [])
        if not isinstance(insights, list):
            self.data["insights"] = []
            insights = self.data["insights"]
        if not isinstance(entries, list):
            self.data["entries"] = []
            entries = self.data["entries"]
        existing_ids = {item.get("id") for item in entries if isinstance(item, dict)}
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
        self.data.setdefault("prompt_mutations", [])
        self.data.setdefault("tier3_escalations", [])


def _clean_lesson(lesson: str) -> str:
    return " ".join(lesson.strip().split())


def _lesson_id(lesson: str) -> str:
    return hashlib.sha256(lesson.encode("utf-8", errors="surrogatepass")).hexdigest()[:LESSON_ID_HEX_LENGTH]
