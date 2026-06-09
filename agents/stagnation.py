from __future__ import annotations
from typing import Any

from config import (
    STAGNATION_WEIGHT_FAILURES, STAGNATION_WEIGHT_REPETITION,
    STAGNATION_WEIGHT_SCREEN, STAGNATION_NORMALIZER,
    REPETITION_WINDOW, REPETITION_MIN_WINDOW,
)


class StagnationAgent:
    name: str = "stagnation"
    reads: list[str] = ["consecutive_failures", "recent_sigs", "screen_stagnation"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        sigs: list[str] = ctx.get("recent_sigs", [])
        window = sigs[-REPETITION_WINDOW:]
        if len(window) >= REPETITION_MIN_WINDOW:
            rep = 1.0 - (len(set(window)) / len(window))
        else:
            rep = 0.0
        failures = int(ctx.get("consecutive_failures", 0))
        screen_stag = int(ctx.get("screen_stagnation", 0))
        raw = (failures * STAGNATION_WEIGHT_FAILURES
               + rep * STAGNATION_WEIGHT_REPETITION
               + screen_stag * STAGNATION_WEIGHT_SCREEN)
        stag = min(1.0, raw / STAGNATION_NORMALIZER)
        return {
            "writes": {"stagnation_score": stag, "repetition_score": rep},
            "next": "lorenz",
            "phase": "stagnation",
            "data": {"stag": round(stag, 3), "rep": round(rep, 3)},
        }
