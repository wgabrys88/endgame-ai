from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import PID_KP, PID_KI, PID_KD, PID_INTEGRAL_MAX, PID_DEAD_ZONE


class PidAgent:
    name: str = "pid"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        error = board.stagnation_score
        integral = board.pid_integral
        if board.consecutive_failures > 0:
            integral = min(integral + error, PID_INTEGRAL_MAX)
        slope = error - board.pid_prev
        d_term = PID_KD * slope if abs(slope) > PID_DEAD_ZONE else 0.0
        output = max(0.0, PID_KP * error + PID_KI * integral + d_term)
        return AgentResult(
            writes={"pid_output": output, "pid_integral": integral, "pid_prev": error},
            event_phase="heartbeat.pid",
            event_data={"output": round(output, 3), "integral": round(integral, 3)},
        )
