from __future__ import annotations
import time
from typing import Any, Callable, cast

from config import (
    BUDGET_PLANNER_OUT, BUDGET_ACTOR_OUT, BUDGET_VERIFIER_OUT, BUDGET_REFLECTOR_OUT,
    DELAY_BETWEEN_CYCLES, DEFAULT_SCROLL_AMOUNT, PROMPTS_DIR,
)
from state import Board
from dispatch import call_role, RoleSpec
from observer import observe
from actions import execute_verb, VERBS
import log

ROLES: dict[str, RoleSpec] = {
    "planner": RoleSpec("planner", 8000, BUDGET_PLANNER_OUT),
    "actor": RoleSpec("actor", 8000, BUDGET_ACTOR_OUT),
    "verifier": RoleSpec("verifier", 8000, BUDGET_VERIFIER_OUT),
    "reflector": RoleSpec("reflector", 16000, BUDGET_REFLECTOR_OUT),
}


def run(board: Board, interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.goal, "budget": log.budget()})

    while not log.exhausted() and not interrupted():
        _observe(board)
        if log.exhausted():
            break

        role = board.decide_next_role()

        if role == "halt":
            log.emit("halt", {"stagnation": board.stagnation_score, "events": log.count()})
            board.save()
            return False

        result = _dispatch(board, role)

        if result == "done":
            log.emit("complete", {"goal": board.goal, "events": log.count()})
            board.save()
            return True

        board.save()
        time.sleep(DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count()})
    board.save()
    return False


def _observe(board: Board) -> None:
    try:
        obs = observe()
        if obs.semantic_hash == board.screen_hash:
            board.screen_stagnation += 1
            if board.last_verb:
                board.update_jacobian(board.last_verb, False)
            return
        if board.last_verb:
            board.update_jacobian(board.last_verb, True)
        board.record_screen(obs.context_text, obs.semantic_hash, obs.book, obs.focused_title, obs.desktop_summary)
        log.emit("observe", {"hash": obs.semantic_hash, "focused": obs.focused_title, "chars": len(obs.context_text)})
    except Exception as e:
        board.screen = f"OBSERVE_FAILED: {e}"
        board.on_failure()
        log.emit("observe.fail", {"error": str(e)})


def _dispatch(board: Board, role: str) -> str:
    if role == "planner":
        return _run_planner(board)
    if role == "actor":
        return _run_actor(board)
    if role == "verifier":
        return _run_verifier(board)
    if role == "reflector":
        return _run_reflector(board)
    return "continue"


def _run_planner(board: Board) -> str:
    if board.plan_steps and board.plan_index < len(board.plan_steps):
        step = board.plan_steps[board.plan_index]
        board.last_instruction = step
        board.requested_next = "actor"
        board.record_role_call("planner")
        board.last_outputs["planner"] = f"mode=direct action='{step[:60]}'"
        log.emit("plan", {"mode": "direct", "action": step, "step": board.plan_index, "steps": len(board.plan_steps)})
        return "continue"

    if board.plan_steps and board.plan_index >= len(board.plan_steps):
        board.requested_next = "verifier"
        board.record_role_call("planner")
        board.last_outputs["planner"] = "mode=done (plan exhausted)"
        log.emit("plan", {"mode": "done", "action": "plan complete", "step": board.plan_index, "steps": len(board.plan_steps)})
        return "continue"

    context = board.context("planner")
    plan = _call_role("planner", context, board)
    if plan is None:
        board.on_failure()
        return "continue"

    mode = str(plan.get("mode", "direct"))
    next_action = str(plan.get("next_action", ""))
    recipient = str(plan.get("recipient", ""))

    sequence = plan.get("sequence", [])
    if isinstance(sequence, list) and sequence:
        board.plan_steps = [str(s) for s in cast(list[Any], sequence) if str(s).strip()]
        board.plan_index = 0

    log.emit("plan", {"mode": mode, "action": next_action, "step": board.plan_index, "steps": len(board.plan_steps)})

    board.last_instruction = next_action
    board.record_role_call("planner")
    board.last_outputs["planner"] = f"mode={mode} action='{next_action[:60]}'"

    if recipient:
        board.requested_next = recipient

    if mode == "done":
        board.requested_next = "verifier"
    elif not board.requested_next:
        board.requested_next = "actor"

    return "continue"


