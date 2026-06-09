from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import (
    STAGNATION_WEIGHT_FAILURES, STAGNATION_WEIGHT_REPETITION,
    STAGNATION_WEIGHT_SCREEN, STAGNATION_NORMALIZER,
    REPETITION_WINDOW, REPETITION_MIN_WINDOW,
)


class StagnationAgent:
    name: str = "stagnation"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        window = board.recent_sigs[-REPETITION_WINDOW:]
        if len(window) >= REPETITION_MIN_WINDOW:
            repetition = 1.0 - (len(set(window)) / len(window))
        else:
            repetition = 0.0
        raw = (board.consecutive_failures * STAGNATION_WEIGHT_FAILURES
               + repetition * STAGNATION_WEIGHT_REPETITION
               + board.screen_stagnation * STAGNATION_WEIGHT_SCREEN)
        stagnation = min(1.0, raw / STAGNATION_NORMALIZER)
        return AgentResult(
            writes={"repetition_score": repetition, "stagnation_score": stagnation},
            event_phase="heartbeat.stagnation",
            event_data={"stagnation": round(stagnation, 3), "repetition": round(repetition, 3)},
        )
