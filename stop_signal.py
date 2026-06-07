from __future__ import annotations

from config import STOP_SIGNAL_PATH


def stop_requested() -> bool:
    return STOP_SIGNAL_PATH.exists()
