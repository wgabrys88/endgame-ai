from __future__ import annotations
from typing import Any, Protocol


class Agent(Protocol):
    name: str
    reads: list[str]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]: ...
