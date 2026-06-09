from __future__ import annotations

from config import ZERO_INT, ONE_INT, TWO_INT
import json
import subprocess
import sys
import time
import traceback
import uuid

from typing import Any, Callable, cast

from config import (
    BASE_DIR, DELAY_BETWEEN_ITERATIONS,
    BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT,
    BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT,
    BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT,
    BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT,
    STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REFLECT_THRESHOLD,
    MAX_PARALLEL_CHILDREN_EXACT, MAX_PARALLEL_CHILDREN_DEFAULT,
    REFLECT_MIN_ITERATION_INTERVAL, REFLECT_MIN_CONSECUTIVE_FAILURES,
    REFLECT_MIN_EXPECTATION_MISSES, REFLECT_MIN_REPETITION_SCORE,
    AGENT_ID_HEX_LENGTH, DEFAULT_SCROLL_AMOUNT, DEFAULT_WAIT_SECONDS,
)
from state import Blackboard, AgentHandle
from lessons import Lessons
from dispatch import call_role, RoleSpec
from observer import observe
from actions import execute_verb, VERBS
from llm import get_backend
from persistence import save_snapshot
from log import log
from stop_signal import stop_requested
from persistence import budget_exhausted, event_count
from self_evolution import process_reflection_result
import tui


PLANNER_SPEC = RoleSpec("planner", BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT)
ACTOR_SPEC = RoleSpec("actor", BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT)
VERIFIER_SPEC = RoleSpec("verifier", BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT)
REFLECTOR_SPEC = RoleSpec("reflector", BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT)

_stagnation_history: list[float] = []
_last_event: str = ""
_last_reflect_iteration: int = -1000000
_prompt_mutations_enabled: bool = False




def _verifier_response_consistent(result: dict[str, Any]) -> bool:
    return str(result.get("verdict", "")) in ("confirmed", "denied")


def _is_backend_unavailable(exception_type: str, error: str) -> bool:
    lower = f"{exception_type} {error}".lower()
    markers = (
        "setup command failed",
        "wsl/service/e_unexpected",
        "protocol version mismatch",
        "no sessionid returned",
        "process not running",
        "connection refused",
        "failed to establish",
        "no connection could be made",
        "client shut down",
    )
    return any(marker in lower for marker in markers)


def _backend_unavailable_recent(board: Blackboard) -> bool:
    if board.last_verb == "backend_unavailable":
        return True
    return any("_backend_unavailable" in error or "[backend_unavailable]" in error for error in board.errors[-TWO_INT:])


def _handle_role_call_failure(board: Blackboard, role: str, exception_type: str, error: str) -> str:
    if _is_backend_unavailable(exception_type, error):
        board.record_error(f"{role}_backend_unavailable", error)
        board.record_action(
            "backend_unavailable",
            {"role": role, "backend": get_backend(), "exception_type": exception_type},
            False,
            f"{role} backend unavailable: {exception_type}: {error}",
        )
        board.record_failure()
        log(board.iteration, "backend.unavailable", "ending run until backend is available", {"role": role, "backend": get_backend(), "exception_type": exception_type, "error": error})
        _report_status(board.agent_id, "failed", error=f"backend_unavailable:{exception_type}")
        return "failed"
    board.record_error(f"{role}_role_error", error)
    board.record_action("role_error", {"role": role, "exception_type": exception_type}, False, f"{role} role error: {exception_type}: {error}")
    board.record_failure()
    return "continue"


def _handle_role_stop(board: Blackboard, role: str, error: str) -> str:
    log(board.iteration, "stop.signal", "stop requested during role call", {"role": role, "error": error})
    _report_status(board.agent_id, "failed", error="stop_signal")
    return "failed"


def run(board: Blackboard, *, interrupted: Callable[[], bool] = lambda: False, prompt_mutations_enabled: bool | None = None) -> bool:
    global _last_event, _prompt_mutations_enabled
    import config
    board.ensure_goal_wrapped()
    _prompt_mutations_enabled = config.PROMPT_MUTATIONS_ENABLED if prompt_mutations_enabled is None else prompt_mutations_enabled
    config.PROMPT_MUTATIONS_ENABLED = _prompt_mutations_enabled
    halt_counter = ZERO_INT
    is_main = board.agent_id == "main"
    return _loop(board, interrupted, halt_counter, is_main)


