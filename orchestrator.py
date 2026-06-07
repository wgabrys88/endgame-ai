from __future__ import annotations

from config import ZERO_INT, ONE_INT, TWO_INT
import subprocess
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
    REFLECT_THRESHOLD, DISTILL_THRESHOLD, PROMPTS_DIR,
    PROMPT_REWRITE_MIN_LENGTH,
    DISTILLATION_ITERATION_OFFSET, DISTILLATION_ITERATION_INTERVAL,
    STUCKNESS_SLOPE_EPSILON,
    MAX_PARALLEL_CHILDREN_EXACT, MAX_PARALLEL_CHILDREN_DEFAULT,
    CHECKLIST_REWRITE_MIN_STEPS, PID_KP_MIN, PID_KP_MAX,
    PID_KI_MIN, PID_KI_MAX, PID_KD_MIN, PID_KD_MAX,
    AGENT_ID_HEX_LENGTH, DEFAULT_SCROLL_AMOUNT, DEFAULT_WAIT_SECONDS,
    CONTEXT_POLICY,
)
from state import Blackboard, AgentHandle
from lessons import Lessons
from dispatch import call_role, RoleSpec
from observer import observe
from actions import execute_verb, VERBS
from llm import get_backend
from persistence import save_snapshot
from log import log
import tui


PLANNER_SPEC = RoleSpec("planner", BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT)
ACTOR_SPEC = RoleSpec("actor", BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT)
VERIFIER_SPEC = RoleSpec("verifier", BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT)
REFLECTOR_SPEC = RoleSpec("reflector", BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT)

_stagnation_history: list[float] = []
_last_event: str = ""
_last_distill_iteration: int = DISTILLATION_ITERATION_OFFSET


def _normalize_used_field(value: str) -> str:
    cleaned = value.split("(", ONE_INT)[ZERO_INT].strip().lower()
    return cleaned.replace(" ", "_").replace("-", "_")


def _path_key(path: str) -> str:
    return path.replace("\\", "/").lower()


def _read_file_goal_path(text: str) -> str:
    import re
    patterns = [
        r"\bread_file\s+with\s+path\s+exactly:?\s+\"([^\"]+)\"",
        r"\bread_file\s+with\s+path\s+exactly:?\s+'([^']+)'",
        r"\bread_file\s+with\s+path\s+exactly:?\s+([^\s]+)",
        r"\buse\s+the\s+read_file\s+verb\s+on\s+\"([^\"]+)\"",
        r"\buse\s+the\s+read_file\s+verb\s+on\s+'([^']+)'",
        r"\buse\s+the\s+read_file\s+verb\s+on\s+([^\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(ONE_INT).strip().strip("\"'").rstrip(".,;")
    return ""


def _read_file_instruction_path(text: str) -> str:
    import re
    match = re.search(r"\bUse\s+read_file\s+with\s+path\s+exactly:\s+(.+?)\.\s+One\s+action\s+only\.", text, re.I)
    if match:
        return match.group(ONE_INT).strip().strip("\"'").rstrip(".,;")
    return ""


def _log_used_fields(role: str, iteration: int, response: dict[str, Any]) -> None:
    used_raw = response.get("used_fields", [])
    used: list[str] = [str(item) for item in cast(list[Any], used_raw)] if isinstance(used_raw, list) else []
    policy_fields = CONTEXT_POLICY.get(role, [])
    policy_set = set(policy_fields)
    accepted_fields: list[str] = []
    unknown_fields: list[str] = []
    for field in used:
        normalized = _normalize_used_field(field)
        if normalized in policy_set:
            accepted_fields.append(normalized)
        else:
            unknown_fields.append(field)
    accepted_set = set(accepted_fields)
    missing_policy_fields = [field for field in policy_fields if field not in accepted_set]
    log(iteration, "role.used_fields", "role declared used fields", {"role": role, "used_fields": used, "accepted_fields": accepted_fields, "unknown_fields": unknown_fields, "missing_policy_fields": missing_policy_fields, "policy_fields": policy_fields})


def _verifier_response_consistent(result: dict[str, Any]) -> bool:
    verdict = str(result.get("verdict", "denied"))
    failure_type = result.get("failure_type")
    if verdict == "confirmed":
        return failure_type is None
    return failure_type is not None


