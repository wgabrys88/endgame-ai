from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any

from config import SNAPSHOT_PATH, LESSONS_PATH


@dataclass(slots=True)
class Board:
    goal: str = ""
    plan_steps: list[str] = field(default_factory=list[str])
    plan_index: int = 0
    history: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    notes: list[str] = field(default_factory=list[str])
    screen: str = ""
    screen_hash: str = ""
    screen_elements: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    desktop_summary: str = ""
    focused_window: str = ""
    last_verb: str = ""
    last_success: bool = False
    last_observation: str = ""
    actor_conclusion: str = ""
    consecutive_failures: int = 0
    verify_denied_count: int = 0
    repetition_score: float = 0.0
    stagnation_score: float = 0.0
    screen_stagnation: int = 0
    recent_hashes: list[str] = field(default_factory=list[str])
    recent_sigs: list[str] = field(default_factory=list[str])
    jacobian: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    jacobian_trials: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    lorenz_x: float = 8.485
    lorenz_y: float = 8.485
    lorenz_z: float = 27.0
    attractor_energy: float = 1.0
    lorenz_wing_crossed: bool = False
    pid_output: float = 0.0
    pid_integral: float = 0.0
    pid_prev: float = 0.0
    last_instruction: str = ""
    requested_next: str = ""
    role_calls: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    total_role_calls: int = 0
    halt_count: int = 0
    last_outputs: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    done: bool = False
    disabled_agents: set[str] = field(default_factory=set[str])

    def apply(self, writes: dict[str, Any]) -> None:
        for key, val in writes.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def save(self) -> None:
        import log
        data = {
            "goal": self.goal, "plan_steps": self.plan_steps, "plan_index": self.plan_index,
            "history": self.history[-20:], "consecutive_failures": self.consecutive_failures,
            "stagnation_score": self.stagnation_score, "repetition_score": self.repetition_score,
            "lorenz_x": self.lorenz_x, "lorenz_y": self.lorenz_y, "lorenz_z": self.lorenz_z,
            "attractor_energy": self.attractor_energy, "lorenz_wing_crossed": self.lorenz_wing_crossed,
            "pid_output": self.pid_output, "pid_integral": self.pid_integral,
            "screen_stagnation": self.screen_stagnation, "halt_count": self.halt_count,
            "jacobian": self.jacobian, "last_verb": self.last_verb,
            "last_instruction": self.last_instruction, "focused_window": self.focused_window,
            "events": log.count(), "budget": log.budget(),
        }
        SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_lesson(self, lesson: str) -> None:
        if not lesson.strip():
            return
        with LESSONS_PATH.open("a", encoding="utf-8") as f:
            f.write(lesson.strip() + "\n")

    def effective_temperature(self) -> float:
        from config import LLM_TEMPERATURE
        base = LLM_TEMPERATURE
        chaos_boost = min(0.4, self.attractor_energy * 0.1)
        stagnation_boost = min(0.3, self.stagnation_score * 0.3)
        return min(1.0, base + chaos_boost + stagnation_boost)
