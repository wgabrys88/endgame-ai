from __future__ import annotations

from typing import Any


def expand(config: dict[str, Any]) -> dict[str, Any]:
    scan = dict(config.get("scan") or {})
    scan.update(config.get("depth") or {})
    return scan