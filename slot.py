"""Slot state — behavior lives in topology.GraphExecutor."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SlotState:
    goal: str = ""
    tasks: list[Any] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    active_task_id: str = ""
    screen: str = ""
    screen_elements: dict[str, Any] = field(default_factory=dict)
    cycles: int = 0
    fissions: int = 0
    phase: str = "unified"
    last_action_error: str = ""
    reasoning_history: list[dict[str, str]] = field(default_factory=list)
    _last_actions: list = field(default_factory=list)


class Slot:
    """Named state container for one wiring slot."""

    def __init__(self, name: str, wiring: dict[str, Any], *, can_act_desktop: bool = True):
        self.name = name
        self.state = SlotState()
        self.can_act_desktop = can_act_desktop
        self.state.phase = str(wiring["transitions"]["default"])

    def set_goal(self, goal: str) -> None:
        self.state.goal = goal
        self.state.tasks = []
        self.state.active_task_id = ""
        self.state.history = []
        self.state.reasoning_history = []
        self.state._last_actions = []
        self.state.phase = "unified"