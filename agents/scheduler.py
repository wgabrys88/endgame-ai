from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import (
    STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REFLECT_THRESHOLD,
)
import log


class SchedulerAgent:
    name: str = "scheduler"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        writes: dict[str, Any] = {}

        if board.stagnation_score >= STAGNATION_HALT_THRESHOLD:
            new_halt = board.halt_count + 1
            if new_halt >= STAGNATION_HALT_SUSTAINED:
                writes["halt_count"] = new_halt
                return AgentResult(
                    writes=writes, next_agent="halt",
                    event_phase="schedule",
                    event_data={"decision": "halt", "stagnation": board.stagnation_score},
                )
            writes["halt_count"] = new_halt
        else:
            writes["halt_count"] = 0

        if board.lorenz_wing_crossed:
            writes["lorenz_wing_crossed"] = False
            writes["plan_steps"] = []
            writes["plan_index"] = 0
            writes["consecutive_failures"] = 0
            writes["halt_count"] = 0
            writes["recent_sigs"] = []
            writes["repetition_score"] = 0.0
            writes["stagnation_score"] = 0.0
            writes["pid_integral"] = 0.0
            writes["notes"] = ["DIVERGE: previous approach failed. Try a completely different method."]
            writes["requested_next"] = ""
            log.emit("lorenz.fork", {"x": board.lorenz_x, "stagnation": board.stagnation_score})
            return AgentResult(
                writes=writes, next_agent="planner",
                event_phase="schedule",
                event_data={"decision": "planner", "reason": "wing_cross"},
            )

        if board.requested_next:
            chosen = board.requested_next
            writes["requested_next"] = ""
            return AgentResult(
                writes=writes, next_agent=chosen,
                event_phase="schedule",
                event_data={"decision": chosen, "reason": "requested"},
            )

        if board.total_role_calls == 0:
            return AgentResult(
                writes=writes, next_agent="planner",
                event_phase="schedule",
                event_data={"decision": "planner", "reason": "initial"},
            )

        if board.pid_output > REFLECT_THRESHOLD and board.role_calls.get("reflector", 0) < board.total_role_calls * 0.15:
            return AgentResult(
                writes=writes, next_agent="reflector",
                event_phase="schedule",
                event_data={"decision": "reflector", "reason": "pid_gate"},
            )

        if not board.last_instruction:
            return AgentResult(
                writes=writes, next_agent="planner",
                event_phase="schedule",
                event_data={"decision": "planner", "reason": "no_instruction"},
            )

        return AgentResult(
            writes=writes, next_agent="actor",
            event_phase="schedule",
            event_data={"decision": "actor", "reason": "default"},
        )