def _loop(board: Blackboard, interrupted: Callable[[], bool], halt_counter: int, is_main: bool) -> bool:
    global _last_event

    while True:
        if _handle_stop_signal(board, is_main):
            return False

        if interrupted():
            log(board.iteration, "run", "interrupted")
            _report_status(board.agent_id, "failed", error="interrupted")
            if is_main:
                tui.render(board, _stagnation_history, "STOP:interrupt")
            return False

        if budget_exhausted():
            log(board.iteration, "budget.exhausted", "event budget reached", {"events": event_count()})
            _last_event = "BUDGET"
            if is_main:
                tui.render(board, _stagnation_history, _last_event)
            _report_status(board.agent_id, "failed", error="event_budget_exhausted")
            return False

        board.iteration += ONE_INT
        board.clear_signals()
        log(board.iteration, "iteration.start", "iteration started", {"stagnation_score": board.stagnation_score, "pid_output": board.pid_output, "attractor_energy": board.attractor_energy, "lorenz": {"x": board.lorenz_x, "y": board.lorenz_y, "z": board.lorenz_z}})

        if board.stagnation_score >= STAGNATION_HALT_THRESHOLD:
            halt_counter += ONE_INT
            if halt_counter >= STAGNATION_HALT_SUSTAINED:
                log(board.iteration, "halt", f"stagnation={board.stagnation_score:.2f} sustained={halt_counter}")
                _last_event = "HALT"
                if is_main:
                    tui.render(board, _stagnation_history, _last_event)
                _try_spawn_successor(board)
                _report_status(board.agent_id, "failed", error="stagnation_halt")
                return False
        else:
            halt_counter = ZERO_INT

        _process_inbox(board)
        _process_children(board)

        if board.agent_id == "main" and board.mode == "coordinate" and board.active_children_count() > ZERO_INT:
            done_n = sum(ONE_INT for h in board.children.values() if h.state == "done")
            fail_n = sum(ONE_INT for h in board.children.values() if h.state == "failed")
            _last_event = "COORD:wait"
            log(
                board.iteration,
                "coordinate.wait",
                f"running={board.active_children_count()} done={done_n} failed={fail_n} agents={list(board.children.keys())}",
            )
            if is_main:
                tui.render(board, _stagnation_history, _last_event)
            log(board.iteration, "iteration.end", f"stagnation={board.stagnation_score:.3f} pid={board.pid_output:.3f}")
            save_snapshot(board.get_persistable_snapshot())
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            continue

        result = _phase_observe(board)
        if result == "done":
            _last_event = "DONE"
            if is_main:
                tui.render(board, _stagnation_history, _last_event)
            return True
        if result == "failed":
            _last_event = "FAIL"
            if is_main:
                tui.render(board, _stagnation_history, _last_event)
            return False

        _stagnation_history.append(board.stagnation_score)

        if board.lorenz_wing_crossed:
            board.last_instruction = ""
            board.lorenz_wing_crossed = False
            _last_event = "LORENZ:fork"
            log(board.iteration, "lorenz.fork", "wing crossing forced replan", {"lorenz_x": board.lorenz_x, "stagnation": board.stagnation_score})

        if board.pid_output > REFLECT_THRESHOLD and _maybe_phase_reflect(board, "pid"):
            _last_event = "PID:reflect"
            log(board.iteration, "pid.reflect", f"pid={board.pid_output:.2f}")

        if is_main:
            tui.render(board, _stagnation_history, _last_event)
            for cmd in tui.poll_commands():
                if cmd.startswith("force_advance:") and board.plan_steps:
                    board.plan_step_index = min(board.plan_step_index + ONE_INT, len(board.plan_steps) - ONE_INT)
                    board.reset_pid_integral()
                    log(board.iteration, "tui.force_advance", f"step={board.plan_step_index}")
        log(board.iteration, "iteration.end", f"stagnation={board.stagnation_score:.3f} pid={board.pid_output:.3f}")
        save_snapshot(board.get_persistable_snapshot())
        time.sleep(DELAY_BETWEEN_ITERATIONS)


