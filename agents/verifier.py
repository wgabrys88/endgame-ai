from __future__ import annotations
from typing import Any

from config import BUDGET_VERIFIER_OUT
from context import render_context
from dispatch import call_role, RoleSpec
import log


SPEC = RoleSpec("verifier", 8000, BUDGET_VERIFIER_OUT)


class VerifierAgent:
    name: str = "verifier"
    reads: list[str] = [
        "goal", "screen", "desktop_summary", "history", "plan_steps",
        "plan_index", "role_calls", "total_role_calls", "last_outputs",
        "verify_denied_count", "stagnation_score", "pid_output",
        "attractor_energy", "lorenz_x", "focused_window",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        role_calls: dict[str, int] = ctx.get("role_calls", {})
        total = int(ctx.get("total_role_calls", 0))
        last_outputs: dict[str, str] = ctx.get("last_outputs", {})
        denied = int(ctx.get("verify_denied_count", 0))

        context = _render(ctx)
        result = _call(ctx, context)
        if result is None:
            return {
                "writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1},
                "next": "stagnation",
                "phase": "verifier.error",
                "data": {"error": "no response"},
            }

        verdict = str(result.get("verdict", "denied"))
        evidence = str(result.get("evidence", ""))

        writes: dict[str, Any] = {
            "role_calls": _inc(role_calls, "verifier"),
            "total_role_calls": total + 1,
            "last_outputs": {**last_outputs, "verifier": f"verdict={verdict}"},
        }

        if verdict == "confirmed":
            writes["done"] = True
            return {"writes": writes, "next": "done", "phase": "verify", "data": {"verdict": "confirmed", "evidence": evidence[:200]}}

        writes["verify_denied_count"] = denied + 1
        writes["plan_steps"] = []
        writes["plan_index"] = 0
        writes["requested_next"] = "planner"
        return {"writes": writes, "next": "stagnation", "phase": "verify", "data": {"verdict": "denied", "evidence": evidence[:200]}}


def _render(ctx: dict[str, Any]) -> str:
    from board import Board
    b = Board()
    for k, v in ctx.items():
        if hasattr(b, k):
            setattr(b, k, v)
    return render_context(b, "verifier")


def _call(ctx: dict[str, Any], context: str) -> dict[str, Any] | None:
    try:
        from board import Board
        b = Board()
        for k, v in ctx.items():
            if hasattr(b, k):
                setattr(b, k, v)
        return call_role(SPEC, context, temperature=b.effective_temperature())
    except Exception as e:
        log.emit("verifier.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
