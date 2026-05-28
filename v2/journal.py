from __future__ import annotations
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MONO_START = time.monotonic_ns() // 1_000_000


class ExecutionJournal:

    def __init__(self, execution_id: str, file_path: Path) -> None:
        self.execution_id = execution_id
        self.rid = execution_id
        self._file_path = file_path
        self._sequence_number = 0
        self._file_handle = open(file_path, "a", encoding="utf-8")

    def append(self, event_name: str, payload: dict[str, Any], *,
               cyc: int = 0, aid: str = "system",
               tid: str | None = None, ph: str = "system",
               lvl: str = "INFO") -> None:

        self._sequence_number += 1
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        payload_text = str(payload) if payload else ""

        record_line = (
            f"[{timestamp}] "
            f"[C:{cyc:03d}] "
            f"[{aid}] "
            f"[{event_name}] "
            f"{lvl} | {payload_text}"
        )

        self._file_handle.write(record_line + "\n")
        self._file_handle.flush()

    def close(self) -> None:
        self._file_handle.close()


def create_execution_journal(project_root: Path, goal_description: str) -> ExecutionJournal:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = uuid.uuid4().hex[:4]
    execution_id = f"{timestamp}-{short_id}"

    journal_file = project_root / f"journal-{execution_id}.txt"

    journal = ExecutionJournal(execution_id, journal_file)
    journal.append("run.start", {"goal": goal_description, "execution_id": execution_id})
    return journal