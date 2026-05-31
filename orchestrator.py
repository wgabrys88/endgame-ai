from __future__ import annotations
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from config import (
    BASE_DIR, DELAY_BETWEEN_ITERATIONS,
    BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT,
    BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT,
    BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT,
    BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT,
    CHAOS_HALT_THRESHOLD, CHAOS_HALT_SUSTAINED_ITERATIONS,
    CONSOLE_VERBOSITY, PROMPTS_DIR, trace,
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

    prev_screen_hash = ""
    reflector_called_this_iteration = False
    spawns_this_iteration = 0
    chaos_halt_counter = 0

    def on_goal_rewritten(payload: dict[str, Any]) -> None:
        journal.append("blackboard.goal_rewritten", payload, it=board.iteration, aid="blackboard")
    board.events.subscribe("goal.rewritten", on_goal_rewritten)

    def on_chaos_change(payload: dict[str, Any]) -> None:
        if payload.get("new", 0) > 0.5:
            journal.append("blackboard.high_chaos", payload, it=board.iteration, aid="blackboard")
    board.events.subscribe("chaos.changed", on_chaos_change)

    def on_needs_reflection(payload: dict[str, Any]) -> None:
        nonlocal reflector_called_this_iteration
        if not reflector_called_this_iteration:
            reflector_called_this_iteration = True
            journal.append("blackboard.reflection_triggered", payload, it=board.iteration, aid="blackboard")
            _call_reflector(board, journal)
    board.events.subscribe("self_regulation.needs_reflection", on_needs_reflection)

    def on_needs_goal_softening(payload: dict[str, Any]) -> None:
        soft_goal = (
            f"SOFTENED RECOVERY: Re-strategize with lower risk first steps. "
            f"Original intent: {board.original_goal}"
        )
        board.rewrite_goal(soft_goal)
        journal.append("blackboard.goal_softened", {"new_goal": soft_goal}, it=board.iteration, aid="blackboard")
    board.events.subscribe("self_regulation.needs_goal_softening", on_needs_goal_softening)

    def on_emergency_reflection(payload: dict[str, Any]) -> None:
        nonlocal reflector_called_this_iteration, spawns_this_iteration
        journal.append("blackboard.emergency_reflection", payload, it=board.iteration, aid="blackboard")
        if not reflector_called_this_iteration:
            reflector_called_this_iteration = True
            _call_reflector(board, journal)
        board.consecutive_failures = 0
        if spawns_this_iteration < 1:
            spawns_this_iteration += 1
            _spawn_distillation(board, journal)
    board.events.subscribe("self_regulation.needs_emergency_reflection", on_emergency_reflection)

    def on_periodic_reflection(payload: dict[str, Any]) -> None:
        nonlocal reflector_called_this_iteration
        if not reflector_called_this_iteration:
            reflector_called_this_iteration = True
            trace("orchestrator.periodic_reflect", f"iteration={board.iteration}")
            _call_reflector(board, journal)
    board.events.subscribe("evolution.periodic_reflection_due", on_periodic_reflection)

    def on_distillation_due(payload: dict[str, Any]) -> None:
        nonlocal spawns_this_iteration
        if spawns_this_iteration < 1:
            spawns_this_iteration += 1
            _spawn_distillation(board, journal)
    board.events.subscribe("evolution.distillation_due", on_distillation_due)

    def on_refusal_detected(payload: dict[str, Any]) -> None:
        journal.append("refusal.detected", payload, it=board.iteration, aid="blackboard")
        board.chaos_level = min(1.0, board.chaos_level + 0.2)
        if board.consecutive_failures >= 3:
            board.events.publish("self_regulation.needs_emergency_reflection", {
                "reason": "repeated_refusals", "iteration": board.iteration
            })
    board.events.subscribe("refusal.detected", on_refusal_detected)

    def on_action_recorded(payload: dict[str, Any]) -> None:
        board._broadcast_action(payload["verb"], payload["success"], payload.get("obs", ""))
    board.events.subscribe("action.recorded", on_action_recorded)

    while True:
        if interrupted():
            journal.append("run.interrupted", {"iteration": board.iteration}, it=board.iteration)
            _report_status(board.agent_id, "failed", error="interrupted")
            return False

        board.iteration += 1
        reflector_called_this_iteration = False
        spawns_this_iteration = 0
        board.clear_signals()
        board.advance_iteration()

        journal.append("iteration.start", {"iteration": board.iteration}, it=board.iteration, ph="system")
        trace("orchestrator.iteration", f"it={board.iteration} chaos={board.chaos_level:.3f} rep={board.repetition_score:.3f} failures={board.consecutive_failures} mode={board.mode}")
        print(f"\n{'='*40}\n[ITERATION {board.iteration}]\n{'='*40}")

        if board.chaos_level >= CHAOS_HALT_THRESHOLD:
            chaos_halt_counter += 1
            if chaos_halt_counter >= CHAOS_HALT_SUSTAINED_ITERATIONS:
                journal.append("run.chaos_halt", {"chaos": board.chaos_level, "sustained": chaos_halt_counter}, it=board.iteration)
                print(f"  [HALT] Chaos sustained at {board.chaos_level:.2f} for {chaos_halt_counter} iterations. System halting.")
                _report_status(board.agent_id, "failed", error="chaos_halt")
                return False
        else:
            chaos_halt_counter = 0

        inbox_commands = board.poll_inbox()
        for cmd in inbox_commands:
            _process_inbox_command(board, journal, cmd)

        child_events = board.poll_children()
        for ev in child_events:
            journal.append("child.event", ev, it=board.iteration, ph="coordinate")
            print(f"  [CHILD] {ev['agent_id']}: {ev['state']} - {ev.get('result','')}")

        if board.all_children_done() and not board.pending_subtasks and board.mode == "coordinate":
            if not board.any_children_failed():
                board.mode = "direct"
                board.last_verb = ""

        is_distillation = "DISTILLATION" in board.goal.upper() or "analyze recent execution" in board.goal.lower()

        if is_distillation:
            board.record_screen("(distillation mode — no screen observation)", "distill", {})
        elif not board.acquire_screen():
            print(f"  [WAIT] Screen locked by another agent. Skipping this iteration.")
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            journal.append("iteration.end", {"iteration": board.iteration, "screen_locked": True}, it=board.iteration, ph="system")
            continue
        else:
            try:
                obs = observe()
                board.record_screen(obs.context_text, obs.content_hash, obs.book)
                journal.append("screen.observed", {"hash": obs.content_hash, "elements": len(obs.book)},
                               it=board.iteration, aid="observer", ph="observe")
            except Exception as e:
                board.release_screen()
                journal.append("error.observe", {"error": str(e)}, it=board.iteration, lvl="ERROR")
                print(f"  [ERROR] observe failed: {e}")
                time.sleep(DELAY_BETWEEN_ITERATIONS)
                continue

        if not is_distillation:
            if board.screen_hash == prev_screen_hash and board.last_verb == "wait" and not child_events:
                board.release_screen()
                journal.append("screen.unchanged", {"hash": board.screen_hash}, it=board.iteration, ph="system")
                time.sleep(DELAY_BETWEEN_ITERATIONS)
                prev_screen_hash = board.screen_hash
                journal.append("iteration.end", {"iteration": board.iteration, "skipped": True}, it=board.iteration, ph="system")
                continue
            prev_screen_hash = board.screen_hash

        context = board.planner_context()
        if board.chaos_level > 0.45:
            context += (
                f"\n\n[CHAOS — Level {board.chaos_level:.2f} | Repetition {board.repetition_score:.2f}] "
                f"Break the current pattern. Prefer parallel mode or spawn_agent."
            )

        if CONSOLE_VERBOSITY != "quiet":
            print(f"  [LLM] Calling planner... (chaos={board.chaos_level:.2f} rep={board.repetition_score:.2f} fails={board.consecutive_failures})")

        t_plan_start = time.time()
        plan = _call_llm_role("planner", PLANNER_SPEC, context, journal, board.iteration)
        t_plan_elapsed = time.time() - t_plan_start

        if CONSOLE_VERBOSITY != "quiet" and isinstance(plan, dict):
            print(f"  [LLM] Planner responded in {t_plan_elapsed:.1f}s (mode={plan.get('mode', '?')})")
            if plan.get("because"):
                print(f"  [PLAN] Reason: {plan['because']}")

        if isinstance(plan, dict) and plan.get("__refusal_detected__"):
            board.events.publish("refusal.detected", {
                "role": "planner", "iteration": board.iteration, "error_preview": plan.get("error", ""),
            })
            board.record_action("parse_fail", {}, False, "planner refusal detected")
            board.record_failure()
            if not is_distillation:
                board.release_screen()
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            continue

        if not plan:
            board.record_action("parse_fail", {}, False, "planner returned no valid JSON")
            board.record_failure()
            if not is_distillation:
                board.release_screen()
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            continue

        mode = plan.get("mode", "direct")
        next_action = plan.get("next_action", "")
        decompose = plan.get("decompose", [])

        if mode == "done" and board.chaos_rejects_done():
            mode = "parallel" if board.chaos_forces_parallel() else "direct"
            trace("orchestrator.chaos_reject_done", f"it={board.iteration} chaos={board.chaos_level:.3f} forced_mode={mode}")
            if mode == "direct" and not next_action:
                next_action = "Observe the current screen state and take the first concrete step toward the goal."

        if mode != "done" and board._detect_repetition_in_history():
            goal_lower = board.goal.lower()
            if any(phrase in goal_lower for phrase in ("emit done", "and done", "then done")):
                mode = "done"
                next_action = ""
                decompose = []
                trace("orchestrator.forced_done", f"it={board.iteration} reason=goal_contains_done_and_action_repeated")

        if board.chaos_forces_parallel() and mode == "direct":
            mode = "parallel"
            if not decompose:
                decompose = [{"sub_goal": f"Sub-task from forced decomposition: {next_action or board.goal}", "agent_id": f"chaos_{board.iteration}"}]
            trace("orchestrator.chaos_force_parallel", f"it={board.iteration} chaos={board.chaos_level:.3f}")

        print(f"  [PLAN] mode={mode} chaos={board.chaos_level:.2f} [{board.lorenz_x:.1f},{board.lorenz_y:.1f},{board.lorenz_z:.1f}]")

        if mode == "done" or next_action.strip().lower() == "done":
            if not is_distillation:
                board.release_screen()
            journal.append("goal.complete", {"iteration": board.iteration}, it=board.iteration)
            _report_status(board.agent_id, "done", result=next_action)
            return True

        if mode == "parallel" and decompose:
            board.mode = "coordinate"
            if not is_distillation:
                board.release_screen()
            _execute_decomposition(board, journal, decompose)
            journal.append("iteration.end", {"iteration": board.iteration}, it=board.iteration, ph="system")
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            continue

        if CONSOLE_VERBOSITY != "quiet":
            print(f"  [LLM] Calling actor... (instruction: {next_action if next_action else 'N/A'})")

        actor_out = _call_llm_role("actor", ACTOR_SPEC, board.actor_context(next_action), journal, board.iteration)

        if isinstance(actor_out, dict) and actor_out.get("__refusal_detected__"):
            board.events.publish("refusal.detected", {
                "role": "actor", "iteration": board.iteration, "error_preview": actor_out.get("error", ""),
            })
            board.record_action("parse_fail", {}, False, "actor refusal detected")
            board.record_failure()
            if not is_distillation:
                board.release_screen()
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            continue

        if not actor_out:
            board.record_action("parse_fail", {}, False, "actor returned no valid JSON")
            board.record_failure()
            if not is_distillation:
                board.release_screen()
            time.sleep(DELAY_BETWEEN_ITERATIONS)
            continue

        board.actor_observe = actor_out.get("observe", "")
        board.actor_reason = actor_out.get("reason", "")
        board.last_expect = actor_out.get("expect", "")

        conclusion = actor_out.get("conclusion", "EXPECTED")
        if conclusion == "UNEXPECTED":
            board.expectation_miss_streak += 1
        else:
            board.expectation_miss_streak = 0

        iteration_had_failure = False
        raw_actions = actor_out.get("actions", [])
        if not isinstance(raw_actions, list):
            raw_actions = []

        if not raw_actions and conclusion == "UNEXPECTED":
            board.record_action("no_match", {}, False, "actor could not resolve element from instruction")
            iteration_had_failure = True

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
            if board.chaos_blocks_action(verb, target):
                board.record_action(verb, args, False, f"CHAOS BLOCKED: {verb}:{target}")
                trace("orchestrator.chaos_block", f"blocked {verb}:{target} chaos={board.chaos_level:.3f}")
                iteration_had_failure = True
                break

            result = execute_verb(verb, args, board.screen_elements, board)
            board.record_action(verb, args, result.success, result.observation)

            journal.append(f"action.{verb}", {
                "verb": verb, "args": args,
                "success": result.success, "observation": result.observation,
            }, it=board.iteration, aid="actor", ph="act")
            print(f"  [{verb}] {result.observation}")

            if not result.success:
                iteration_had_failure = True
                break

            if verb == "done":
                board.done_claimed = True
                board.done_evidence = result.observation
                break

        if not is_distillation:
            board.release_screen()

        if board.done_claimed or board.problem:
            verified = _call_verifier(board, journal, next_action)
            if verified and board.done_claimed:
                journal.append("goal.complete", {"iteration": board.iteration}, it=board.iteration)
                _report_status(board.agent_id, "done", result=board.done_evidence)
                return True
            if not verified:
                iteration_had_failure = True

        if iteration_had_failure:
            board.record_failure()
            if CONSOLE_VERBOSITY != "quiet":
                print(f"  [FAIL] consecutive={board.consecutive_failures} chaos={board.chaos_level:.2f}")
        else:
            board.record_success()
            if CONSOLE_VERBOSITY != "quiet":
                print(f"  [OK] chaos={board.chaos_level:.2f}")

        journal.append("iteration.end", {"iteration": board.iteration}, it=board.iteration, ph="system")
        save_snapshot(board.get_persistable_snapshot())
        time.sleep(DELAY_BETWEEN_ITERATIONS)


def _process_inbox_command(board: Blackboard, journal: ExecutionJournal | NullJournal, cmd: dict[str, Any]) -> None:
    cmd_type = cmd.get("type", "")
    payload = cmd.get("payload", "")
    trace("inbox.process", f"type={cmd_type} payload={payload}")

    if cmd_type == "goal_rewrite":
        board.rewrite_goal(payload)
        journal.append("inbox.goal_rewrite", {"new_goal": payload}, it=board.iteration)
    elif cmd_type == "hint":
        board.problem = payload
        journal.append("inbox.hint", {"hint": payload}, it=board.iteration)
    elif cmd_type == "inject_lesson":
        store = Lessons()
        store._data.setdefault("insights", []).append(payload)
        store._save()
        journal.append("inbox.lesson", {"lesson": payload}, it=board.iteration)
    elif cmd_type == "set_chaos":
        try:
            board.chaos_level = float(payload)
        except ValueError:
            pass
    elif cmd_type == "kill":
        journal.append("inbox.kill", {}, it=board.iteration)
        raise SystemExit(0)


def _spawn_distillation(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    try:
        goal = (
            f"DISTILLATION — Analyze recent execution. chaos={board.chaos_level:.2f}. "
            f"Produce evolutionary insights and refined goal recommendations."
        )
        cmd = ["python", str(BASE_DIR / "main.py"), goal,
               "--backend", get_backend(), "--agent-id", "distill"]
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        journal.append("distillation.spawned", {"goal": goal}, it=board.iteration)
        trace("orchestrator.distill_spawn", f"goal={goal}")
    except Exception as e:
        journal.append("error.distillation_spawn", {"error": str(e)}, it=board.iteration, lvl="ERROR")


def _execute_decomposition(board: Blackboard, journal: ExecutionJournal | NullJournal, decompose: list[dict[str, Any]]) -> None:
    backend = get_backend()

    if backend == "acp":
        for subtask in decompose:
            sub_goal = subtask.get("sub_goal", "")
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:6]}")
            if not sub_goal:
                continue
            print(f"  [SUBTASK] {agent_id}: {sub_goal}")
            child_board = Blackboard()
            child_board.goal = sub_goal
            child_board.agent_id = agent_id
            from journal import create_execution_journal
            child_journal = create_execution_journal(BASE_DIR, sub_goal)
            success = run(child_board, child_journal, interrupted=lambda: False)
            child_journal.close()
            result_text = child_board.done_evidence or child_board.last_observation or ""
            state = "done" if success else "failed"
            handle = AgentHandle(agent_id=agent_id, goal=sub_goal, pid=0,
                                 status_file=BASE_DIR / "blackboard" / "blackboard_state.json")
            handle.state = state
            handle.result = result_text
            board.children[agent_id] = handle
            if success:
                board.completed_subtasks.append({"agent_id": agent_id, "goal": sub_goal, "result": result_text})
            print(f"  [SUBTASK DONE] {agent_id}: {state} - {result_text}")
    else:
        for subtask in decompose:
            sub_goal = subtask.get("sub_goal", "")
            agent_id = subtask.get("agent_id", f"agent_{uuid.uuid4().hex[:6]}")
            if not sub_goal:
                continue
            handle, _ = _spawn_child(agent_id, sub_goal, journal, board.iteration)
            if handle:
                board.children[agent_id] = handle
                print(f"  [SPAWN] {agent_id} pid={handle.pid}: {sub_goal}")

    journal.append("decompose", {
        "subtasks": len(decompose),
        "agents": list(board.children.keys()),
    }, it=board.iteration, ph="coordinate")


