from __future__ import annotations
from typing import Any, cast

from agents import AgentResult
from config import BUDGET_PLANNER_OUT
from context import render_context
from dispatch import call_role, RoleSpec
import log


SPEC = RoleSpec("planner", 8000, BUDGET_PLANNER_OUT)


class PlannerAgent:
    name: str = "planner"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        if board.plan_steps and board.plan_index < len(board.plan_steps):
            step = board.plan_steps[board.plan_index]
            return AgentResult(
                writes={
                    "last_instruction": step,
                    "requested_next": "actor",
                    "role_calls": _inc(board.role_calls, "planner"),
                    "total_role_calls": board.total_role_calls + 1,
                    "last_outputs": {**board.last_outputs, "planner": f"step='{step[:60]}'"},
                },
                next_agent="actor",
                event_phase="plan",
                event_data={"mode": "direct", "action": step, "step": board.plan_index, "steps": len(board.plan_steps)},
            )

        if board.plan_steps and board.plan_index >= len(board.plan_steps):
            return AgentResult(
                writes={
                    "requested_next": "verifier",
                    "role_calls": _inc(board.role_calls, "planner"),
                    "total_role_calls": board.total_role_calls + 1,
                    "last_outputs": {**board.last_outputs, "planner": "mode=done (plan exhausted)"},
                },
                next_agent="verifier",
                event_phase="plan",
                event_data={"mode": "done", "step": board.plan_index, "steps": len(board.plan_steps)},
            )

        context = render_context(board, "planner")
        plan = _call(board, context)
        if plan is None:
            return AgentResult(
                writes={"consecutive_failures": board.consecutive_failures + 1},
                event_phase="planner.error",
                event_data={"error": "no response"},
            )

        mode = str(plan.get("mode", "direct"))
        next_action = str(plan.get("next_action", ""))
        recipient = str(plan.get("recipient", ""))
        sequence = plan.get("sequence", [])

        writes: dict[str, Any] = {
            "role_calls": _inc(board.role_calls, "planner"),
            "total_role_calls": board.total_role_calls + 1,
            "last_outputs": {**board.last_outputs, "planner": f"mode={mode} action='{next_action[:60]}'"},
        }

        if isinstance(sequence, list) and sequence:
            writes["plan_steps"] = [str(s) for s in cast(list[Any], sequence) if str(s).strip()]
            writes["plan_index"] = 0

        plan_steps = writes.get("plan_steps", board.plan_steps)
        writes["last_instruction"] = plan_steps[0] if plan_steps else next_action

        next_agent = ""
        if recipient:
            writes["requested_next"] = recipient
            next_agent = recipient
        if mode == "done":
            writes["requested_next"] = "verifier"
            next_agent = "verifier"
        elif not next_agent:
            writes["requested_next"] = "actor"
            next_agent = "actor"

        return AgentResult(
            writes=writes, next_agent=next_agent,
            event_phase="plan",
            event_data={"mode": mode, "action": next_action, "step": 0, "steps": len(plan_steps)},
        )


def _call(board: Any, context: str) -> dict[str, Any] | None:
    try:
        return call_role(SPEC, context, temperature=board.effective_temperature())
    except Exception as e:
        log.emit("planner.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
