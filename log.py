from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from config import EVENTS_PATH

_handle: TextIO | None = None
_counter: int = 0
_budget: int = 100
_seq: int = 0


def init(budget: int) -> Path:
    global _handle, _counter, _budget, _seq
    _counter = 0
    _seq = 0
    _budget = budget
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _handle = EVENTS_PATH.open("a", encoding="utf-8", newline="\n")
    return EVENTS_PATH


def emit(phase: str, data: Any = None) -> int:
    global _counter
    _counter += 1
    _write(phase, data, _counter)
    return _counter


def trace(phase: str, data: Any = None) -> int:
    _write(phase, data, None)
    return _counter


def _write(phase: str, data: Any, n: int | None) -> None:
    global _seq
    _seq += 1
    if _handle is None:
        return
    record: dict[str, Any] = {
        "seq": _seq,
        "t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "phase": phase,
    }
    if n is not None:
        record["n"] = n
    if data is not None:
        record["d"] = data
    _handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    _handle.flush()


def exhausted() -> bool:
    return _counter >= _budget


def count() -> int:
    return _counter


def budget() -> int:
    return _budget


def close() -> None:
    global _handle
    if _handle:
        _handle.close()
        _handle = None
