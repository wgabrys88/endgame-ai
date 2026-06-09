from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import SCREEN_STAGNATION_LOOKBACK


class JacobianAgent:
    name: str = "jacobian"

    def should_run(self, board: Any) -> bool:
        return board.last_verb != ""

    def run(self, board: Any) -> AgentResult:
        verb = board.last_verb
        screen_changed = board.screen_hash not in board.recent_hashes[-SCREEN_STAGNATION_LOOKBACK:]
        trials = board.jacobian_trials.get(verb, 0) + 1
        new_trials = dict(board.jacobian_trials)
        new_trials[verb] = trials
        old = board.jacobian.get(verb, 0.5)
        alpha = 1.0 / min(trials, 10)
        new_score = old + alpha * ((1.0 if screen_changed else 0.0) - old)
        new_jacobian = dict(board.jacobian)
        new_jacobian[verb] = new_score
        return AgentResult(
            writes={"jacobian": new_jacobian, "jacobian_trials": new_trials},
            event_phase="heartbeat.jacobian",
            event_data={"verb": verb, "score": round(new_score, 3), "changed": screen_changed},
        )