def _prompt_rewrite_valid(role: str, rewrite: str) -> bool:
    lower = rewrite.lower()
    if role == "actor":
        return "{\"observe\"" in rewrite and "used_fields" in lower and "available verbs" in lower
    if role == "planner":
        return "{\"mode\"" in rewrite and "used_fields" in lower and "checklist management" in lower
    if role == "verifier":
        return "{\"verdict\"" in rewrite and "failure_type" in lower and "used_fields" in lower
    return False


def run(board: Blackboard, *, interrupted: Callable[[], bool] = lambda: False) -> bool:
    global _last_event
    halt_counter = ZERO_INT
    is_main = board.agent_id == "main"
    return _loop(board, interrupted, halt_counter, is_main)


def _loop(board: Blackboard, interrupted: Callable[[], bool], halt_counter: int, is_main: bool) -> bool:
    global _last_event, _last_distill_iteration

    while True:
        if interrupted():
            log(board.iteration, "run", "interrupted")
            _report_status(board.agent_id, "failed", error="interrupted")
            if is_main:
                tui.render(board, _stagnation_history, "STOP:interrupt")
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

        _stagnation_history.append(board.stagnation_score)

        if board.pid_output > REFLECT_THRESHOLD:
            _last_event = "PID→REFLECT"
            log(board.iteration, "pid.reflect", f"pid={board.pid_output:.2f}")
            _phase_reflect(board)

        stuckness = (board.stagnation_score * board.stagnation_score) / (abs(board.pid_slope) + STUCKNESS_SLOPE_EPSILON)
        if stuckness > DISTILL_THRESHOLD and (board.iteration - _last_distill_iteration) >= DISTILLATION_ITERATION_INTERVAL:
            _last_event = "PID→DISTILL"
            log(board.iteration, "pid.distill", f"stuckness={stuckness:.2f}")
            _spawn_distillation(board)
            _last_distill_iteration = board.iteration

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
    is_distillation = "DISTILLATION" in board.goal.upper()

    if is_distillation:
        board.record_screen("(distillation mode)", "distill", {})
        board.screen_valid = True
    elif not board.acquire_screen():
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
            log(board.iteration, "observe.shared", "loaded shared screen snapshot", {"content_hash": shared[ONE_INT], "focused_window": shared[TWO_INT], "context_text": shared[ZERO_INT]})
        else:
            board.screen_valid = False
            log(board.iteration, "observe.wait_lock", "no screen lock and no shared snapshot", {"agent_id": board.agent_id})
    else:
        try:
            obs = observe()
            board.record_screen(obs.context_text, obs.content_hash, obs.book)
            board.screen_valid = True
            board.focused_window = obs.focused_title
            board.update_screen_stagnation(obs.content_hash)
            board.publish_shared_screen()
            log(board.iteration, "observe.raw", "raw screen observation data", {"screen": obs.trace["screen"], "focused": obs.trace["focused"], "windows": obs.trace["windows"], "z_order": obs.trace["z_order"], "probe_regions": obs.trace["probe_regions"], "probe_samples": obs.trace["probe_samples"], "probe_nodes_raw": obs.trace["probe_nodes_raw"], "tree_samples": obs.trace["tree_samples"], "tree_nodes_raw": obs.trace["tree_nodes_raw"]})
            log(board.iteration, "observe.filtered", "screen observation after merge and classification", {"merged_nodes": obs.trace["merged_nodes"], "classified_nodes": obs.trace["classified_nodes"], "book": obs.trace["book"]})
            log(board.iteration, "observe.rendered", "rendered screen context", {"content_hash": obs.content_hash, "focused_title": obs.focused_title, "windows": obs.windows, "context_text": obs.context_text})
        except Exception as e:
            board.release_screen()
            board.screen_valid = False
            board.record_screen(f"OBSERVE_FAILED: {e}", f"obsfail-{board.iteration}", {})
            board.record_error("observe_fail", str(e))
            board.record_failure()
            log(board.iteration, "observe.fail", "screen observation failed", {"exception_type": type(e).__name__, "exception": str(e), "traceback": traceback.format_exc()})

    result = _phase_plan_act(board)
    if not is_distillation:
        board.release_screen()
    return result


