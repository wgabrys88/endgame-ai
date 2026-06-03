from __future__ import annotations
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from config import BASE_DIR

_handle: io.TextIOWrapper | None = None
_path: Path | None = None
_tui_hook: Callable[[str], None] | None = None


def open_log(agent_id: str) -> Path:
    global _handle, _path
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _path = BASE_DIR / f"log-{agent_id}-{ts}.txt"
    _handle = open(_path, "a", encoding="utf-8")
    return _path


def set_tui_hook(hook: Callable[[str], None] | None) -> None:
    global _tui_hook
    _tui_hook = hook


def log(iteration: int, section: str, data: str) -> None:
    if _handle is None:
        return
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    line = f"[{ts}] [IT:{iteration:03d}] [{section}] {data}"
    _handle.write(line + "\n")
    _handle.flush()
    if _tui_hook is not None:
        _tui_hook(f"{section} {data[:60]}")


def close_log() -> None:
    global _handle
    if _handle:
        _handle.close()
        _handle = None
