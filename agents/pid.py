from __future__ import annotations
from typing import Any

from config import PID_KP, PID_KI, PID_KD, PID_INTEGRAL_MAX, PID_DEAD_ZONE


class PidAgent:
    name: str = "pid"
    reads: list[str] = ["stagnation_score", "pid_integral", "pid_prev", "consecutive_failures"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        stag = float(ctx.get("stagnation_score", 0))
        integral = float(ctx.get("pid_integral", 0))
        prev = float(ctx.get("pid_prev", 0))
        failures = int(ctx.get("consecutive_failures", 0))

        if failures > 0:
            integral = min(integral + stag, PID_INTEGRAL_MAX)
        slope = stag - prev
        d_term = PID_KD * slope if abs(slope) > PID_DEAD_ZONE else 0.0
        output = max(0.0, PID_KP * stag + PID_KI * integral + d_term)

        return {
            "writes": {"pid_output": output, "pid_integral": integral, "pid_prev": stag},
            "next": "scheduler",
            "phase": "pid",
            "data": {"pid": round(output, 3)},
        }
