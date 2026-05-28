from __future__ import annotations
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from config import (
    BASE_DIR, DELAY_BETWEEN_CYCLES,
    BUDGET_PLANNER_IN, BUDGET_PLANNER_OUT,
    BUDGET_ACTOR_IN, BUDGET_ACTOR_OUT,
    BUDGET_VERIFIER_IN, BUDGET_VERIFIER_OUT,
    BUDGET_REFLECTOR_IN, BUDGET_REFLECTOR_OUT,
    PROMPTS_DIR,
    trace,
)
from state import Blackboard, AgentHandle
from journal import ExecutionJournal
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


def run(board: Blackboard, journal: ExecutionJournal, max_cycles: int, *,
        interrupted: Callable[[], bool] = lambda: False) -> bool:

    board.max_cycles = max_cycles
    prev_screen_hash = ""
    reflector_called_this_cycle = False
    spawns_this_cycle = 0

    def on_goal_rewritten(payload):
        journal.append("blackboard.goal_rewritten", payload, cyc=board.cycle, aid="blackboard")
    board.events.subscribe("goal.rewritten", on_goal_rewritten)

    def on_chaos_change(payload):
        if payload.get("new", 0) > 0.5:
            journal.append("blackboard.high_chaos", payload, cyc=board.cycle, aid="blackboard")
    board.events.subscribe("chaos.changed", on_chaos_change)

    def on_needs_reflection(payload):
        nonlocal reflector_called_this_cycle
        if not reflector_called_this_cycle:
            reflector_called_this_cycle = True
            journal.append("blackboard.reflection_triggered", payload, cyc=board.cycle, aid="blackboard")
            _call_reflector(board, journal, board.cycle)
    board.events.subscribe("self_regulation.needs_reflection", on_needs_reflection)

    def on_needs_goal_softening(payload):
        soft_goal = (
            f"SOFTENED RECOVERY: Re-strategize with lower risk first steps. "
            f"Original intent: {board.original_goal}"
        )
        board.rewrite_goal(soft_goal)
        journal.append("blackboard.goal_softened", {"new_goal": soft_goal}, cyc=board.cycle, aid="blackboard")
    board.events.subscribe("self_regulation.needs_goal_softening", on_needs_goal_softening)

    def on_emergency_reflection(payload):
        nonlocal reflector_called_this_cycle, spawns_this_cycle
        journal.append("blackboard.emergency_reflection", payload, cyc=board.cycle, aid="blackboard")
        if not reflector_called_this_cycle:
            reflector_called_this_cycle = True
            _call_reflector(board, journal, board.cycle)
        board.consecutive_failures = 0
        if spawns_this_cycle < 1:
            spawns_this_cycle += 1
            _spawn_distillation(board, journal)
    board.events.subscribe("self_regulation.needs_emergency_reflection", on_emergency_reflection)

    def on_periodic_reflection(payload):
        nonlocal reflector_called_this_cycle
        if not reflector_called_this_cycle:
            reflector_called_this_cycle = True
            trace("orchestrator.periodic_reflect", f"cycle={board.cycle}")
            _call_reflector(board, journal, board.cycle)
    board.events.subscribe("evolution.periodic_reflection_due", on_periodic_reflection)

    def on_distillation_due(payload):
        nonlocal spawns_this_cycle
        if spawns_this_cycle < 1:
            spawns_this_cycle += 1
            _spawn_distillation(board, journal)
    board.events.subscribe("evolution.distillation_due", on_distillation_due)

    def on_refusal_detected(payload):
        journal.append("refusal.detected", payload, cyc=board.cycle, aid="blackboard")
        board.chaos_level = min(1.0, board.chaos_level + 0.2)
        if board.consecutive_failures >= 3:
            board.events.publish("self_regulation.needs_emergency_reflection", {
                "reason": "repeated_refusals", "cycle": board.cycle
            })
    board.events.subscribe("refusal.detected", on_refusal_detected)

    def on_action_recorded(payload):
        board._broadcast_action(payload["verb"], payload["success"], payload.get("obs", ""))
    board.events.subscribe("action.recorded", on_action_recorded)

    for cycle in range(board.cycle + 1, max_cycles + 1):
        if interrupted():
            journal.append("run.interrupted", {"cycle": cycle}, cyc=cycle)
            _report_status(board.agent_id, "failed", error="interrupted")
            return False

        reflector_called_this_cycle = False
        spawns_this_cycle = 0
        board.clear_signals()
        board.advance_cycle(cycle)

        journal.append("cycle.start", {"cycle": cycle}, cyc=cycle, ph="system")
        trace("orchestrator.cycle", f"cycle={cycle} chaos={board.chaos_level:.3f} rep={board.repetition_score:.3f} failures={board.consecutive_failures} mode={board.mode}")
        print(f"\n{'='*40}\n[CYCLE {cycle}]\n{'='*40}")

        inbox_commands = board.poll_inbox()
        for cmd in inbox_commands:
            _process_inbox_command(board, journal, cycle, cmd)

        child_events = board.poll_children()
        for ev in child_events:
            journal.append("child.event", ev, cyc=cycle, ph="coordinate")
            print(f"  [CHILD] {ev['agent_id']}: {ev['state']} - {ev.get('result','')}")

        if board.all_children_done() and not board.pending_subtasks and board.mode == "coordinate":
            if not board.any_children_failed():
                board.mode = "direct"
                board.last_verb = ""

        if not board.acquire_screen():
            print(f"  [WAIT] Screen locked by another agent. Skipping GUI this cycle.")
            time.sleep(DELAY_BETWEEN_CYCLES)
            journal.append("cycle.end", {"cycle": cycle, "screen_locked": True}, cyc=cycle, ph="system")
            continue

        try:
            obs = observe()
            board.record_screen(obs.context_text, obs.content_hash, obs.book)
            journal.append("screen.observed", {"hash": obs.content_hash, "elements": len(obs.book)},
                           cyc=cycle, aid="observer", ph="observe")
        except Exception as e:
            board.release_screen()
            journal.append("error.observe", {"error": str(e)}, cyc=cycle, lvl="ERROR")
            print(f"  [ERROR] observe failed: {e}")
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        if obs.content_hash == prev_screen_hash and board.last_verb == "wait" and not child_events:
            board.release_screen()
            journal.append("screen.unchanged", {"hash": obs.content_hash}, cyc=cycle, ph="system")
            time.sleep(DELAY_BETWEEN_CYCLES)
            prev_screen_hash = obs.content_hash
            journal.append("cycle.end", {"cycle": cycle, "skipped": True}, cyc=cycle, ph="system")
            continue

        prev_screen_hash = obs.content_hash

        context = board.planner_context()
        if board.chaos_level > 0.45:
            context += (
                f"\n\n[CHAOS — Level {board.chaos_level:.2f} | Repetition {board.repetition_score:.2f}] "
                f"Break the current pattern. Prefer parallel mode or spawn_agent."
            )

        trace("orchestrator.planner_context", f"context_len={len(context)} chaos_injected={board.chaos_level > 0.45}")
        plan = _call_llm_role("planner", PLANNER_SPEC, context, journal, cycle)

        if isinstance(plan, dict) and plan.get("__refusal_detected__"):
            trace("orchestrator.refusal", f"role=planner cycle={cycle} error={plan.get('error', '')}")
            board.events.publish("refusal.detected", {
                "role": "planner", "cycle": cycle, "error_preview": plan.get("error", ""),
            })
            board.record_failure()
            board.record_failure()
            board.release_screen()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        if not plan:
            board.release_screen()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        mode = plan.get("mode", "direct")
        next_action = plan.get("next_action", "")
        decompose = plan.get("decompose", [])

        if mode == "done" and board.chaos_rejects_done():
            mode = "parallel" if board.chaos_forces_parallel() else "direct"
            trace("orchestrator.chaos_reject_done", f"cycle={cycle} chaos={board.chaos_level:.3f} forced_mode={mode}")
            if mode == "direct" and not next_action:
                next_action = "Observe the current screen state and take the first concrete step toward the goal."

        if board.chaos_forces_parallel() and mode == "direct":
            mode = "parallel"
            if not decompose:
                decompose = [{"sub_goal": f"Sub-task from forced decomposition: {next_action or board.goal[:200]}", "agent_id": f"chaos_{cycle}"}]
            trace("orchestrator.chaos_force_parallel", f"cycle={cycle} chaos={board.chaos_level:.3f}")

        print(f"  [PLAN] mode={mode} chaos={board.chaos_level:.2f} [{board.lorenz_x:.1f},{board.lorenz_y:.1f},{board.lorenz_z:.1f}]")

        if mode == "done" or next_action.strip().lower() == "done":
            board.release_screen()
            journal.append("goal.complete", {"cycle": cycle}, cyc=cycle)
            _report_status(board.agent_id, "done", result=next_action)
            return True

        if mode == "parallel" and decompose:
            board.mode = "coordinate"
            board.release_screen()
            _execute_decomposition(board, journal, cycle, decompose)
            journal.append("cycle.end", {"cycle": cycle}, cyc=cycle, ph="system")
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        actor_out = _call_llm_role("actor", ACTOR_SPEC, board.actor_context(next_action), journal, cycle)

        if isinstance(actor_out, dict) and actor_out.get("__refusal_detected__"):
            trace("orchestrator.refusal", f"role=actor cycle={cycle} error={actor_out.get('error', '')}")
            board.events.publish("refusal.detected", {
                "role": "actor", "cycle": cycle, "error_preview": actor_out.get("error", ""),
            })
            board.record_failure()
            board.record_failure()
            board.release_screen()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        if not actor_out:
            board.release_screen()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        board.actor_observe = actor_out.get("observe", "")
        board.actor_reason = actor_out.get("reason", "")
        board.last_expect = actor_out.get("expect", "")

        conclusion = actor_out.get("conclusion", "EXPECTED")
        if conclusion == "UNEXPECTED":
            board.expectation_miss_streak += 1
        else:
            board.expectation_miss_streak = 0

        cycle_had_failure = False
        raw_actions = []
        for key in ("action_1", "action_2", "action_3"):
            a = actor_out.get(key)
            if a and isinstance(a, dict) and a.get("verb"):
                raw_actions.append(a)
        if not raw_actions:
            old_actions = actor_out.get("actions", [])
            if old_actions:
                raw_actions = old_actions[:3]

        for action_obj in raw_actions:
            if isinstance(action_obj, str):
                continue
            verb = action_obj.get("verb", "")
            target = action_obj.get("target", "")
            value = action_obj.get("value", "")
            args = _build_args(verb, target, value)
            if verb not in VERBS:
                board.record_action(verb, args, False, f"unknown verb: {verb}")
                cycle_had_failure = True
                break
            if board.chaos_blocks_action(verb, target):
                board.record_action(verb, args, False, f"CHAOS BLOCKED: {verb}:{target}")
                trace("orchestrator.chaos_block", f"blocked {verb}:{target} chaos={board.chaos_level:.3f}")
                cycle_had_failure = True
                break

            result = execute_verb(verb, args, board.screen_elements, board)
            board.record_action(verb, args, result.success, result.observation)

            journal.append(f"action.{verb}", {
                "verb": verb, "args": args,
                "success": result.success, "observation": result.observation,
            }, cyc=cycle, aid="actor", ph="act")
            print(f"  [{verb}] {result.observation}")

            if not result.success:
                cycle_had_failure = True
                break

            if verb == "done":
                board.done_claimed = True
                board.done_evidence = result.observation
                break

        board.release_screen()

        if board.done_claimed or board.problem:
            verified = _call_verifier(board, journal, cycle, next_action)
            if verified and board.done_claimed:
                journal.append("goal.complete", {"cycle": cycle}, cyc=cycle)
                _report_status(board.agent_id, "done", result=board.done_evidence)
                return True
            if not verified:
                cycle_had_failure = True

        if cycle_had_failure:
            board.record_failure()
        else:
            board.record_success()

        journal.append("cycle.end", {"cycle": cycle}, cyc=cycle, ph="system")
        save_snapshot(board.get_persistable_snapshot())
        time.sleep(DELAY_BETWEEN_CYCLES)

    journal.append("run.end", {"success": False, "reason": "max_cycles", "max": max_cycles}, cyc=max_cycles)
    _report_status(board.agent_id, "failed", error="max_cycles exhausted")
    return False


