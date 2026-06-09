from __future__ import annotations
from typing import Any, cast

from agents import AgentResult
from config import BUDGET_ACTOR_OUT, DEFAULT_SCROLL_AMOUNT
from context import render_context
from dispatch import call_role, RoleSpec
from actions import execute_verb, VERBS
import log


SPEC = RoleSpec("actor", 8000, BUDGET_ACTOR_OUT)


class ActorAgent:
    name: str = "actor"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        instruction = board.last_instruction or (board.plan_steps[board.plan_index] if board.plan_steps else "")
        if not instruction:
            return AgentResult(
                writes={"consecutive_failures": board.consecutive_failures + 1},
                event_phase="actor.error",
                event_data={"error": "no instruction"},
            )

        direct = _try_direct(instruction, board)
        if direct is not None:
            return direct

        context = render_context(board, "actor", instruction)
        actor_out = _call(board, context)
        if actor_out is None:
            return AgentResult(
                writes={"consecutive_failures": board.consecutive_failures + 1},
                event_phase="actor.error",
                event_data={"error": "no response"},
            )

        conclusion = str(actor_out.get("conclusion", ""))
        raw_actions = actor_out.get("actions", [])
        actions: list[dict[str, Any]] = cast(list[dict[str, Any]], raw_actions) if isinstance(raw_actions, list) else []

        writes: dict[str, Any] = {
            "actor_conclusion": conclusion,
            "role_calls": _inc(board.role_calls, "actor"),
            "total_role_calls": board.total_role_calls + 1,
            "last_outputs": {**board.last_outputs, "actor": f"conclusion={conclusion} actions={len(actions)}"},
        }

        if conclusion == "DONE" and not actions:
            writes["consecutive_failures"] = 0
            writes["plan_index"] = board.plan_index + 1
            writes["pid_integral"] = 0.0
            return AgentResult(
                writes=writes, next_agent="planner",
                event_phase="actor",
                event_data={"conclusion": "DONE", "actions": 0},
            )

        if conclusion == "CANNOT":
            writes["consecutive_failures"] = board.consecutive_failures + 1
            writes["plan_steps"] = []
            writes["plan_index"] = 0
            writes["requested_next"] = "planner"
            return AgentResult(
                writes=writes, next_agent="planner",
                event_phase="actor",
                event_data={"conclusion": "CANNOT", "actions": 0},
            )

        had_failure = False
        for action in actions:
            verb = str(action.get("verb", ""))
            target = str(action.get("target", ""))
            value = str(action.get("value", ""))
            args = _build_args(verb, target, value)

            if verb not in VERBS:
                _record(board, writes, verb, False, f"unknown verb: {verb}")
                had_failure = True
                break

            result = execute_verb(verb, args, board.screen_elements, board)
            _record(board, writes, verb, result.success, result.observation)
            log.emit("action", {"verb": verb, "ok": result.success, "obs": result.observation[:100]})

            if not result.success:
                had_failure = True
                break

        if had_failure:
            writes["consecutive_failures"] = board.consecutive_failures + 1
        else:
            writes["consecutive_failures"] = 0
            writes["plan_index"] = board.plan_index + 1
            writes["pid_integral"] = 0.0

        writes["requested_next"] = "planner"
        return AgentResult(
            writes=writes, next_agent="planner",
            event_phase="actor",
            event_data={"conclusion": conclusion, "actions": len(actions)},
        )


def _try_direct(instruction: str, board: Any) -> AgentResult | None:
    parts = instruction.split(None, 2)
    if not parts:
        return None
    verb = parts[0].lower()
    if verb not in VERBS:
        return None
    if verb in ("click", "write", "scroll") and len(parts) >= 2:
        target = parts[1].strip("[]")
        if not target.isdigit():
            return None
        value = parts[2] if len(parts) > 2 else ""
    elif verb in ("hotkey", "press"):
        value = parts[1] if len(parts) > 1 else ""
        target = ""
    elif verb == "wait":
        target = parts[1] if len(parts) > 1 else "1"
        value = ""
    elif verb == "focus":
        target = ""
        value = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif verb == "cmd":
        target = ""
        value = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif verb == "write_file" and len(parts) >= 3:
        target = parts[1]
        value = parts[2]
    elif verb == "read_file":
        target = parts[1] if len(parts) > 1 else ""
        value = ""
    else:
        return None

    args = _build_args(verb, target, value)
    result = execute_verb(verb, args, board.screen_elements, board)

    writes: dict[str, Any] = {
        "last_verb": verb,
        "last_success": result.success,
        "last_observation": result.observation,
        "role_calls": _inc(board.role_calls, "actor"),
        "total_role_calls": board.total_role_calls + 1,
        "last_outputs": {**board.last_outputs, "actor": f"direct={verb} ok={result.success}"},
        "requested_next": "planner",
    }
    _append_sig(board, writes, verb)
    _append_history(board, writes, verb, result.success, result.observation)

    if result.success:
        writes["consecutive_failures"] = 0
        writes["plan_index"] = board.plan_index + 1
        writes["pid_integral"] = 0.0
    else:
        writes["consecutive_failures"] = board.consecutive_failures + 1

    log.emit("action", {"verb": verb, "ok": result.success, "obs": result.observation[:100], "direct": True})
    return AgentResult(
        writes=writes, next_agent="planner",
        event_phase="actor",
        event_data={"conclusion": "direct", "verb": verb, "ok": result.success},
    )


def _record(board: Any, writes: dict[str, Any], verb: str, success: bool, obs: str) -> None:
    writes["last_verb"] = verb
    writes["last_success"] = success
    writes["last_observation"] = obs
    _append_sig(board, writes, verb)
    _append_history(board, writes, verb, success, obs)


def _append_sig(board: Any, writes: dict[str, Any], verb: str) -> None:
    from config import REPETITION_WINDOW
    sigs = list(board.recent_sigs)
    sigs.append(verb)
    if len(sigs) > REPETITION_WINDOW:
        sigs = sigs[-REPETITION_WINDOW:]
    writes["recent_sigs"] = sigs


def _append_history(board: Any, writes: dict[str, Any], verb: str, success: bool, obs: str) -> None:
    from config import MAX_HISTORY
    history = list(board.history)
    history.append({"verb": verb, "ok": success, "obs": obs[:1000]})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    writes["history"] = history


def _build_args(verb: str, target: str, value: str) -> dict[str, Any]:
    target = target.strip("[]")
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


def _call(board: Any, context: str) -> dict[str, Any] | None:
    try:
        return call_role(SPEC, context, temperature=board.effective_temperature())
    except Exception as e:
        log.emit("actor.error", {"type": type(e).__name__, "msg": str(e)[:200]})
        return None


def _inc(calls: dict[str, int], role: str) -> dict[str, int]:
    result = dict(calls)
    result[role] = result.get(role, 0) + 1
    return result
