from __future__ import annotations

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
    CHAOS_HALT_THRESHOLD, CHAOS_HALT_SUSTAINED_ITERATIONS,
    REFLECT_EVERY_N_ITERATIONS,
    DISTILL_EVERY_N_ITERATIONS, CONSOLE_VERBOSITY, PROMPTS_DIR, trace,
)
from state import Blackboard, AgentHandle
from journal import ExecutionJournal, NullJournal
from lessons import Lessons
from dispatch import call_role, RoleSpec
from observer import observe
from actions import execute_verb, VERBS
from llm import get_backend
from persistence import save_snapshot


PLANNER_SPEC = RoleSpec("planner", BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT)
ACTOR_SPEC = RoleSpec("actor", BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT)
VERIFIER_SPEC = RoleSpec("verifier", BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT)
REFLECTOR_SPEC = RoleSpec("reflector", BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT)


def run(board: Blackboard, journal: ExecutionJournal | NullJournal, *,
        interrupted: Callable[[], bool] = lambda: False) -> bool:

    chaos_halt_counter = 0
    reflect_only_counter = 0

    while True:
        if interrupted():
            _log(board, journal, "run.interrupted", {"iteration": board.iteration})
            _report_status(board.agent_id, "failed", error="interrupted")
            return False

        board.iteration += 1
        board.clear_signals()
        _log(board, journal, "iteration.start", {"iteration": board.iteration})
        _print(board, f"\n{'='*40}\n[ITERATION {board.iteration}]\n{'='*40}")
        trace("orchestrator.iteration", f"it={board.iteration} chaos={board.chaos_level:.3f} rep={board.repetition_score:.3f} failures={board.consecutive_failures}")

        if _check_chaos_halt(board, journal, chaos_halt_counter):
            chaos_halt_counter += 1
            if chaos_halt_counter >= CHAOS_HALT_SUSTAINED_ITERATIONS:
                _log(board, journal, "run.chaos_halt", {"chaos": board.chaos_level, "sustained": chaos_halt_counter})
                _print(board, f"  [HALT] Chaos sustained at {board.chaos_level:.2f} for {chaos_halt_counter} iterations.")
                _try_spawn_successor(board, journal)
                _report_status(board.agent_id, "failed", error="chaos_halt")
                return False
        else:
            chaos_halt_counter = 0

        _process_inbox(board, journal)
        _process_children(board, journal)

        decision = _schedule(board)
        _print(board, f"  [SCHEDULE] {decision} (chaos={board.chaos_level:.2f} rep={board.repetition_score:.2f} fails={board.consecutive_failures})")

        if decision == "observe_plan_act":
            reflect_only_counter = 0
            result = _phase_observe(board, journal)
            if result == "done":
                return True
            if result == "halt":
                return False
        elif decision == "plan_blind":
            reflect_only_counter = 0
            result = _phase_plan_act(board, journal, blind=True)
            if result == "done":
                return True
        elif decision == "reflect_only":
            reflect_only_counter += 1
            _phase_reflect(board, journal)
            board.consecutive_failures = 0
            board.chaos_level = max(0.0, board.chaos_level - 0.15)
            if reflect_only_counter >= 3:
                _print(board, "  [ESCAPE] Forcing observe_plan_act after 3 reflect cycles.")
                reflect_only_counter = 0
                board.chaos_level = 0.2
                result = _phase_observe(board, journal)
                if result == "done":
                    return True
        elif decision == "emergency":
            reflect_only_counter = 0
            _phase_emergency(board, journal)

        if board.iteration % REFLECT_EVERY_N_ITERATIONS == 0:
            _phase_reflect(board, journal)
        if board.iteration % DISTILL_EVERY_N_ITERATIONS == 0:
            _spawn_distillation(board, journal)

        _log(board, journal, "iteration.end", {"iteration": board.iteration})
        save_snapshot(board.get_persistable_snapshot())
        time.sleep(DELAY_BETWEEN_ITERATIONS)


