from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import BUDGET_VERIFIER_OUT
from context import render_context
from dispatch import call_role, RoleSpec
import log


SPEC = RoleSpec("verifier", 8000, BUDGET_VERIFIER_OUT)


class VerifierAgent:
    name: str = "verifier"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        context = render_context(board, "verifier")
        result = _call(board, context)
        if result is None:
            return AgentResult(
                writes={"consecutive_failures": board.consecutive_failures + 1},
                event_phase="verifier.error",
                event_data={"error": "no response"},
            )

        verdict = str(result.get("verdict", "denied"))
        evidence = str(result.get("evidence", ""))

        writes: dict[str, Any] = {
            "role_calls": _inc(board.role_calls, "verifier"),
            "total_role_calls": board.total_role_calls + 1,
            "last_outputs": {**board.last_outputs, "verifier": f"verdict={verdict}"},
        }

        if verdict == "confirmed":
            writes["done"] = True
            return AgentResult(
                writes=writes, next_agent="done",
                event_phase="verify",
                event_data={"verdict": "confirmed", "evidence": evidence[:200]},
            )

        writes["verify_denied_count"] = board.verify_denied_count + 1
        writes["plan_steps"] = []
        writes["plan_index"] = 0
        writes["requested_next"] = "planner"
        return AgentResult(
            writes=writes, next_agent="planner",
            event_phase="verify",
            event_data={"verdict": "denied", "evidence": evidence[:200]},
        )


def _call(board: Any, context: str) -> dict[str, Any] | None:
    try:
        return call_role(SPEC, context, temperature=board.effective_temperature())
    except Exception as e:
        log.emit("verifier.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
