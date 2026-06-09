from __future__ import annotations
from typing import Any, cast

from config import BUDGET_REFLECTOR_OUT, PROMPTS_DIR
from context import render_context
from dispatch import call_role, RoleSpec
import log


SPEC = RoleSpec("reflector", 16000, BUDGET_REFLECTOR_OUT)
PROMPT_MIN_LENGTH: int = 200


class ReflectorAgent:
    name: str = "reflector"
    reads: list[str] = [
        "goal", "screen", "desktop_summary", "history", "plan_steps",
        "plan_index", "role_calls", "total_role_calls", "last_outputs",
        "stagnation_score", "pid_output", "attractor_energy", "lorenz_x",
        "jacobian", "focused_window", "notes",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        role_calls: dict[str, int] = ctx.get("role_calls", {})
        total = int(ctx.get("total_role_calls", 0))
        last_outputs: dict[str, str] = ctx.get("last_outputs", {})

        writes: dict[str, Any] = {
            "role_calls": _inc(role_calls, "reflector"),
            "total_role_calls": total + 1,
        }

        context = _render(ctx)
        result = _call(ctx, context)

        if result is None:
            return {"writes": writes, "next": "stagnation", "phase": "reflector.error", "data": {"error": "no response"}}

        diagnosis = str(result.get("diagnosis", ""))
        lesson = str(result.get("lesson", ""))
        writes["notes"] = [f"REFLECT: {lesson}"]
        writes["last_outputs"] = {**last_outputs, "reflector": f"lesson='{lesson[:80]}'"}

        if lesson.strip():
            from config import LESSONS_PATH
            with LESSONS_PATH.open("a", encoding="utf-8") as f:
                f.write(lesson.strip() + "\n")

        mutation = result.get("prompt_mutation")
        if isinstance(mutation, dict):
            target = str(cast(dict[str, Any], mutation).get("target", ""))
            append_text = str(cast(dict[str, Any], mutation).get("append", ""))
            if target and append_text:
                _apply_prompt_mutation(target, append_text)

        return {"writes": writes, "next": "stagnation", "phase": "reflect", "data": {"diagnosis": diagnosis[:200], "lesson": lesson[:200]}}


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


def _render(ctx: dict[str, Any]) -> str:
    from board import Board
    b = Board()
    for k, v in ctx.items():
        if hasattr(b, k):
            setattr(b, k, v)
    return render_context(b, "reflector")


def _call(ctx: dict[str, Any], context: str) -> dict[str, Any] | None:
    try:
        from board import Board
        b = Board()
        for k, v in ctx.items():
            if hasattr(b, k):
                setattr(b, k, v)
        return call_role(SPEC, context, temperature=b.effective_temperature())
    except Exception as e:
        log.emit("reflector.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