def _schedule(board: Blackboard) -> str:
    if board.chaos_level >= 0.7:
        return "emergency"
    if board.chaos_level >= 0.5:
        return "reflect_only"
    if not board.screen_valid and board.chaos_level >= 0.25:
        return "plan_blind"
    return "observe_plan_act"


def _phase_observe(board: Blackboard, journal: ExecutionJournal | NullJournal) -> str:
    is_distillation = "DISTILLATION" in board.goal.upper() or "analyze recent execution" in board.goal.lower()

    if is_distillation:
        board.record_screen("(distillation mode)", "distill", {})
        board.screen_valid = True
    elif not board.acquire_screen():
        board.screen_valid = False
        board.record_error("screen_lock", "Another agent holds the screen lock.")
        _print(board, "  [WAIT] Screen locked. Planner runs blind.")
        return _phase_plan_act(board, journal, blind=True)
    else:
        try:
            obs = observe()
            board.record_screen(obs.context_text, obs.content_hash, obs.book)
            board.screen_valid = True
            _log(board, journal, "screen.observed", {"hash": obs.content_hash, "elements": len(obs.book)})
        except Exception as e:
            board.release_screen()
            board.screen_valid = False
            board.record_error("observe_fail", str(e))
            _print(board, f"  [ERROR] observe failed: {e}")
            return _phase_plan_act(board, journal, blind=True)

    result = _phase_plan_act(board, journal, blind=False)
    if not is_distillation:
        board.release_screen()
    return result


def _phase_plan_act(board: Blackboard, journal: ExecutionJournal | NullJournal, *, blind: bool) -> str:
    context = board.planner_context()
    if board.chaos_level > 0.45:
        context += f"\n\n[CHAOS — Level {board.chaos_level:.2f} | Repetition {board.repetition_score:.2f}] Break the current pattern. Prefer parallel mode or spawn_agent."
    if blind:
        context += "\n\n[BLIND MODE] Screen observation failed or unavailable. Use only: cmd, read_file, write_file, spawn_agent, wait, press, hotkey, done. Do NOT use click or scroll."

    _print(board, f"  [LLM] Calling planner... (chaos={board.chaos_level:.2f})")
    plan = _call_llm_role("planner", PLANNER_SPEC, context, journal, board.iteration)

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

    _print(board, f"  [PLAN] mode={mode} chaos={board.chaos_level:.2f} [{board.lorenz_x:.1f},{board.lorenz_y:.1f},{board.lorenz_z:.1f}]")
    if plan.get("because"):
        _print(board, f"  [PLAN] Reason: {plan['because']}")

    if mode == "done" and board.chaos_rejects_done():
        mode = "parallel" if board.chaos_forces_parallel() else "direct"
        if mode == "direct" and not next_action:
            next_action = "Observe current state and take concrete step toward goal."

    if mode != "done" and board.detect_repetition_in_history():
        goal_lower = board.goal.lower()
        if any(phrase in goal_lower for phrase in ("emit done", "and done", "then done")):
            mode = "done"

    if board.chaos_forces_parallel() and mode == "direct":
        mode = "parallel"
        if not decompose:
            decompose = [{"sub_goal": f"Recovery: {next_action or board.goal}", "agent_id": f"chaos_{board.iteration}"}]

    if mode == "done" and board.verifier_denied_last:
        mode = "direct"
        next_action = "The verifier denied your last completion claim. Address feedback before claiming done again."
        board.verifier_denied_last = False
        _print(board, "  [GATE] Verifier denial blocks done claim.")

    if mode == "done" or next_action.strip().lower() == "done":
        is_distillation = "DISTILLATION" in board.goal.upper()
        if is_distillation:
            _log(board, journal, "goal.complete", {"iteration": board.iteration})
            _report_status(board.agent_id, "done", result=next_action)
            return "done"
        board.done_claimed = True
        board.done_evidence = plan.get("because", next_action)
        verified = _call_verifier(board, journal, "planner claimed mode=done")
        if verified:
            _log(board, journal, "goal.complete", {"iteration": board.iteration})
            _report_status(board.agent_id, "done", result=board.done_evidence)
            return "done"
        board.verifier_denied_last = True
        board.record_failure()
        _print(board, "  [VERIFY] Denied planner done claim. Continuing.")
        return "continue"

    if mode == "parallel" and decompose:
        board.mode = "coordinate"
        _execute_decomposition(board, journal, decompose)
        board.record_success()
        return "continue"

    return _phase_act(board, journal, next_action, blind=blind)