def _process_inbox_command(board: Blackboard, journal: ExecutionJournal, cycle: int, cmd: dict) -> None:
    cmd_type = cmd.get("type", "")
    payload = cmd.get("payload", "")
    trace("inbox.process", f"type={cmd_type} payload={payload}")

    if cmd_type == "goal_rewrite":
        board.rewrite_goal(payload)
        journal.append("inbox.goal_rewrite", {"new_goal": payload}, cyc=cycle)
    elif cmd_type == "hint":
        board.problem = payload
        journal.append("inbox.hint", {"hint": payload}, cyc=cycle)
    elif cmd_type == "inject_lesson":
        store = Lessons()
        store._data.setdefault("insights", []).append(payload)
        store._save()
        journal.append("inbox.lesson", {"lesson": payload}, cyc=cycle)
    elif cmd_type == "set_chaos":
        try:
            board.chaos_level = float(payload)
        except ValueError:
            pass
    elif cmd_type == "kill":
        journal.append("inbox.kill", {}, cyc=cycle)
        raise SystemExit(0)


def _spawn_distillation(board: Blackboard, journal: ExecutionJournal) -> None:
    try:
        goal = (
            f"DISTILLATION — Analyze recent execution. chaos={board.chaos_level:.2f}. "
            f"Produce evolutionary insights and refined goal recommendations."
        )
        cmd = ["python", str(BASE_DIR / "main.py"), goal, "--cycles", "6",
               "--backend", get_backend(), "--distill", "--agent-id", "distill"]
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        journal.append("distillation.spawned", {"goal": goal}, cyc=board.cycle)
        trace("orchestrator.distill_spawn", f"goal={goal}")
    except Exception as e:
        journal.append("error.distillation_spawn", {"error": str(e)}, cyc=board.cycle, lvl="ERROR")