def _spawn_child(agent_id: str, goal: str, journal: ExecutionJournal | NullJournal, iteration: int = 0) -> tuple[AgentHandle | None, subprocess.Popen[bytes] | None]:
    from persistence import register_agent
    cmd = [
        "python", str(BASE_DIR / "main.py"), goal,
        "--backend", get_backend(), "--agent-id", agent_id,
    ]
    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        register_agent(agent_id, proc.pid)
        journal.append("child.spawned", {"agent_id": agent_id, "goal": goal, "pid": proc.pid},
                       it=iteration, ph="coordinate")
        return AgentHandle(agent_id=agent_id, goal=goal, pid=proc.pid, status_file=BASE_DIR / "blackboard" / "blackboard_state.json"), proc
    except Exception as e:
        journal.append("error.spawn", {"agent_id": agent_id, "error": str(e)}, it=iteration, lvl="ERROR")
        return None, None


def _report_status(agent_id: str, state: str, result: str = "", error: str = "") -> None:
    if not agent_id or agent_id == "main":
        return
    from persistence import post_event
    verb = "child_done" if state == "done" else "child_failed"
    post_event(verb, agent_id, "main", {"result": result, "error": error})


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


def _call_llm_role(role: str, spec: RoleSpec, context: str,
                   journal: ExecutionJournal | NullJournal, iteration: int = 0) -> dict[str, Any] | None:
    try:
        result = call_role(spec, context)
        if not isinstance(result, dict):
            journal.append(f"error.{role}", {"error": f"non-dict response: {type(result).__name__}"}, it=iteration, lvl="ERROR")
            return None
        journal.append(f"{role}.output", result, it=iteration, aid=role, ph=role)
        return result
    except Exception as e:
        err_str = str(e)
        journal.append(f"error.{role}", {"error": err_str}, it=iteration, lvl="ERROR")
        print(f"  [ERROR] {role} parse failed: {err_str}")
        if any(x in err_str.lower() for x in ["not going to help", "i'm not going to", "cannot assist", "refusal", "safety", "impersonation"]):
            return {"__refusal_detected__": True, "error": err_str}
        return None