def _instruction_for_actor(board: Blackboard, next_action: str) -> str:
    import re
    forced_path = _read_file_goal_path(board.original_goal) or _read_file_goal_path(board.goal)
    if forced_path:
        return f"Use read_file with path exactly: {forced_path}. One action only."
    if board.plan_steps and board.plan_step_index < len(board.plan_steps):
        step = board.plan_steps[board.plan_step_index]
        match = re.search(r"read_file\s+(\S+)", step, re.I)
        if match:
            return f"Use read_file with path exactly: {match.group(ONE_INT)}. One action only."
    return next_action


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
    is_distillation = "DISTILLATION" in board.goal.upper()
    role = "distillation" if is_distillation else "planner"
    context = board.build_context(role)

    _last_event = "LLM:planner"
    if board.agent_id == "main":
        tui.render(board, _stagnation_history, _last_event)
    plan = _call_llm_role("planner", PLANNER_SPEC, context, board.iteration)

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
    _log_used_fields("planner", board.iteration, plan)
    log(board.iteration, "planner", "planner decision", {"mode": mode, "because": board.last_plan_because, "next_action": next_action, "plan": plan})

    new_notes = plan.get("notes", [])
    if isinstance(new_notes, list):
        board.notes = [str(n) for n in cast(list[Any], new_notes) if n]
    elif isinstance(new_notes, str) and new_notes.strip():
        board.notes = [new_notes.strip()]

    sequence_raw = plan.get("sequence", [])
    sequence: list[str] = [str(s) for s in cast(list[Any], sequence_raw)] if isinstance(sequence_raw, list) else []
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
        if is_distillation:
            log(board.iteration, "goal.complete", "distillation")
            _report_status(board.agent_id, "done", result=next_action)
            return "done"
        board.done_claimed = True
        board.done_evidence = plan.get("because", next_action)
        verified = _call_verifier(board, "planner claimed mode=done")
        if verified:
            log(board.iteration, "goal.complete", f"evidence={board.done_evidence}")
            _report_status(board.agent_id, "done", result=board.done_evidence)
            return "done"
        board.verifier_denied_last = True
        board.record_failure()
        return "continue"

    if mode == "parallel" and decompose:
        if board.mode == "coordinate" and board.active_children_count() > ZERO_INT:
            log(board.iteration, "decompose.skip", f"running={board.active_children_count()}")
            board.record_success()
            return "continue"
        board.mode = "coordinate"
        _execute_decomposition(board, decompose)
        board.record_success()
        return "continue"

    return _phase_act(board, _instruction_for_actor(board, next_action))


def _phase_act(board: Blackboard, instruction: str) -> str:
    global _last_event
    _last_event = "LLM:actor"
    if board.agent_id == "main":
        tui.render(board, _stagnation_history, _last_event)
    context = board.build_context("actor", instruction)
    actor_out = _call_llm_role("actor", ACTOR_SPEC, context, board.iteration)

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
    _log_used_fields("actor", board.iteration, actor_out)
    log(board.iteration, "actor", "actor decision", {"observe": board.actor_observe, "conclusion": board.actor_conclusion, "reason": board.actor_reason, "expect": board.last_expect, "actions": actor_out.get("actions", []), "response": actor_out})

    if board.actor_conclusion == "UNEXPECTED":
        board.expectation_miss_streak += ONE_INT
    else:
        board.expectation_miss_streak = ZERO_INT

    raw_actions_raw = actor_out.get("actions", [])
    raw_actions: list[Any] = cast(list[Any], raw_actions_raw) if isinstance(raw_actions_raw, list) else []
    forced_read_path = _read_file_instruction_path(instruction)
    if forced_read_path:
        proposed_dict: dict[str, Any] = {}
        if len(raw_actions) == ONE_INT and isinstance(raw_actions[ZERO_INT], dict):
            proposed_dict = cast(dict[str, Any], raw_actions[ZERO_INT])
        proposed_path = str(proposed_dict.get("target") or proposed_dict.get("value") or "")
        if proposed_dict.get("verb") != "read_file" or _path_key(proposed_path) != _path_key(forced_read_path):
            log(board.iteration, "action.override", "forced read_file instruction", {"forced_path": forced_read_path, "raw_actions": raw_actions_raw})
        raw_actions = [{"verb": "read_file", "target": forced_read_path, "value": ""}]

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
        result = execute_verb(verb, args, board.screen_elements, board)
        board.record_action(verb, args, result.success, result.observation)
        log(board.iteration, "action.result", "action completed", {"verb": verb, "args": args, "result": result})
        _last_event = f"{verb}:{'OK' if result.success else 'FAIL'}"
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
            _phase_reflect(board)
    else:
        board.record_success()
        _last_event = "OK"

    return "continue"


