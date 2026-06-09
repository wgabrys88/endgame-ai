from __future__ import annotations
import time
from typing import Any, Callable, cast

from config import (
    BUDGET_PLANNER_OUT, BUDGET_ACTOR_OUT, BUDGET_VERIFIER_OUT, BUDGET_REFLECTOR_OUT,
    DELAY_BETWEEN_CYCLES, STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REFLECT_THRESHOLD, REFLECT_BUDGET_GATE, REFLECT_MIN_INTERVAL, REFLECT_MIN_FAILURES,
    DEFAULT_SCROLL_AMOUNT,
)
from state import Board
from dispatch import call_role, RoleSpec
from observer import observe
from actions import execute_verb, VERBS
import log

PLANNER = RoleSpec("planner", 8000, BUDGET_PLANNER_OUT)
ACTOR = RoleSpec("actor", 8000, BUDGET_ACTOR_OUT)
VERIFIER = RoleSpec("verifier", 8000, BUDGET_VERIFIER_OUT)
REFLECTOR = RoleSpec("reflector", 16000, BUDGET_REFLECTOR_OUT)

_halt_count: int = 0
_last_reflect: int = 0


def run(board: Board, interrupted: Callable[[], bool]) -> bool:
    global _halt_count, _last_reflect
    _halt_count = 0
    _last_reflect = 0

    log.emit("start", {"goal": board.goal, "budget": log.budget()})

    while not log.exhausted() and not interrupted():
        result = _cycle(board)
        if result == "done":
            log.emit("complete", {"goal": board.goal, "events": log.count()})
            board.save()
            return True
        if result == "halt":
            log.emit("halt", {"stagnation": board.stagnation_score, "events": log.count()})
            board.save()
            return False
        board.save()
        time.sleep(DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count()})
    board.save()
    return False


def _cycle(board: Board) -> str:
    global _halt_count

    if board.stagnation_score >= STAGNATION_HALT_THRESHOLD:
        _halt_count += 1
        if _halt_count >= STAGNATION_HALT_SUSTAINED:
            return "halt"
    else:
        _halt_count = 0

    if board.lorenz_wing_crossed:
        board.lorenz_wing_crossed = False
        board.plan_steps = []
        board.plan_index = 0
        board.notes = ["DIVERGE: previous approach failed. Try a completely different method."]
        log.emit("lorenz.fork", {"x": board.lorenz_x, "stagnation": board.stagnation_score})

    if board.pid_output > REFLECT_THRESHOLD:
        _maybe_reflect(board)

    _observe(board)

    if log.exhausted():
        return "continue"

    return _plan_act(board)


def _observe(board: Board) -> None:
    try:
        obs = observe()
        board.record_screen(obs.context_text, obs.semantic_hash, obs.book, obs.focused_title)
        log.emit("observe", {"hash": obs.semantic_hash, "focused": obs.focused_title, "chars": len(obs.context_text)})
    except Exception as e:
        board.screen = f"OBSERVE_FAILED: {e}"
        board.on_failure()
        log.emit("observe.fail", {"error": str(e)})


def _plan_act(board: Board) -> str:
    context = board.context("planner")
    plan = _call_role("planner", PLANNER, context)
    if plan is None:
        board.on_failure()
        return "continue"

    mode = str(plan.get("mode", "direct"))
    next_action = str(plan.get("next_action", ""))

    sequence = plan.get("sequence", [])
    if isinstance(sequence, list) and sequence and not board.plan_steps:
        board.plan_steps = [str(s) for s in cast(list[Any], sequence) if str(s).strip()]
        board.plan_index = 0

    log.emit("plan", {"mode": mode, "action": next_action, "step": board.plan_index, "steps": len(board.plan_steps)})

    if mode == "done":
        return _verify(board, next_action or "planner declared done")

    return _act(board, next_action)


def _act(board: Board, instruction: str) -> str:
    context = board.context("actor", instruction)
    actor_out = _call_role("actor", ACTOR, context)
    if actor_out is None:
        board.on_failure()
        return "continue"

    board.actor_observe = str(actor_out.get("observe", ""))
    board.actor_conclusion = str(actor_out.get("conclusion", ""))

    raw_actions = actor_out.get("actions", [])
    actions: list[dict[str, Any]] = cast(list[dict[str, Any]], raw_actions) if isinstance(raw_actions, list) else []

    if board.actor_conclusion == "DONE" and not actions:
        board.on_success()
        if board.on_last_step():
            return _verify(board, f"actor done: {board.actor_observe}")
        board.advance_step()
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
        if board.on_last_step():
            return _verify(board, f"actions succeeded: {board.actor_observe}")

    return "continue"


def _verify(board: Board, evidence: str) -> str:
    context = board.context("verifier")
    result = _call_role("verifier", VERIFIER, context)
    if result is None:
        board.on_failure()
        return "continue"
    verdict = str(result.get("verdict", "denied"))
    log.emit("verify", {"verdict": verdict, "evidence": str(result.get("evidence", ""))[:200]})
    if verdict == "confirmed":
        return "done"
    board.on_failure()
    return "continue"


def _maybe_reflect(board: Board) -> None:
    global _last_reflect
    elapsed = log.count() - _last_reflect
    if elapsed < REFLECT_MIN_INTERVAL:
        return
    if board.consecutive_failures < REFLECT_MIN_FAILURES:
        return
    budget_ratio = log.count() / max(log.budget(), 1)
    if budget_ratio > REFLECT_BUDGET_GATE:
        return
    _last_reflect = log.count()
    context = board.context("reflector")
    result = _call_role("reflector", REFLECTOR, context)
    if result:
        diagnosis = str(result.get("diagnosis", ""))
        lesson = str(result.get("lesson", ""))
        log.emit("reflect", {"diagnosis": diagnosis, "lesson": lesson})


def _call_role(role: str, spec: RoleSpec, context: str) -> dict[str, Any] | None:
    try:
        return call_role(spec, context)
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
