from __future__ import annotations
from typing import Any, cast

from config import BUDGET_PLANNER_OUT
from context import render_context
from dispatch import call_role, RoleSpec
import log


SPEC = RoleSpec("planner", 8000, BUDGET_PLANNER_OUT)


class PlannerAgent:
    name: str = "planner"
    reads: list[str] = [
        "goal", "plan_steps", "plan_index", "screen", "desktop_summary",
        "history", "notes", "consecutive_failures", "verify_denied_count",
        "stagnation_score", "pid_output", "attractor_energy", "lorenz_x",
        "jacobian", "last_outputs", "role_calls", "total_role_calls",
        "focused_window", "screen_elements",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        plan_steps: list[str] = ctx.get("plan_steps", [])
        plan_index = int(ctx.get("plan_index", 0))
        role_calls: dict[str, int] = ctx.get("role_calls", {})
        total = int(ctx.get("total_role_calls", 0))
        last_outputs: dict[str, str] = ctx.get("last_outputs", {})

        if plan_steps and plan_index < len(plan_steps):
            step = plan_steps[plan_index]
            return {
                "writes": {
                    "last_instruction": step,
                    "requested_next": "actor",
                    "role_calls": _inc(role_calls, "planner"),
                    "total_role_calls": total + 1,
                    "last_outputs": {**last_outputs, "planner": f"step='{step[:60]}'"},
                },
                "next": "actor",
                "phase": "plan",
                "data": {"mode": "direct", "action": step, "step": plan_index, "steps": len(plan_steps)},
            }

        if plan_steps and plan_index >= len(plan_steps):
            return {
                "writes": {
                    "requested_next": "verifier",
                    "role_calls": _inc(role_calls, "planner"),
                    "total_role_calls": total + 1,
                    "last_outputs": {**last_outputs, "planner": "mode=done (plan exhausted)"},
                },
                "next": "verifier",
                "phase": "plan",
                "data": {"mode": "done", "step": plan_index, "steps": len(plan_steps)},
            }

        context = _render(ctx)
        plan = _call(ctx, context)
        if plan is None:
            return {
                "writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1},
                "next": "stagnation",
                "phase": "planner.error",
                "data": {"error": "no response"},
            }

        mode = str(plan.get("mode", "direct"))
        next_action = str(plan.get("next_action", ""))
        recipient = str(plan.get("recipient", ""))
        sequence = plan.get("sequence", [])

        writes: dict[str, Any] = {
            "role_calls": _inc(role_calls, "planner"),
            "total_role_calls": total + 1,
            "last_outputs": {**last_outputs, "planner": f"mode={mode} action='{next_action[:60]}'"},
        }

        if isinstance(sequence, list) and sequence:
            writes["plan_steps"] = [str(s) for s in cast(list[Any], sequence) if str(s).strip()]
            writes["plan_index"] = 0

        steps = writes.get("plan_steps", plan_steps)
        writes["last_instruction"] = steps[0] if steps else next_action

        next_agent = "actor"
        if recipient:
            writes["requested_next"] = recipient
            next_agent = recipient
        if mode == "done":
            writes["requested_next"] = "verifier"
            next_agent = "verifier"
        elif not recipient:
            writes["requested_next"] = "actor"

        return {
            "writes": writes,
            "next": next_agent,
            "phase": "plan",
            "data": {"mode": mode, "action": next_action, "step": 0, "steps": len(steps)},
        }


def _render(ctx: dict[str, Any]) -> str:
    from board import Board
    b = Board()
    for k, v in ctx.items():
        if hasattr(b, k):
            setattr(b, k, v)
    return render_context(b, "planner")


def _call(ctx: dict[str, Any], context: str) -> dict[str, Any] | None:
    try:
        from board import Board
        b = Board()
        for k, v in ctx.items():
            if hasattr(b, k):
                setattr(b, k, v)
        return call_role(SPEC, context, temperature=b.effective_temperature())
    except Exception as e:
        log.emit("planner.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
