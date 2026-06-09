from __future__ import annotations
from typing import Any, cast

from agents import AgentResult
from config import BUDGET_REFLECTOR_OUT, PROMPTS_DIR
from context import render_context
from dispatch import call_role, RoleSpec
import log


SPEC = RoleSpec("reflector", 16000, BUDGET_REFLECTOR_OUT)
PROMPT_MIN_LENGTH: int = 200


class ReflectorAgent:
    name: str = "reflector"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        context = render_context(board, "reflector")
        result = _call(board, context)

        writes: dict[str, Any] = {
            "role_calls": _inc(board.role_calls, "reflector"),
            "total_role_calls": board.total_role_calls + 1,
        }

        if result is None:
            return AgentResult(
                writes=writes, next_agent="planner",
                event_phase="reflector.error",
                event_data={"error": "no response"},
            )

        diagnosis = str(result.get("diagnosis", ""))
        lesson = str(result.get("lesson", ""))
        writes["notes"] = [f"REFLECT: {lesson}"]
        writes["last_outputs"] = {**board.last_outputs, "reflector": f"lesson='{lesson[:80]}'"}

        from board import Board
        temp_board = Board()
        temp_board.goal = board.goal
        temp_board.write_lesson(lesson)

        mutation = result.get("prompt_mutation")
        if isinstance(mutation, dict):
            target = str(cast(dict[str, Any], mutation).get("target", ""))
            append_text = str(cast(dict[str, Any], mutation).get("append", ""))
            if target and append_text:
                _apply_prompt_mutation(target, append_text)

        return AgentResult(
            writes=writes, next_agent="planner",
            event_phase="reflect",
            event_data={"diagnosis": diagnosis[:200], "lesson": lesson[:200]},
        )


def _apply_prompt_mutation(target: str, append_text: str) -> None:
    path = PROMPTS_DIR / f"{target}.txt"
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    new_content = current.rstrip() + "\n\n" + append_text.strip() + "\n"
    if len(new_content) < PROMPT_MIN_LENGTH:
        return
    path.write_text(new_content, encoding="utf-8")
    log.emit("mutation", {"target": target, "appended": append_text[:100]})


def _call(board: Any, context: str) -> dict[str, Any] | None:
    try:
        return call_role(SPEC, context, temperature=board.effective_temperature())
    except Exception as e:
        log.emit("reflector.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