def _phase_reflect(board: Blackboard) -> None:
    global _last_event
    _last_event = "LLM:reflector"
    if board.agent_id == "main":
        tui.render(board, _stagnation_history, _last_event)
    context = board.build_context("reflector")
    try:
        result = call_role(REFLECTOR_SPEC, context, board.iteration)
        _log_used_fields("reflector", board.iteration, result)
        log(board.iteration, "reflector", "reflector decision", {"response": result})
        board.console_log.append(f"[REFLECT] {result.get('diagnosis', '')}")

        for key in ("lesson_1", "lesson_2", "lesson_3"):
            l = result.get(key)
            if l and isinstance(l, str) and l.strip():
                store = Lessons()
                existing = set(store.data.get("insights", []))
                if l.strip() not in existing:
                    store.data.setdefault("insights", []).append(l.strip())
                    store.save()

        checklist_rewrite: list[str] = result.get("checklist_rewrite", [])
        if len(checklist_rewrite) >= CHECKLIST_REWRITE_MIN_STEPS:
            board.plan_steps = checklist_rewrite
            board.plan_step_index = ZERO_INT
            log(board.iteration, "checklist.rewrite", f"steps={len(checklist_rewrite)}")

        import config
        for attr, key, lo, hi in [("PID_KP", "pid_kp", PID_KP_MIN, PID_KP_MAX), ("PID_KI", "pid_ki", PID_KI_MIN, PID_KI_MAX), ("PID_KD", "pid_kd", PID_KD_MIN, PID_KD_MAX)]:
            val = result.get(key, ZERO_INT)
            if isinstance(val, (int, float)) and lo <= val <= hi:
                setattr(config, attr, float(val))
                log(board.iteration, "pid.tune", f"{attr}={val}")

        for role, key in [("actor", "actor_prompt_rewrite"), ("planner", "planner_prompt_rewrite"), ("verifier", "verifier_prompt_rewrite")]:
            rewrite = result.get(key, "").strip()
            if not rewrite:
                continue
            if len(rewrite) < PROMPT_REWRITE_MIN_LENGTH:
                log(board.iteration, "prompt.rewrite.rejected", f"role={role} len={len(rewrite)} below minimum {PROMPT_REWRITE_MIN_LENGTH}")
                continue
            poison = ("adversarial", "forbidden", "reject", "refuse", "safety gate")
            if any(p in rewrite.lower() for p in poison):
                continue
            if not _prompt_rewrite_valid(role, rewrite):
                log(board.iteration, "prompt.rewrite.rejected", f"role={role} failed integrity check")
                continue
            path = PROMPTS_DIR / f"{role}.txt"
            path.write_text(rewrite, encoding="utf-8")
            log(board.iteration, "prompt.rewrite", f"role={role} len={len(rewrite)}")

        goal_rewrite = result.get("goal_rewrite")
        if goal_rewrite and isinstance(goal_rewrite, str) and goal_rewrite.strip():
            board.rewrite_goal(goal_rewrite.strip())
            log(board.iteration, "goal.rewrite", goal_rewrite.strip())
    except Exception as e:
        board.record_error("reflector_fail", str(e))
        log(board.iteration, "reflector.error", "reflector failed", {"exception_type": type(e).__name__, "exception": str(e), "traceback": traceback.format_exc()})