def _execute_decomposition(board: Blackboard, journal: ExecutionJournal, cycle: int, decompose: list) -> None:
    backend = get_backend()

    if backend == "acp":
        for subtask in decompose[:5]:
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
            success = run(child_board, child_journal, 6)
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
            handle, _ = _spawn_child(agent_id, sub_goal, journal, cycle)
            if handle:
                board.children[agent_id] = handle
                print(f"  [SPAWN] {agent_id} pid={handle.pid}: {sub_goal}")

    journal.append("decompose", {
        "subtasks": len(decompose),
        "agents": list(board.children.keys()),
    }, cyc=cycle, ph="coordinate")


def _spawn_child(agent_id: str, goal: str, journal: ExecutionJournal, cycle: int) -> tuple[AgentHandle | None, subprocess.Popen | None]:
    from persistence import register_agent
    cmd = [
        "python", str(BASE_DIR / "main.py"), goal,
        "--cycles", "8", "--backend", get_backend(),
        "--agent-id", agent_id,
    ]
    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        register_agent(agent_id, proc.pid)
        journal.append("child.spawned", {"agent_id": agent_id, "goal": goal, "pid": proc.pid},
                       cyc=cycle, ph="coordinate")
        return AgentHandle(agent_id=agent_id, goal=goal, pid=proc.pid, status_file=BASE_DIR / "blackboard" / "blackboard_state.json"), proc
    except Exception as e:
        journal.append("error.spawn", {"agent_id": agent_id, "error": str(e)}, cyc=cycle, lvl="ERROR")
        return None, None