def _call_verifier(board: Blackboard, journal: ExecutionJournal | NullJournal, instruction: str = "") -> bool:
    context = board.verifier_context(instruction)
    try:
        result = call_role(VERIFIER_SPEC, context)
        verdict = result.get("verdict", "denied")
        journal.append("verifier.output", result, it=board.iteration, aid="verifier", ph="verify")
        print(f"  [VERIFY] {verdict}: {result.get('reason', '')}")
        return verdict == "confirmed"
    except Exception as e:
        journal.append("error.verifier", {"error": str(e)}, it=board.iteration, lvl="ERROR")
        return False


def _call_reflector(board: Blackboard, journal: ExecutionJournal | NullJournal) -> None:
    context = board.build_reflector_context()
    trace("orchestrator.reflector", f"it={board.iteration} context_len={len(context)} chaos={board.chaos_level:.3f}")

    try:
        result = call_role(REFLECTOR_SPEC, context)
        journal.append("reflector.output", result, it=board.iteration, aid="reflector", ph="reflect")
        print(f"  [REFLECT] {result.get('diagnosis', '')}")

        lessons_list: list[str] = []
        for key in ("lesson_1", "lesson_2", "lesson_3"):
            l = result.get(key)
            if l and isinstance(l, str) and l.strip():
                lessons_list.append(l.strip())

        if lessons_list:
            store = Lessons()
            for lesson in lessons_list:
                store._data.setdefault("insights", []).append(lesson)
            store._save()

        for role, key in [("actor", "actor_prompt_rewrite"),
                          ("planner", "planner_prompt_rewrite"),
                          ("verifier", "verifier_prompt_rewrite")]:
            rewrite = result.get(key, "").strip()
            if not rewrite:
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
            journal.append("reflector.applied", {"role": role, "len": len(rewrite)}, it=board.iteration, aid="reflector")

        goal_rewrite = result.get("goal_rewrite")
        if goal_rewrite and isinstance(goal_rewrite, str) and goal_rewrite.strip():
            old = board.goal
            board.rewrite_goal(goal_rewrite.strip())
            trace("orchestrator.goal_rewrite", f"old={old} new={board.goal}")
            journal.append("reflector.goal_rewritten", {"old": old, "new": board.goal}, it=board.iteration, aid="reflector")
    except Exception as e:
        err = str(e)
        trace("orchestrator.reflector_error", f"it={board.iteration} error={err}")
        journal.append("error.reflector", {"error": err}, it=board.iteration, lvl="ERROR")
        print(f"  [ERROR] reflector failed:\n{err}\n")
