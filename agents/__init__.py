from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class AgentResult:
    writes: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    next_agent: str = ""
    event_phase: str = ""
    event_data: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


class Agent(Protocol):
    name: str

    def should_run(self, board: Any) -> bool: ...

    def run(self, board: Any) -> AgentResult: ...