def _report_status(agent_id: str, state: str, result: str = "", error: str = "") -> None:
    if not agent_id or agent_id == "main":
        return
    from persistence import post_event
    verb = "child_done" if state == "done" else "child_failed"
    post_event(verb, agent_id, "main", {"result": result, "error": error})


def _build_args(verb: str, target: str, value: str) -> dict:
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
                   journal: ExecutionJournal, cycle: int) -> dict | None:
    try:
        result = call_role(spec, context)
        if not isinstance(result, dict):
            journal.append(f"error.{role}", {"error": f"non-dict response: {type(result).__name__}"}, cyc=cycle, lvl="ERROR")
            return None
        journal.append(f"{role}.output", result, cyc=cycle, aid=role, ph=role)
        return result
    except Exception as e:
        err_str = str(e)
        journal.append(f"error.{role}", {"error": err_str}, cyc=cycle, lvl="ERROR")
        print(f"  [ERROR] {role} failed:\n{err_str}\n")
        if any(x in err_str.lower() for x in ["not going to help", "i'm not going to", "cannot assist", "refusal", "safety", "impersonation"]):
            return {"__refusal_detected__": True, "error": err_str}
        return None


def _call_verifier(board: Blackboard, journal: ExecutionJournal, cycle: int, instruction: str = "") -> bool:
    context = board.verifier_context(instruction)
    try:
        result = call_role(VERIFIER_SPEC, context)
        verdict = result.get("verdict", "denied")
        journal.append("verifier.output", result, cyc=cycle, aid="verifier", ph="verify")
        print(f"  [VERIFY] {verdict}: {result.get('reason', '')}")
        return verdict == "confirmed"
    except Exception as e:
        journal.append("error.verifier", {"error": str(e)}, cyc=cycle, lvl="ERROR")
        return False