def _phase_observe(board: Blackboard) -> str:
    if not board.acquire_screen():
        if board.agent_id == "main":
            board.screen_valid = False
            _last_event = "WAIT:lock"
            log(board.iteration, "observe.wait_lock", "main blocked on screen lock", {"agent_id": board.agent_id})
            return "continue"
        shared = board.load_shared_screen()
        if shared:
            board.record_screen(shared[ZERO_INT], shared[ONE_INT], {})
            board.screen_valid = True
            board.focused_window = shared[TWO_INT]
            from artifacts import materialize_text
            shared_ref = materialize_text(shared[ZERO_INT], board.agent_id, board.iteration, "observe.shared", ("context_text",))
            log(board.iteration, "observe.shared", "loaded shared screen snapshot", {"content_hash": shared[ONE_INT], "focused_window": shared[TWO_INT], "context_text": shared_ref, "context_chars": len(shared[ZERO_INT])})
        else:
            board.screen_valid = False
            log(board.iteration, "observe.wait_lock", "no screen lock and no shared snapshot", {"agent_id": board.agent_id})
    else:
        try:
            obs = observe()
            board.record_screen(obs.context_text, obs.semantic_hash, obs.book)
            board.screen_valid = True
            board.focused_window = obs.focused_title
            board.update_screen_stagnation(obs.semantic_hash)
            board.publish_shared_screen()
            from artifacts import materialize_text
            raw_ref = materialize_text(json.dumps({"screen": obs.trace["screen"], "focused": obs.trace["focused"], "windows": obs.trace["windows"], "z_order": obs.trace["z_order"], "probe_regions": obs.trace["probe_regions"], "probe_decision": obs.trace["probe_decision"], "probe_samples": obs.trace["probe_samples"], "tree_decision": obs.trace["tree_decision"], "tree_samples": obs.trace["tree_samples"], "timing": obs.trace["timing"]}, ensure_ascii=False, separators=(",", ":")), board.agent_id, board.iteration, "observe.raw", ("data",))
            filtered_ref = materialize_text(json.dumps({"merged_nodes": len(obs.trace["merged_nodes"]), "classified_nodes": len(obs.trace["classified_nodes"]), "book_entries": len(obs.trace["book"]), "book_ids": sorted(obs.trace["book"].keys())}, ensure_ascii=False, separators=(",", ":")), board.agent_id, board.iteration, "observe.filtered", ("data",))
            rendered_ref = materialize_text(obs.context_text, board.agent_id, board.iteration, "observe.rendered", ("context_text",))
            semantic_ref = materialize_text(obs.trace["semantic_text"], board.agent_id, board.iteration, "observe.rendered", ("semantic_text",))
            log(board.iteration, "observe.raw", "raw screen observation data", raw_ref)
            log(board.iteration, "observe.filtered", "screen observation after merge and classification", filtered_ref)
            log(board.iteration, "observe.rendered", "rendered screen context", {"content_hash": obs.content_hash, "semantic_hash": obs.semantic_hash, "semantic_text": semantic_ref, "focused_title": obs.focused_title, "windows": obs.windows, "context_text": rendered_ref, "context_chars": len(obs.context_text)})
        except Exception as e:
            board.release_screen()
            board.screen_valid = False
            board.record_screen(f"OBSERVE_FAILED: {e}", f"obsfail-{board.iteration}", {})
            board.record_error("observe_fail", str(e))
            board.record_failure()
            log(board.iteration, "observe.fail", "screen observation failed", {"exception_type": type(e).__name__, "exception": str(e), "traceback": traceback.format_exc()})

    result = _phase_plan_act(board)
    board.release_screen()
    return result


def _coordinate_children_ready(board: Blackboard) -> bool:
    if board.agent_id != "main" or not board.children:
        return False
    if board.verifier_denied_last:
        return False
    if not board.all_children_done() or board.any_children_failed():
        return False
    return len(board.completed_subtasks) >= len(board.children)



def _claim_done(board: Blackboard, evidence: str, claim_source: str) -> str:
    board.done_claimed = True
    board.done_evidence = evidence
    verified = _call_verifier(board, claim_source)
    if verified:
        log(board.iteration, "goal.complete", f"evidence={board.done_evidence}")
        _report_status(board.agent_id, "done", result=board.done_evidence)
        return "done"
    if _backend_unavailable_recent(board):
        return "failed"
    board.verifier_denied_last = True
    board.record_failure()
    return "continue"


