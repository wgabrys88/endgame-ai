"""Archive per-agent event logs before the rolling window trims them."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import config

ARCHIVE_DIR: Path = config.BASE_DIR / "runtime" / "comms" / "archive"
ARCHIVE_INTERVAL_SEC: float = 60.0


def run(board):
    state = board.get("_plugin_archive_logs", {})
    last = state.get("last_archive", 0)
    now = time.time()
    if now - last < ARCHIVE_INTERVAL_SEC:
        return None

    archive = ARCHIVE_DIR
    archive.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in sorted(config.BASE_DIR.glob("events-child-*.jsonl")):
        if not src.exists() or src.stat().st_size == 0:
            continue
        dst = archive / f"{src.stem}-{int(now)}.jsonl"
        try:
            shutil.copy2(str(src), str(dst))
            copied += 1
        except OSError:
            continue

    return {
        "writes": {"_plugin_archive_logs": {"last_archive": now, "copied": copied}},
        "phase": "plugin.archive_logs",
        "data": {"copied": copied, "archive": str(archive.relative_to(config.BASE_DIR))},
    }