def _call_reflector(board: Blackboard, journal: ExecutionJournal, cycle: int) -> None:
    context = board.build_reflector_context()
    trace("orchestrator.reflector", f"cycle={cycle} context_len={len(context)} chaos={board.chaos_level:.3f}")

    try:
        result = call_role(REFLECTOR_SPEC, context)
        journal.append("reflector.output", result, cyc=cycle, aid="reflector", ph="reflect")
        print(f"  [REFLECT] {result.get('diagnosis', '')}")

        lessons_list = []
        for key in ("lesson_1", "lesson_2", "lesson_3"):
            l = result.get(key)
            if l and isinstance(l, str) and l.strip():
                lessons_list.append(l.strip())

        if lessons_list:
            store = Lessons()
            for lesson in lessons_list:
                if not isinstance(lesson, str) or not lesson.strip():
                    continue
                store._data.setdefault("insights", []).append(lesson.strip())
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
            journal.append("reflector.applied", {"role": role, "len": len(rewrite)}, cyc=cycle, aid="reflector")

        goal_rewrite = result.get("goal_rewrite")
        if goal_rewrite and isinstance(goal_rewrite, str) and goal_rewrite.strip():
            old = board.goal
            board.rewrite_goal(goal_rewrite.strip())
            trace("orchestrator.goal_rewrite", f"old={old} new={board.goal}")
            journal.append("reflector.goal_rewritten", {"old": old, "new": board.goal}, cyc=cycle, aid="reflector")
    except Exception as e:
        err = str(e)
        trace("orchestrator.reflector_error", f"cycle={cycle} error={err}")
        journal.append("error.reflector", {"error": err}, cyc=cycle, lvl="ERROR")
        print(f"  [ERROR] reflector failed:\n{err}\n")