def _actor_done_should_verify_goal(board: Blackboard) -> bool:
    if not board.plan_steps:
        return True
    return board.plan_step_index >= len(board.plan_steps) - ONE_INT


def _maybe_advance_after_read(board: Blackboard, verb: str, args: dict[str, Any], success: bool) -> None:
    if verb != "read_file" or not success or not board.plan_steps:
        return
    if board.plan_step_index >= len(board.plan_steps):
        return
    path = str(args.get("path", ""))
    base = path.replace("\\", "/").split("/")[-ONE_INT].lower()
    step = board.plan_steps[board.plan_step_index].lower()
    if base and base in step:
        if board.plan_step_index < len(board.plan_steps) - ONE_INT:
            board.plan_step_index += ONE_INT
            board.reset_pid_integral()
            log(board.iteration, "checklist.advance", f"auto read_file={path} step={board.plan_step_index}")


def _normalize_decompose(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in cast(list[Any], raw):
        if isinstance(item, dict):
            item_dict = cast(dict[str, Any], item)
            sub_goal = str(item_dict.get("sub_goal", "")).strip()
            agent_id = str(item_dict.get("agent_id", "")).strip()
            if sub_goal and agent_id:
                out.append({"sub_goal": sub_goal, "agent_id": agent_id})
        elif isinstance(item, str) and item.strip():
            out.append({"sub_goal": item.strip(), "agent_id": f"agent_{uuid.uuid4().hex[:AGENT_ID_HEX_LENGTH]}"})
    return out


def _phase_plan_act(board: Blackboard) -> str:
    global _last_event
    if _coordinate_children_ready(board):
        parts = [f"{item['agent_id']}:{item.get('result', '')}" for item in board.completed_subtasks]
        evidence = "; ".join(parts) if parts else "all parallel children completed"
        log(board.iteration, "coordinate.complete", f"children={list(board.children.keys())} evidence={evidence}")
        _last_event = "COORD:done"
        return _claim_done(board, evidence, "all parallel children completed")

    if board.screen_stagnation >= 3 and board.last_verb == "wait" and board.consecutive_failures == ZERO_INT:
        log(board.iteration, "idle.stagnation", "screen unchanged, skipping planner", {"screen_stagnation": board.screen_stagnation})
        return "continue"

    if _should_continue_actor(board):
        log(board.iteration, "actor.continue", "continuing current actor subtask", {"instruction": board.last_instruction, "last_verb": board.last_verb})
        return _phase_act(board, board.last_instruction)

    context = board.build_context("planner")

    _last_event = "LLM:planner"
    if board.agent_id == "main":
        tui.render(board, _stagnation_history, _last_event)
    plan = _call_llm_role("planner", PLANNER_SPEC, context, board.iteration, board.agent_id)

    if isinstance(plan, dict) and plan.get("__stop_requested__"):
        return _handle_role_stop(board, "planner", str(plan.get("error", "")))

    if isinstance(plan, dict) and plan.get("__role_error__"):
        err = str(plan.get("error", ""))
        exception_type = str(plan.get("exception_type", ""))
        return _handle_role_call_failure(board, "planner", exception_type, err)

    if isinstance(plan, dict) and plan.get("__refusal_detected__"):
        board.record_error("planner_refusal", plan.get("error", ""))
        board.record_action("parse_fail", {}, False, "planner refusal detected")
        board.record_failure()
        return "continue"

    if not plan:
        board.record_error("planner_parse", "planner returned no valid JSON")
        board.record_action("parse_fail", {}, False, "planner returned no valid JSON")
        board.record_failure()
        return "continue"

    mode = str(plan.get("mode", "direct"))
    next_action = str(plan.get("next_action", ""))
    decompose = _normalize_decompose(plan.get("decompose", []))

    board.last_plan_because = str(plan.get("because", ""))
    board.last_instruction = next_action
    log(board.iteration, "planner", "planner decision", {"mode": mode, "because": board.last_plan_because, "next_action": next_action, "plan": plan})

    new_notes = plan.get("notes", [])
    if isinstance(new_notes, list):
        board.notes = [str(n) for n in cast(list[Any], new_notes) if n]
    elif isinstance(new_notes, str) and new_notes.strip():
        board.notes = [new_notes.strip()]

    sequence_raw = plan.get("sequence", [])
    sequence: list[str] = [str(s) for s in cast(list[Any], sequence_raw) if str(s).strip()] if isinstance(sequence_raw, list) else []
    if sequence and not board.plan_steps:
        board.plan_steps = sequence
        board.plan_step_index = ZERO_INT
        log(board.iteration, "checklist.created", "planner created checklist", {"steps": sequence})

    if plan.get("step_advance") and board.plan_steps:
        board.plan_step_index = min(board.plan_step_index + ONE_INT, len(board.plan_steps) - ONE_INT)
        board.reset_pid_integral()
        log(board.iteration, "checklist.advance", f"step={board.plan_step_index}")

    _last_event = f"PLAN:{mode}"

    if mode == "done" and board.verifier_denied_last:
        mode = "direct"
        next_action = "The verifier denied your last completion claim. Address feedback before claiming done again."
        board.verifier_denied_last = False

    if mode == "done":
        return _claim_done(board, str(plan.get("because", next_action)), "planner claimed mode=done")

    if mode == "parallel" and decompose:
        if board.agent_id != "main":
            log(board.iteration, "decompose.blocked", f"parallel mode blocked for child agent {board.agent_id}")
            mode = "direct"
            next_action = f"Complete the assigned sub-goal using GUI-first actions: {board.goal}"
            decompose = []
        elif board.mode == "coordinate" and board.active_children_count() > ZERO_INT:
            log(board.iteration, "decompose.skip", f"running={board.active_children_count()}")
            board.record_success()
            return "continue"
        board.mode = "coordinate"
        _execute_decomposition(board, decompose)
        board.record_success()
        return "continue"

    return _phase_act(board, next_action)


def _phase_act(board: Blackboard, instruction: str) -> str:
    global _last_event
    _last_event = "LLM:actor"
    if board.agent_id == "main":
        tui.render(board, _stagnation_history, _last_event)
    context = board.build_context("actor", instruction)
    actor_out = _call_llm_role("actor", ACTOR_SPEC, context, board.iteration, board.agent_id)

    if isinstance(actor_out, dict) and actor_out.get("__stop_requested__"):
        return _handle_role_stop(board, "actor", str(actor_out.get("error", "")))

    if isinstance(actor_out, dict) and actor_out.get("__role_error__"):
        err = str(actor_out.get("error", ""))
        exception_type = str(actor_out.get("exception_type", ""))
        return _handle_role_call_failure(board, "actor", exception_type, err)

    if isinstance(actor_out, dict) and actor_out.get("__refusal_detected__"):
        board.record_error("actor_refusal", actor_out.get("error", ""))
        board.record_action("parse_fail", {}, False, "actor refusal detected")
        board.record_failure()
        return "continue"

    if not actor_out:
        board.record_error("actor_parse", "actor returned no valid JSON")
        board.record_action("parse_fail", {}, False, "actor returned no valid JSON")
        board.record_failure()
        return "continue"

    board.actor_observe = actor_out.get("observe", "")
    board.actor_conclusion = actor_out.get("conclusion", "")
    board.actor_reason = actor_out.get("reason", "")
    board.last_expect = actor_out.get("expect", "")
    log(board.iteration, "actor", "actor decision", {"observe": board.actor_observe, "conclusion": board.actor_conclusion, "reason": board.actor_reason, "expect": board.last_expect, "actions": actor_out.get("actions", []), "response": actor_out})

    if board.actor_conclusion == "UNEXPECTED":
        board.expectation_miss_streak += ONE_INT
    else:
        board.expectation_miss_streak = ZERO_INT

    raw_actions_raw = actor_out.get("actions", [])
    raw_actions: list[Any] = cast(list[Any], raw_actions_raw) if isinstance(raw_actions_raw, list) else []
    if board.actor_conclusion == "DONE" and not raw_actions:
        board.record_success()
        board.last_instruction = ""
        _last_event = "ACTOR:done"
        if board.plan_steps and board.plan_step_index < len(board.plan_steps) - ONE_INT:
            board.plan_step_index += ONE_INT
            board.reset_pid_integral()
            log(board.iteration, "checklist.advance", f"actor_done step={board.plan_step_index}")
        if _actor_done_should_verify_goal(board):
            evidence = f"actor reported instruction done: {board.actor_observe or board.actor_reason}"
            return _claim_done(board, evidence, "actor emitted DONE")
        return "continue"

    if not raw_actions and board.actor_conclusion == "UNEXPECTED":
        board.record_action("no_match", {}, False, "actor could not resolve element")
        board.record_failure()
        return "continue"

    iteration_had_failure = False

    for action_obj_raw in raw_actions:
        if not isinstance(action_obj_raw, dict):
            continue
        action_obj = cast(dict[str, Any], action_obj_raw)
        verb = action_obj.get("verb", "")
        target = action_obj.get("target", "")
        value = action_obj.get("value", "")

        args = _build_args(verb, target, value)
        if verb not in VERBS:
            board.record_action(verb, args, False, f"unknown verb: {verb}")
            log(board.iteration, "action.result", "unknown action verb", {"verb": verb, "args": args, "raw_action": action_obj, "success": False, "observation": f"unknown verb: {verb}"})
            iteration_had_failure = True
            break
        if board.stagnation_blocks_action(verb, target):
            board.record_action(verb, args, False, f"STAGNATION BLOCKED: {verb}:{target}")
            log(board.iteration, "action.result", "action blocked by stagnation", {"verb": verb, "args": args, "raw_action": action_obj, "success": False, "observation": f"STAGNATION BLOCKED: {verb}:{target}"})
            iteration_had_failure = True
            break

        log(board.iteration, "action.request", "executing action", {"verb": verb, "args": args, "raw_action": action_obj})
        if stop_requested():
            log(board.iteration, "stop.signal", "stop requested before action", {"agent_id": board.agent_id})
            iteration_had_failure = True
            break
        result = execute_verb(verb, args, board.screen_elements, board)
        board.record_action(verb, args, result.success, result.observation)
        log(board.iteration, "action.result", "action completed", {"verb": verb, "args": args, "result": result})
        _last_event = f"{verb}:{'OK' if result.success else 'FAIL'}"
        if verb == "spawn_agent" and result.success and board.children:
            board.mode = "coordinate"
        _maybe_advance_after_read(board, verb, args, result.success)

        if not result.success:
            iteration_had_failure = True
            break

    if iteration_had_failure:
        board.record_failure()
        board.failed_step_index = board.plan_step_index
        _last_event = f"FAIL:{board.consecutive_failures}"
        if board.should_replan(board.failed_step_index):
            log(board.iteration, "jacobian", f"replan triggered at step {board.failed_step_index} dominant={board.jacobian_dominant_step()}")
            _maybe_phase_reflect(board, "replan")
    else:
        board.record_success()
        _last_event = "OK"
        should_verify = (
            board.actor_conclusion == "DONE"
            or (board.plan_steps and board.plan_step_index >= len(board.plan_steps) - ONE_INT)
        )
        if should_verify:
            evidence = f"actions succeeded on final step: {board.actor_observe or instruction}"
            log(board.iteration, "verify.proactive", "proactive verification after success", {"step_index": board.plan_step_index, "conclusion": board.actor_conclusion, "plan_steps": len(board.plan_steps)})
            return _claim_done(board, evidence, "proactive verify after actions")

    return "continue"


def _should_continue_actor(board: Blackboard) -> bool:
    if not board.last_instruction:
        return False
    if board.actor_conclusion == "DONE":
        return False
    if board.verifier_denied_last or board.consecutive_failures > ZERO_INT:
        return False
    if not board.last_success:
        return False
    if board.last_verb in ("role_error", "parse_fail", "no_match"):
        return False
    if board.last_verb in ("click", "focus", "hotkey", "press", "scroll", "wait") and board.screen_stagnation > ZERO_INT:
        return False
    if board.detect_repetition_in_history():
        return False
    return True


def _maybe_phase_reflect(board: Blackboard, reason: str) -> bool:
    global _last_reflect_iteration
    if _backend_unavailable_recent(board):
        log(board.iteration, "reflect.skip", "backend unavailable", {"reason": reason, "last_verb": board.last_verb})
        return False
    elapsed = board.iteration - _last_reflect_iteration
    if elapsed < REFLECT_MIN_ITERATION_INTERVAL:
        log(board.iteration, "reflect.skip", "minimum reflection interval not met", {"reason": reason, "elapsed": elapsed, "minimum": REFLECT_MIN_ITERATION_INTERVAL})
        return False
    if reason == "pid":
        repeated_without_screen_progress = board.repetition_score >= REFLECT_MIN_REPETITION_SCORE and board.screen_stagnation > ZERO_INT
        strong_signal = (
            board.consecutive_failures >= REFLECT_MIN_CONSECUTIVE_FAILURES
            or board.expectation_miss_streak >= REFLECT_MIN_EXPECTATION_MISSES
            or repeated_without_screen_progress
        )
        if not strong_signal:
            log(
                board.iteration,
                "reflect.skip",
                "pid signal below reflection evidence threshold",
                {
                    "consecutive_failures": board.consecutive_failures,
                    "expectation_miss_streak": board.expectation_miss_streak,
                    "repetition_score": board.repetition_score,
                    "screen_stagnation": board.screen_stagnation,
                },
            )
            return False
    _last_reflect_iteration = board.iteration
    _phase_reflect(board)
    return True


def _phase_reflect(board: Blackboard) -> None:
    global _last_event, _prompt_mutations_enabled
    _last_event = "LLM:reflector"
    if board.agent_id == "main":
        tui.render(board, _stagnation_history, _last_event)
    context = board.build_context("reflector")
    try:
        result = call_role(REFLECTOR_SPEC, context, board.iteration, board.agent_id)
        log(board.iteration, "reflector", "reflector decision", {"response": result})
        board.console_log.append(f"[REFLECT] {result.get('diagnosis', '')}")
        evolution_result = process_reflection_result(board, result, prompt_mutations_enabled=_prompt_mutations_enabled)
        log(board.iteration, "reflection.pipeline", "linearized reflection pipeline completed", evolution_result)
    except Exception as e:
        if "stop signal requested" in str(e).lower():
            log(board.iteration, "stop.signal", "stop requested during reflector call", {"error": str(e)})
            return
        board.record_error("reflector_fail", str(e))
        log(board.iteration, "reflector.error", "reflector failed", {"exception_type": type(e).__name__, "exception": str(e), "traceback": traceback.format_exc()})


def _try_spawn_successor(board: Blackboard) -> None:
    board.plan_steps = []
    board.plan_step_index = ZERO_INT
    board.reset_pid_integral()
    board.last_instruction = ""

def _handle_stop_signal(board: Blackboard, is_main: bool) -> bool:
    if not stop_requested():
        return False
    log(board.iteration, "stop.signal", "stop requested via comms stop file", {"agent_id": board.agent_id})
    _report_status(board.agent_id, "failed", error="stop_signal")
    if is_main:
        tui.render(board, _stagnation_history, "STOP:signal")
    return True


def _process_inbox(board: Blackboard) -> None:
    for cmd in board.poll_inbox():
        cmd_type = cmd.get("type", "")
        payload = cmd.get("payload", "")
        if cmd_type == "goal_rewrite":
            board.rewrite_goal(payload)
        elif cmd_type == "hint":
            board.problem = payload
        elif cmd_type == "inject_lesson":
            store = Lessons()
            store.add_lesson(str(payload), role="planner", issue_key="manual", diagnosis="manual injection", source_iteration=board.iteration)
            store.save()
        elif cmd_type == "set_chaos":
            try:
                board.stagnation_score = float(payload)
            except ValueError:
                pass
        elif cmd_type == "kill":
            raise SystemExit(ZERO_INT)


def _process_children(board: Blackboard) -> None:
    for ev in board.poll_children():
        log(board.iteration, "child.event", f"{ev['agent_id']}:{ev['state']}")
        board.console_log.append(f"[CHILD] {ev['agent_id']}: {ev['state']}")

    if board.all_children_done() and not board.pending_subtasks and board.mode == "coordinate":
        if not board.any_children_failed():
            board.mode = "direct"
            board.last_verb = ""


def _execute_decomposition(board: Blackboard, decompose: list[dict[str, Any]]) -> None:
    spawned = ZERO_INT
    max_spawn = MAX_PARALLEL_CHILDREN_EXACT if "exactly 4 parallel" in board.goal.lower() else MAX_PARALLEL_CHILDREN_DEFAULT
    for subtask in decompose:
        if spawned >= max_spawn:
            break
        sub_goal = subtask.get("sub_goal", "")
        agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:AGENT_ID_HEX_LENGTH]}")
        if not sub_goal:
            continue
        aid_lower = agent_id.lower()
        if aid_lower in ("main", "main_sync") or aid_lower.startswith("main_"):
            log(board.iteration, "child.spawn.skip", f"{agent_id} reserved for parent")
            continue
        sub_lower = sub_goal.lower()
        if "main waits" in sub_lower or "child_done events" in sub_lower:
            log(board.iteration, "child.spawn.skip", f"{agent_id} parent-only sub_goal")
            continue
        existing = board.children.get(agent_id)
        if existing and existing.state == "running":
            continue
        handle = _spawn_child(agent_id, sub_goal, board.iteration)
        if handle:
            board.children[agent_id] = handle
            spawned += ONE_INT

    log(board.iteration, "decompose", f"subtasks={len(decompose)} agents={list(board.children.keys())}")