def _phase_act(board: Blackboard, journal: ExecutionJournal | NullJournal, instruction: str, *, blind: bool) -> str:
    _print(board, f"  [LLM] Calling actor... (instruction: {instruction[:80]})")
    actor_out = _call_llm_role("actor", ACTOR_SPEC, board.actor_context(instruction), journal, board.iteration)

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
    board.last_expect = actor_out.get("expect", "")

    conclusion = actor_out.get("conclusion", "EXPECTED")
    if conclusion == "UNEXPECTED":
        board.expectation_miss_streak += 1
    else:
        board.expectation_miss_streak = 0

    raw_actions: list[dict[str, Any]] = actor_out.get("actions", [])
    if not isinstance(raw_actions, list):
        raw_actions = []

    if not raw_actions and conclusion == "UNEXPECTED":
        board.record_action("no_match", {}, False, "actor could not resolve element")
        board.record_failure()
        return "continue"

    blind_verbs = {"cmd", "read_file", "write_file", "spawn_agent", "wait", "press", "hotkey", "done"}
    iteration_had_failure = False

    for action_obj in raw_actions:
        if isinstance(action_obj, str):
            continue
        verb = action_obj.get("verb", "")
        target = action_obj.get("target", "")
        value = action_obj.get("value", "")

        if blind and verb not in blind_verbs:
            board.record_action(verb, {}, False, f"BLIND MODE: {verb} requires screen observation")
            iteration_had_failure = True
            break

        args = _build_args(verb, target, value)
        if verb not in VERBS:
            board.record_action(verb, args, False, f"unknown verb: {verb}")
            iteration_had_failure = True
            break
        if board.chaos_blocks_action(verb, target):
            board.record_action(verb, args, False, f"CHAOS BLOCKED: {verb}:{target}")
            iteration_had_failure = True
            break

        result = execute_verb(verb, args, board.screen_elements, board)
        board.record_action(verb, args, result.success, result.observation)
        _log(board, journal, f"action.{verb}", {"verb": verb, "args": args, "success": result.success, "observation": result.observation})
        _print(board, f"  [{verb}] {result.observation}")

        if not result.success:
            iteration_had_failure = True
            break
        if verb == "done":
            board.done_claimed = True
            board.done_evidence = result.observation
            break

    if board.done_claimed or board.problem:
        verified = _call_verifier(board, journal, instruction)
        if verified and board.done_claimed:
            _log(board, journal, "goal.complete", {"iteration": board.iteration})
            _report_status(board.agent_id, "done", result=board.done_evidence)
            return "done"
        if not verified:
            board.verifier_denied_last = True
            iteration_had_failure = True

    if iteration_had_failure:
        board.record_failure()
        _print(board, f"  [FAIL] consecutive={board.consecutive_failures} chaos={board.chaos_level:.2f}")
    else:
        board.record_success()
        _print(board, f"  [OK] chaos={board.chaos_level:.2f}")

    return "continue"