def _run_actor(board: Board) -> str:
    instruction = board.last_instruction or (board.plan_steps[board.plan_index] if board.plan_steps else "")
    if not instruction:
        board.on_failure()
        return "continue"

    context = board.context("actor", instruction)
    actor_out = _call_role("actor", context, board)
    if actor_out is None:
        board.on_failure()
        return "continue"

    board.actor_observe = str(actor_out.get("observe", ""))
    board.actor_conclusion = str(actor_out.get("conclusion", ""))
    recipient = str(actor_out.get("recipient", ""))

    raw_actions = actor_out.get("actions", [])
    actions: list[dict[str, Any]] = cast(list[dict[str, Any]], raw_actions) if isinstance(raw_actions, list) else []

    if board.actor_conclusion == "DONE" and not actions:
        board.on_success()
        board.record_role_call("actor")
        board.advance_step()
        return "continue"

    if board.actor_conclusion == "UNEXPECTED":
        board.on_failure()
        board.record_role_call("actor")
        board.plan_steps = []
        board.plan_index = 0
        board.requested_next = "planner"
        log.emit("actor", {"conclusion": "UNEXPECTED", "actions": 0})
        return "continue"

    log.emit("actor", {"conclusion": board.actor_conclusion, "actions": len(actions)})

    had_failure = False
    for action in actions:
        verb = str(action.get("verb", ""))
        target = str(action.get("target", ""))
        value = str(action.get("value", ""))
        args = _build_args(verb, target, value)

        if verb not in VERBS:
            board.record_action(verb, False, f"unknown verb: {verb}")
            had_failure = True
            break

        result = execute_verb(verb, args, board.screen_elements, board)
        board.record_action(verb, result.success, result.observation)
        log.emit("action", {"verb": verb, "ok": result.success, "obs": result.observation[:100]})

        if not result.success:
            had_failure = True
            break

    if had_failure:
        board.on_failure()
    else:
        board.on_success()
        board.advance_step()

    board.record_role_call("actor")
    board.last_outputs["actor"] = f"conclusion={board.actor_conclusion} actions={len(actions)}"
    if recipient:
        board.requested_next = recipient
    elif not board.requested_next:
        board.requested_next = "planner"

    return "continue"


def _run_verifier(board: Board) -> str:
    context = board.context("verifier")
    result = _call_role("verifier", context, board)
    if result is None:
        board.on_failure()
        return "continue"
    verdict = str(result.get("verdict", "denied"))
    log.emit("verify", {"verdict": verdict, "evidence": str(result.get("evidence", ""))[:200]})
    board.record_role_call("verifier")
    board.last_outputs["verifier"] = f"verdict={verdict}"
    if verdict == "confirmed":
        return "done"
    board.on_verify_denied()
    board.requested_next = "planner"
    return "continue"


def _run_reflector(board: Board) -> str:
    context = board.context("reflector")
    result = _call_role("reflector", context, board)
    if result:
        diagnosis = str(result.get("diagnosis", ""))
        lesson = str(result.get("lesson", ""))
        log.emit("reflect", {"diagnosis": diagnosis, "lesson": lesson})
        board.notes = [f"REFLECT: {lesson}"]
        board.last_outputs["reflector"] = f"lesson='{lesson[:80]}'"
        board.write_lesson(lesson)
        mutation = result.get("prompt_mutation")
        if isinstance(mutation, dict):
            target = str(cast(dict[str, Any], mutation).get("target", ""))
            append_text = str(cast(dict[str, Any], mutation).get("append", ""))
            if target and append_text:
                _apply_prompt_mutation(target, append_text)
    board.record_role_call("reflector")
    return "continue"


def _call_role(role: str, context: str, board: Board) -> dict[str, Any] | None:
    spec = ROLES[role]
    try:
        temp = board.effective_temperature()
        return call_role(spec, context, temperature=temp)
    except Exception as e:
        log.emit(f"{role}.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _build_args(verb: str, target: str, value: str) -> dict[str, Any]:
    if verb == "click":
        return {"selector": target}
    if verb == "write":
        return {"selector": target, "text": value}
    if verb == "press":
        return {"key": target or value}
    if verb == "hotkey":
        raw = value or target
        keys = [k.strip() for k in raw.replace("+", ",").split(",") if k.strip()]
        return {"keys": keys}
    if verb == "scroll":
        try:
            return {"selector": target, "amount": int(value) if value else DEFAULT_SCROLL_AMOUNT}
        except ValueError:
            return {"selector": target, "amount": DEFAULT_SCROLL_AMOUNT}
    if verb == "wait":
        try:
            return {"seconds": float(target or value or "1.0")}
        except ValueError:
            return {"seconds": 1.0}
    if verb == "focus":
        return {"window_title": target or value}
    if verb == "read_file":
        return {"path": target or value}
    if verb == "write_file":
        return {"path": target, "content": value}
    if verb == "cmd":
        return {"command": value or target}
    return {}


PROMPT_MIN_LENGTH: int = 200


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