def _spawn_child(agent_id: str, goal: str, iteration: int) -> AgentHandle | None:
    from persistence import register_agent
    original_goal = goal
    cmd = [sys.executable, str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", agent_id]
    _append_prompt_mutation_flag(cmd)
    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
        register_agent(agent_id, proc.pid)
        log(iteration, "child.spawn", f"{agent_id} pid={proc.pid}", {"original_goal": original_goal, "goal": goal})
        return AgentHandle(agent_id=agent_id, goal=goal, pid=proc.pid, status_file=BASE_DIR / "blackboard_state.json")
    except Exception as e:
        log(iteration, "child.spawn.error", str(e))
        return None


def _append_prompt_mutation_flag(cmd: list[str]) -> None:
    import config
    if config.PROMPT_MUTATIONS_ENABLED:
        cmd.append("--enable-prompt-mutations")


def _report_status(agent_id: str, state: str, result: str = "", error: str = "") -> None:
    if not agent_id or agent_id == "main":
        return
    from persistence import post_event
    verb = "child_done" if state == "done" else "child_failed"
    post_event(verb, agent_id, "main", {"result": result, "error": error})


def _call_llm_role(role: str, spec: RoleSpec, context: str, iteration: int, agent_id: str = "main") -> dict[str, Any] | None:
    try:
        result = call_role(spec, context, iteration, agent_id)
        log(iteration, f"{role}.response", "role response accepted", {"role": role, "keys": list(result.keys()), "response": result})
        return result
    except Exception as e:
        err_str = str(e)
        log(iteration, f"{role}.error", "role call failed", {"exception_type": type(e).__name__, "exception": err_str, "traceback": traceback.format_exc()})
        if "stop signal requested" in err_str.lower():
            return {"__stop_requested__": True, "error": err_str}
        if any(x in err_str.lower() for x in ["not going to help", "i'm not going to", "cannot assist", "refusal", "safety", "impersonation"]):
            return {"__refusal_detected__": True, "error": err_str}
        return {"__role_error__": True, "exception_type": type(e).__name__, "error": err_str}


def _call_verifier(board: Blackboard, instruction: str = "") -> bool:
    context = board.build_context("verifier", instruction)
    try:
        result = call_role(VERIFIER_SPEC, context, board.iteration, board.agent_id)
        verdict = result.get("verdict", "denied")
        if not _verifier_response_consistent(result):
            log(board.iteration, "verifier.inconsistent", "verifier verdict and failure_type mismatch", {"response": result})
            return False
        log(board.iteration, "verifier", "verifier decision", {"verdict": verdict, "response": result})
        board.console_log.append(f"[VERIFY] {verdict}: {result.get('reason', '')}")
        return verdict == "confirmed"
    except Exception as e:
        exception_type = type(e).__name__
        error = str(e)
        log(board.iteration, "verifier.error", "verifier failed", {"exception_type": exception_type, "exception": error, "traceback": traceback.format_exc()})
        if _is_backend_unavailable(exception_type, error):
            _handle_role_call_failure(board, "verifier", exception_type, error)
        return False


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
            return {"seconds": float(target or value or str(DEFAULT_WAIT_SECONDS))}
        except ValueError:
            return {"seconds": DEFAULT_WAIT_SECONDS}
    if verb == "focus":
        return {"window_title": target or value}
    if verb == "read_file":
        return {"path": target or value}
    if verb == "write_file":
        return {"path": target, "content": value}
    if verb == "spawn_agent":
        return {"goal": value or target}
    if verb == "cmd":
        return {"command": value or target}
    return {}
