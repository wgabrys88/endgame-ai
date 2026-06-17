"""Shared bus/blackboard for inter-slot communication."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Record:
    record_id: str
    record_type: str
    role: str
    task_id: str
    data: dict[str, Any]
    created_at: float = field(default_factory=time.time)


class Bus:
    """In-memory blackboard with optional file persistence for multi-slot."""

    def __init__(self, persist_path: Path | None = None):
        self.records: list[Record] = []
        self._persist_path = persist_path
        self._seq = 0

    def publish(self, record_type: str, role: str, task_id: str, data: dict[str, Any]) -> Record:
        self._seq += 1
        record = Record(
            record_id=f"{record_type}-{self._seq}",
            record_type=record_type,
            role=role,
            task_id=task_id,
            data=data,
        )
        self.records.append(record)
        if len(self.records) > 200:
            self.records = self.records[-200:]
        if self._persist_path:
            self._append_to_file(record)
        return record

    def query(self, record_type: str | None = None, task_id: str | None = None,
              limit: int = 20) -> list[Record]:
        result = self.records
        if record_type:
            result = [r for r in result if r.record_type == record_type]
        if task_id:
            result = [r for r in result if r.task_id == task_id]
        return result[-limit:]

    def _append_to_file(self, record: Record):
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "record_id": record.record_id,
                    "record_type": record.record_type,
                    "role": record.role,
                    "task_id": record.task_id,
                    "data": record.data,
                    "created_at": record.created_at,
                }, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass

    def has_pending_routes(self) -> bool:
        return any(r.record_type == "route" and r.data.get("status") == "open"
                   for r in self.records)

    def format_context(self, task_id: str | None = None, limit: int = 8) -> str:
        records = self.query(task_id=task_id, limit=limit)
        if not records:
            return ""
        lines = ["BUS RECORDS:"]
        for r in records:
            lines.append(f"  [{r.record_type}] {r.role}: {json.dumps(r.data, ensure_ascii=False)[:200]}")
        return "\n".join(lines)