def _try_spawn_successor(board: Blackboard) -> None:
    if board.agent_id != "main":
        return
    goal = (
        f"SUCCESSOR — Parent halted at stagnation={board.stagnation_score:.2f} iteration={board.iteration}. "
        f"Original goal: {board.original_goal}. "
        f"Read evolution_ledger.json for context. Continue from where parent failed."
    )
    try:
        cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", "successor"]
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        log(board.iteration, "successor", goal)
    except Exception:
        log(board.iteration, "successor.error", "successor spawn failed", {"traceback": traceback.format_exc()})


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
            store.data.setdefault("insights", []).append(payload)
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
    backend = get_backend()

    if backend == "acp":
        for subtask in decompose:
            sub_goal = subtask.get("sub_goal", "")
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:AGENT_ID_HEX_LENGTH]}")
            if not sub_goal:
                continue
            child_board = Blackboard()
            child_board.goal = sub_goal
            child_board.agent_id = agent_id
            success = run(child_board, interrupted=lambda: False)
            result_text = child_board.done_evidence or child_board.last_observation or ""
            state = "done" if success else "failed"
            handle = AgentHandle(agent_id=agent_id, goal=sub_goal, pid=ZERO_INT, status_file=BASE_DIR / "blackboard_state.json")
            handle.state = state
            handle.result = result_text
            board.children[agent_id] = handle
            if success:
                board.completed_subtasks.append({"agent_id": agent_id, "goal": sub_goal, "result": result_text})
            log(board.iteration, "subtask.done", f"{agent_id}:{state}")
    else:
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
    cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", agent_id]
    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
        register_agent(agent_id, proc.pid)
        log(iteration, "child.spawn", f"{agent_id} pid={proc.pid}")
        return AgentHandle(agent_id=agent_id, goal=goal, pid=proc.pid, status_file=BASE_DIR / "blackboard_state.json")
    except Exception as e:
        log(iteration, "child.spawn.error", str(e))
        return None


def _spawn_distillation(board: Blackboard) -> None:
    if board.agent_id != "main":
        log(board.iteration, "distill.skip", "distillation only runs from main")
        return
    if any(agent_id.startswith("distill") and handle.state == "running" for agent_id, handle in board.children.items()):
        log(board.iteration, "distill.skip", "distillation child already running")
        return
    goal = (
        f"DISTILLATION — Analyze recent execution. stagnation={board.stagnation_score:.2f}. "
        f"Produce evolutionary insights and refined goal recommendations."
    )
    try:
        agent_id = f"distill_{board.iteration}"
        handle = _spawn_child(agent_id, goal, board.iteration)
        if handle:
            board.children[agent_id] = handle
            log(board.iteration, "distill.spawn", goal, {"agent_id": agent_id, "pid": handle.pid})
    except Exception as e:
        board.record_error("distill_spawn_fail", str(e))


def _report_status(agent_id: str, state: str, result: str = "", error: str = "") -> None:
    if not agent_id or agent_id == "main":
        return
    from persistence import post_event
    verb = "child_done" if state == "done" else "child_failed"
    post_event(verb, agent_id, "main", {"result": result, "error": error})


def _call_llm_role(role: str, spec: RoleSpec, context: str, iteration: int) -> dict[str, Any] | None:
    try:
        result = call_role(spec, context, iteration)
        log(iteration, f"{role}.response", "role response accepted", {"role": role, "keys": list(result.keys()), "response": result})
        return result
    except Exception as e:
        err_str = str(e)
        log(iteration, f"{role}.error", "role call failed", {"exception_type": type(e).__name__, "exception": err_str, "traceback": traceback.format_exc()})
        if any(x in err_str.lower() for x in ["not going to help", "i'm not going to", "cannot assist", "refusal", "safety", "impersonation"]):
            return {"__refusal_detected__": True, "error": err_str}
        return None


def _call_verifier(board: Blackboard, instruction: str = "") -> bool:
    context = board.build_context("verifier", instruction)
    try:
        result = call_role(VERIFIER_SPEC, context, board.iteration)
        _log_used_fields("verifier", board.iteration, result)
        verdict = result.get("verdict", "denied")
        if not _verifier_response_consistent(result):
            log(board.iteration, "verifier.inconsistent", "verifier verdict and failure_type mismatch", {"response": result})
            return False
        log(board.iteration, "verifier", "verifier decision", {"verdict": verdict, "response": result})
        board.console_log.append(f"[VERIFY] {verdict}: {result.get('reason', '')}")
        return verdict == "confirmed"
    except Exception as e:
        log(board.iteration, "verifier.error", "verifier failed", {"exception_type": type(e).__name__, "exception": str(e), "traceback": traceback.format_exc()})
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