def _phase_reflect(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    context = board.build_reflector_context()
    trace("orchestrator.reflector", f"it={board.iteration} chaos={board.chaos_level:.3f}")
    try:
        result = call_role(REFLECTOR_SPEC, context)
        _log(board, journal, "reflector.output", result)
        _print(board, f"  [REFLECT] {result.get('diagnosis', '')}")

        lessons_list: list[str] = []
        for key in ("lesson_1", "lesson_2", "lesson_3"):
            l = result.get(key)
            if l and isinstance(l, str) and l.strip():
                lessons_list.append(l.strip())
        if lessons_list:
            store = Lessons()
            existing = set(store.data.get("insights", []))
            for lesson in lessons_list:
                if lesson not in existing:
                    store.data.setdefault("insights", []).append(lesson)
                    existing.add(lesson)
            store.save()

        for role, key in [("actor", "actor_prompt_rewrite"), ("planner", "planner_prompt_rewrite"), ("verifier", "verifier_prompt_rewrite")]:
            rewrite = result.get(key, "").strip()
            if not rewrite:
                continue
            poison = ("adversarial", "forbidden", "reject", "refuse", "safety gate", "critical json output", "you must output only")
            if any(p in rewrite.lower() for p in poison):
                continue
            if role == "actor" and "verb" not in rewrite.lower():
                continue
            if role == "planner" and "json" not in rewrite.lower():
                continue
            path = PROMPTS_DIR / f"{role}.txt"
            path.write_text(rewrite, encoding="utf-8")
            _log(board, journal, "reflector.applied", {"role": role, "len": len(rewrite)})

        goal_rewrite = result.get("goal_rewrite")
        if goal_rewrite and isinstance(goal_rewrite, str) and goal_rewrite.strip():
            board.rewrite_goal(goal_rewrite.strip())
    except Exception as e:
        board.record_error("reflector_fail", str(e))
        _print(board, f"  [ERROR] reflector failed: {e}")


def _phase_emergency(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    _print(board, f"  [EMERGENCY] chaos={board.chaos_level:.2f} — attempting recovery")
    _phase_reflect(board, journal)
    board.consecutive_failures = 0
    board.expectation_miss_streak = 0
    board.chaos_level = max(0.0, board.chaos_level - 0.25)
    _spawn_distillation(board, journal)


def _try_spawn_successor(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    if board.agent_id != "main":
        return
    goal = (
        f"SUCCESSOR — Parent halted at chaos={board.chaos_level:.2f} iteration={board.iteration}. "
        f"Original goal: {board.original_goal}. "
        f"Read evolution_ledger.json for context. Continue from where parent failed."
    )
    try:
        cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", "successor"]
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        _log(board, journal, "successor.spawned", {"goal": goal})
        _print(board, f"  [SUCCESSOR] Spawned successor agent before death.")
    except Exception as e:
        _print(board, f"  [ERROR] Could not spawn successor: {e}")


def _check_chaos_halt(board: Blackboard, journal: ExecutionJournal | NullJournal, counter: int) -> bool:
    return board.chaos_level >= CHAOS_HALT_THRESHOLD


def _process_inbox(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
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
                board.chaos_level = float(payload)
            except ValueError:
                pass
        elif cmd_type == "kill":
            raise SystemExit(0)


def _process_children(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    for ev in board.poll_children():
        _log(board, journal, "child.event", ev)
        _print(board, f"  [CHILD] {ev['agent_id']}: {ev['state']} - {ev.get('result', '')}")

    if board.all_children_done() and not board.pending_subtasks and board.mode == "coordinate":
        if not board.any_children_failed():
            board.mode = "direct"
            board.last_verb = ""


def _execute_decomposition(board: Blackboard, journal: ExecutionJournal | NullJournal, decompose: list[dict[str, Any]]) -> None:
    backend = get_backend()

    if backend == "acp":
        for subtask in decompose:
            sub_goal = subtask.get("sub_goal", "")
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:6]}")
            if not sub_goal:
                continue
            _print(board, f"  [SUBTASK] {agent_id}: {sub_goal}")
            child_board = Blackboard()
            child_board.goal = sub_goal
            child_board.agent_id = agent_id
            from journal import create_execution_journal
            child_journal = create_execution_journal(BASE_DIR, sub_goal)
            success = run(child_board, child_journal, interrupted=lambda: False)
            child_journal.close()
            result_text = child_board.done_evidence or child_board.last_observation or ""
            state = "done" if success else "failed"
            handle = AgentHandle(agent_id=agent_id, goal=sub_goal, pid=0, status_file=BASE_DIR / "blackboard_state.json")
            handle.state = state
            handle.result = result_text
            board.children[agent_id] = handle
            if success:
                board.completed_subtasks.append({"agent_id": agent_id, "goal": sub_goal, "result": result_text})
            _print(board, f"  [SUBTASK DONE] {agent_id}: {state} - {result_text}")
    else:
        for subtask in decompose:
            sub_goal = subtask.get("sub_goal", "")
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:6]}")
            if not sub_goal:
                continue
            handle = _spawn_child(agent_id, sub_goal, journal, board.iteration)
            if handle:
                board.children[agent_id] = handle
                _print(board, f"  [SPAWN] {agent_id} pid={handle.pid}: {sub_goal}")

    _log(board, journal, "decompose", {"subtasks": len(decompose), "agents": list(board.children.keys())})


def _spawn_child(agent_id: str, goal: str, journal: ExecutionJournal | NullJournal, iteration: int) -> AgentHandle | None:
    from persistence import register_agent
    cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", agent_id]
    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        register_agent(agent_id, proc.pid)
        _log_raw(journal, "child.spawned", {"agent_id": agent_id, "goal": goal, "pid": proc.pid}, iteration)
        return AgentHandle(agent_id=agent_id, goal=goal, pid=proc.pid, status_file=BASE_DIR / "blackboard_state.json")
    except Exception as e:
        _log_raw(journal, "error.spawn", {"agent_id": agent_id, "error": str(e)}, iteration)
        return None


def _spawn_distillation(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    goal = (
        f"DISTILLATION — Analyze recent execution. chaos={board.chaos_level:.2f}. "
        f"Produce evolutionary insights and refined goal recommendations."
    )
    try:
        cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend(), "--agent-id", "distill"]
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        _log(board, journal, "distillation.spawned", {"goal": goal})
    except Exception as e:
        board.record_error("distill_spawn_fail", str(e))


def _report_status(agent_id: str, state: str, result: str = "", error: str = "") -> None:
    if not agent_id or agent_id == "main":
        return
    from persistence import post_event
    verb = "child_done" if state == "done" else "child_failed"
    post_event(verb, agent_id, "main", {"result": result, "error": error})


def _call_llm_role(role: str, spec: RoleSpec, context: str, journal: ExecutionJournal | NullJournal, iteration: int) -> dict[str, Any] | None:
    try:
        result = call_role(spec, context)
        if not isinstance(result, dict):
            return None
        _log_raw(journal, f"{role}.output", result, iteration)
        return result
    except Exception as e:
        err_str = str(e)
        _log_raw(journal, f"error.{role}", {"error": err_str}, iteration)
        if any(x in err_str.lower() for x in ["not going to help", "i'm not going to", "cannot assist", "refusal", "safety", "impersonation"]):
            return {"__refusal_detected__": True, "error": err_str}
        return None


def _call_verifier(board: Blackboard, journal: ExecutionJournal | NullJournal, instruction: str = "") -> bool:
    context = board.verifier_context(instruction)
    try:
        result = call_role(VERIFIER_SPEC, context)
        verdict = result.get("verdict", "denied")
        _log(board, journal, "verifier.output", result)
        _print(board, f"  [VERIFY] {verdict}: {result.get('reason', '')}")
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
    if verb == "done":
        return {"evidence": value or target}
    return {}


def _print(board: Blackboard, msg: str) -> None:
    if CONSOLE_VERBOSITY != "quiet":
        print(msg)
    board.console_log.append(msg)


def _log(board: Blackboard, journal: ExecutionJournal | NullJournal, event: str, payload: dict[str, Any]) -> None:
    journal.append(event, payload, it=board.iteration, aid="system")


def _log_raw(journal: ExecutionJournal | NullJournal, event: str, payload: dict[str, Any], iteration: int) -> None:
    journal.append(event, payload, it=iteration, aid="system")
