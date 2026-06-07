from __future__ import annotations
from config import ZERO_INT, ONE_INT
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO, cast

from config import BASE_DIR, LOG_SCHEMA_VERSION
from artifacts import materialize
from persistence import append_runtime_event

type LogRecord = dict[str, Any]
type TuiHook = Callable[[LogRecord, str], None]

_handle: TextIO | None = None
_path: Path | None = None
_tui_hook: TuiHook | None = None
_agent_id: str = ""
_sequence: int = ZERO_INT


def open_log(agent_id: str) -> Path:
    global _handle, _path, _agent_id, _sequence
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _path = BASE_DIR / f"log-{agent_id}-{ts}.jsonl"
    _handle = _path.open("a", encoding="utf-8", newline="\n")
    _agent_id = agent_id
    _sequence = ZERO_INT
    return _path


def set_tui_hook(hook: TuiHook | None) -> None:
    global _tui_hook
    _tui_hook = hook


def log(iteration: int, section: str, message: str, data: Any = None) -> LogRecord | None:
    global _tui_hook
    if _handle is None:
        return None
    record = _record(iteration, section, message, data)
    line = _write_record(record)
    if _tui_hook is not None:
        try:
            _tui_hook(record, line)
        except Exception as e:
            _tui_hook = None
            error_record = _record(iteration, "tui.error", "tui hook failed", {"phase": section, "exception_type": type(e).__name__, "exception": str(e)})
            _write_record(error_record)
    return record


def _write_record(record: LogRecord) -> str:
    if _handle is None:
        return ""
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    _handle.write(line + "\n")
    _handle.flush()
    append_runtime_event(record)
    return line


def _record(iteration: int, section: str, message: str, data: Any) -> LogRecord:
    global _sequence
    _sequence += ONE_INT
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    ready_data = materialize(_json_ready(data), _agent_id, _sequence, section)
    return {
        "version": LOG_SCHEMA_VERSION,
        "sequence": _sequence,
        "timestamp_utc": ts,
        "agent_id": _agent_id,
        "iteration": iteration,
        "phase": section,
        "message": message,
        "data": ready_data,
    }


def _json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(cast(Any, value)))
    if isinstance(value, dict):
        dict_value = cast(dict[Any, Any], value)
        return {str(k): _json_ready(v) for k, v in dict_value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        values = cast(Iterable[Any], value)
        return [_json_ready(v) for v in values]
    return repr(value)


def close_log() -> None:
    global _handle, _path, _agent_id
    if _handle:
        _handle.close()
        _handle = None
    _path = None
    _agent_id = ""
