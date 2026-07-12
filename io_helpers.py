"""Shared filesystem IO helpers.

One home for the atomic-write and ndjson-append logic that was previously
duplicated across core_wiring.py, core_nodes.py, and core_brain.py. One
function, one job. No behavior change from the originals.
"""
import json
import os
import pathlib
import threading
import time
from typing import Any


def replace_with_retry(tmp: pathlib.Path, path: pathlib.Path, *, attempts: int = 6, base_delay: float = 0.05) -> None:
    """os.replace, but patient with a momentarily locked destination.

    On Windows os.replace needs exclusive access to `path` for an instant; a
    held handle (an editor, indexer, or a human's Notepad) makes it raise
    PermissionError (WinError 5). Such locks are transient, so retry with
    backoff before giving up. The final attempt is not caught, so a truly
    stuck destination still fails loud rather than silently losing the write.
    """
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(base_delay * (2 ** i))


def atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    replace_with_retry(tmp, path)


def atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    replace_with_retry(tmp, path)


def append_ndjson(path: pathlib.Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
