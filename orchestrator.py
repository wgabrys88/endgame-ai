from __future__ import annotations

import json
import subprocess
import time
import uuid

from typing import Any, Callable

from config import (
    BASE_DIR, DELAY_BETWEEN_ITERATIONS,
    BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT,
    BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT,
    BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT,
    BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT,
    STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REFLECT_THRESHOLD, DISTILL_THRESHOLD, PROMPTS_DIR,
    PROMPT_REWRITE_MIN_LENGTH,
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
_FIELD_USAGE_PATH = BASE_DIR / "field_usage.json"
_last_distill_iteration: int = -10


def _log_used_fields(role: str, iteration: int, response: dict[str, Any]) -> None:
    used: list[str] = response.get("used_fields", [])
    if not used:
        return
    entry = {"role": role, "iteration": iteration, "used_fields": used}
    data: list[dict[str, Any]] = []
    if _FIELD_USAGE_PATH.exists():
        try:
            data = json.loads(_FIELD_USAGE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    data.append(entry)
    _FIELD_USAGE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run(board: Blackboard, *, interrupted: Callable[[], bool] = lambda: False) -> bool:
    global _last_event
    halt_counter = 0
    is_main = board.agent_id == "main"

    if is_main:
        from log import set_tui_hook
        set_tui_hook(tui.event)
        tui.enter()
    try:
        return _loop(board, interrupted, halt_counter, is_main)
    finally:
        if is_main:
            tui.exit()
            from log import set_tui_hook
            set_tui_hook(None)


def _loop(board: Blackboard, interrupted: Callable[[], bool], halt_counter: int, is_main: bool) -> bool:
    global _last_event, _last_distill_iteration

    while True:
        if interrupted():
            log(board.iteration, "run", "interrupted")
            _report_status(board.agent_id, "failed", error="interrupted")
            return False

        board.iteration += 1
        board.clear_signals()
        log(board.iteration, "iteration.start", f"stagnation={board.stagnation_score:.3f} pid={board.pid_output:.3f} energy={board.attractor_energy:.3f}")

        if board.stagnation_score >= STAGNATION_HALT_THRESHOLD:
            halt_counter += 1
            if halt_counter >= STAGNATION_HALT_SUSTAINED:
                log(board.iteration, "halt", f"stagnation={board.stagnation_score:.2f} sustained={halt_counter}")
                _last_event = "HALT"
                if is_main:
                    tui.render(board, _stagnation_history, _last_event)
                _try_spawn_successor(board)
                _report_status(board.agent_id, "failed", error="stagnation_halt")
                return False
        else:
            halt_counter = 0

        _process_inbox(board)
        _process_children(board)

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

        stuckness = (board.stagnation_score * board.stagnation_score) / (abs(board.pid_slope) + 0.01)
        if stuckness > DISTILL_THRESHOLD and (board.iteration - _last_distill_iteration) >= 10:
            _last_event = "PID→DISTILL"
            log(board.iteration, "pid.distill", f"stuckness={stuckness:.2f}")
            _spawn_distillation(board)
            _last_distill_iteration = board.iteration

        if is_main:
            tui.render(board, _stagnation_history, _last_event)
            for cmd in tui.poll_commands():
                if cmd.startswith("force_advance:") and board.plan_steps:
                    board.plan_step_index = min(board.plan_step_index + 1, len(board.plan_steps) - 1)
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
        board.screen_valid = False
        _last_event = "WAIT:lock"
        return "continue"
    else:
        try:
            obs = observe()
            board.record_screen(obs.context_text, obs.content_hash, obs.book)
            board.screen_valid = True
            board.focused_window = obs.focused_title
            board.update_screen_stagnation(obs.content_hash)
            log(board.iteration, "observe", f"hash={obs.content_hash} elements={len(obs.book)}")
        except Exception as e:
            board.release_screen()
            board.screen_valid = False
            board.record_error("observe_fail", str(e))
            return "continue"

    result = _phase_plan_act(board)
    if not is_distillation:
        board.release_screen()
    return result


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

    mode = plan.get("mode", "direct")
    next_action = plan.get("next_action", "")
    decompose = plan.get("decompose", [])

    board.last_plan_because = plan.get("because", "")
    board.last_instruction = next_action
    _log_used_fields("planner", board.iteration, plan)
    log(board.iteration, "planner", f"mode={mode} because={board.last_plan_because}")

    new_notes: list[str] = plan.get("notes", [])
    if new_notes:
        board.notes = [n for n in new_notes if n]

    sequence: list[str] = plan.get("sequence", [])
    if sequence and not board.plan_steps:
        board.plan_steps = sequence
        board.plan_step_index = 0
        log(board.iteration, "checklist.created", f"steps={len(sequence)}")

    if plan.get("step_advance") and board.plan_steps:
        board.plan_step_index = min(board.plan_step_index + 1, len(board.plan_steps) - 1)
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
    log(board.iteration, "actor", f"observe={board.actor_observe} conclusion={board.actor_conclusion}")

    if board.actor_conclusion == "UNEXPECTED":
        board.expectation_miss_streak += 1
    else:
        board.expectation_miss_streak = 0

    raw_actions: list[dict[str, Any]] = actor_out.get("actions", [])

    if not raw_actions and board.actor_conclusion == "UNEXPECTED":
        board.record_action("no_match", {}, False, "actor could not resolve element")
        board.record_failure()
        return "continue"

    iteration_had_failure = False

    for action_obj in raw_actions:
        if isinstance(action_obj, str):
            continue
        verb = action_obj.get("verb", "")
        target = action_obj.get("target", "")
        value = action_obj.get("value", "")

        args = _build_args(verb, target, value)
        if verb not in VERBS:
            board.record_action(verb, args, False, f"unknown verb: {verb}")
            iteration_had_failure = True
            break
        if board.stagnation_blocks_action(verb, target):
            board.record_action(verb, args, False, f"STAGNATION BLOCKED: {verb}:{target}")
            iteration_had_failure = True
            break

        result = execute_verb(verb, args, board.screen_elements, board)
        board.record_action(verb, args, result.success, result.observation)
        log(board.iteration, f"action.{verb}", f"success={result.success} obs={result.observation}")
        _last_event = f"{verb}:{'OK' if result.success else 'FAIL'}"

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
        result = call_role(REFLECTOR_SPEC, context)
        _log_used_fields("reflector", board.iteration, result)
        log(board.iteration, "reflector", f"diagnosis={result.get('diagnosis', '')}")
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
        if len(checklist_rewrite) >= 2:
            board.plan_steps = checklist_rewrite
            board.plan_step_index = 0
            log(board.iteration, "checklist.rewrite", f"steps={len(checklist_rewrite)}")

        import config
        for attr, key, lo, hi in [("PID_KP", "pid_kp", 0.1, 3.0), ("PID_KI", "pid_ki", 0.05, 1.0), ("PID_KD", "pid_kd", 0.5, 5.0)]:
            val = result.get(key, 0)
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
            if role == "actor" and "verb" not in rewrite.lower():
                continue
            if role == "planner" and "json" not in rewrite.lower():
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
        pass


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
            raise SystemExit(0)


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
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:6]}")
            if not sub_goal:
                continue
            child_board = Blackboard()
            child_board.goal = sub_goal
            child_board.agent_id = agent_id
            success = run(child_board, interrupted=lambda: False)
            result_text = child_board.done_evidence or child_board.last_observation or ""
            state = "done" if success else "failed"
            handle = AgentHandle(agent_id=agent_id, goal=sub_goal, pid=0, status_file=BASE_DIR / "blackboard_state.json")
            handle.state = state
            handle.result = result_text
            board.children[agent_id] = handle
            if success:
                board.completed_subtasks.append({"agent_id": agent_id, "goal": sub_goal, "result": result_text})
            log(board.iteration, "subtask.done", f"{agent_id}:{state}")
    else:
        for subtask in decompose:
            sub_goal = subtask.get("sub_goal", "")
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:6]}")
            if not sub_goal:
                continue
            handle = _spawn_child(agent_id, sub_goal, board.iteration)
            if handle:
                board.children[agent_id] = handle

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
    goal = (
        f"DISTILLATION — Analyze recent execution. stagnation={board.stagnation_score:.2f}. "
        f"Produce evolutionary insights and refined goal recommendations."
    )
    try:
        cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", "distill"]
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        log(board.iteration, "distill.spawn", goal)
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
        result = call_role(spec, context)
        log(iteration, f"{role}.response", f"keys={list(result.keys())}")
        return result
    except Exception as e:
        err_str = str(e)
        log(iteration, f"{role}.error", err_str)
        if any(x in err_str.lower() for x in ["not going to help", "i'm not going to", "cannot assist", "refusal", "safety", "impersonation"]):
            return {"__refusal_detected__": True, "error": err_str}
        return None


def _call_verifier(board: Blackboard, instruction: str = "") -> bool:
    context = board.build_context("verifier", instruction)
    try:
        result = call_role(VERIFIER_SPEC, context)
        _log_used_fields("verifier", board.iteration, result)
        verdict = result.get("verdict", "denied")
        log(board.iteration, "verifier", f"verdict={verdict} reason={result.get('reason', '')}")
        board.console_log.append(f"[VERIFY] {verdict}: {result.get('reason', '')}")
        return verdict == "confirmed"
    except Exception:
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
            return {"selector": target, "amount": int(value) if value else 3}
        except ValueError:
            return {"selector": target, "amount": 3}
    if verb == "wait":
        try:
            return {"seconds": float(target or value or "1")}
        except ValueError:
            return {"seconds": 1.0}
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
