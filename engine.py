from __future__ import annotations
import json
import threading
import time
from typing import Any, Callable

from actions import is_python_step
from agents import (
    StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
    ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
    _similar_to_completed, _trivial_milestone,
)
import config
import log


MATH_AGENTS: list[Any] = [StagnationAgent(), LorenzAgent(), PidAgent()]

AGENTS: dict[str, Any] = {
    "scheduler": SchedulerAgent(),
    "observer": ObserverAgent(),
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "reflector": ReflectorAgent(),
}

LLM_AGENTS: frozenset[str] = frozenset({"planner", "actor", "verifier", "reflector"})


def _math_loop(board: dict[str, Any], stop: threading.Event) -> None:
    while not stop.is_set():
        for agent in MATH_AGENTS:
            ctx = {k: board[k] for k in agent.reads if k in board}
            result: dict[str, Any] = agent.run(ctx)
            board.update(result.get("writes", {}))
            log.emit(result.get("phase", agent.name), result.get("data"))
        trace: list[dict[str, Any]] = list(board.get("math_trace", []))
        trace.append({
            "stag": round(float(board.get("stagnation", 0)), 3),
            "pid": round(float(board.get("pid_output", 0)), 3),
            "energy": round(float(board.get("energy", 1)), 3),
            "wing": bool(board.get("wing_crossed", False)),
            "x": round(float(board.get("lorenz_x", 0)), 2),
        })
        board["math_trace"] = trace[-config.MATH_TRACE_LEN:]
        _save(board)
        stop.wait(config.MATH_INTERVAL)


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.get("goal", ""), "budget": log.budget()})

    stop = threading.Event()
    math_thread = threading.Thread(target=_math_loop, args=(board, stop), daemon=True)
    math_thread.start()

    try:
        return _main_loop(board, interrupted)
    finally:
        stop.set()
        math_thread.join(timeout=5)


def _needs_screen(board: dict[str, Any], target: str) -> bool:
    if target not in LLM_AGENTS or target == "planner":
        return False
    if target == "actor":
        active = next((s for s in board.get("plan", []) if s.get("status") == "active"), None)
        if active and is_python_step(str(active.get("text", ""))):
            return False
        return config.GUI_MODE_PATH.exists()
    return config.GUI_MODE_PATH.exists()


def _run_agent(board: dict[str, Any], name: str) -> dict[str, Any]:
    if _needs_screen(board, name):
        obs = AGENTS["observer"]
        obs_ctx = {k: board[k] for k in obs.reads if k in board}
        obs_result = obs.run(obs_ctx)
        board.update(obs_result.get("writes", {}))
        log.emit(obs_result.get("phase", "observe"), obs_result.get("data"))
    agent = AGENTS[name]
    ctx = {k: board[k] for k in agent.reads if k in board}
    result = agent.run(ctx)
    board.update(result.get("writes", {}))
    log.emit(result.get("phase", name), result.get("data"))
    return result


def _main_loop(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    while not log.exhausted() and not interrupted():
        scheduler = AGENTS["scheduler"]
        ctx = {k: board[k] for k in scheduler.reads if k in board}
        result: dict[str, Any] = scheduler.run(ctx)
        board.update(result.get("writes", {}))
        log.emit(result.get("phase", "schedule"), result.get("data"))

        target = str(result.get("next", ""))
        if target == "done":
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue
        if target == "halt":
            _save(board)
            log.emit("stop", {
                "reason": "goal_satisfied",
                "events": log.count(),
                "work": log.work_count(),
                "power": board.get("power", 0.0),
                "completions": len(board.get("completed", [])),
            })
            return True
        if target in ("idle",) or target not in AGENTS:
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        result = _run_agent(board, target)
        nxt = str(result.get("next", ""))
        if nxt == "halt":
            _save(board)
            log.emit("stop", {
                "reason": "goal_satisfied",
                "events": log.count(),
                "work": log.work_count(),
                "power": board.get("power", 0.0),
                "completions": len(board.get("completed", [])),
            })
            return True
        if nxt == "done":
            _fission(board)
            log.emit("fission_sustain", {"power": board.get("power", 0.0), "completions": len(board.get("completed", []))})
        elif nxt == "actor" and target == "planner":
            result = _run_agent(board, "actor")
            if str(result.get("next", "")) == "done":
                _fission(board)
        elif nxt == "planner" and target == "verifier":
            result = _run_agent(board, "planner")
            if str(result.get("next", "")) == "actor":
                _run_agent(board, "actor")

        _save(board)
        time.sleep(config.DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count(), "work": log.work_count(), "power": board.get("power", 0.0)})
    return False


def _fission(board: dict[str, Any]) -> None:
    completed: list[str] = board.get("completed", [])
    done_when = str(board.get("done_when", ""))
    goal = str(board.get("goal", ""))
    if _similar_to_completed(done_when, completed):
        log.emit("fission_blocked", {"reason": "repeat", "done_when": done_when})
        board["plan"] = []
        board["done_when"] = ""
        return
    if _trivial_milestone(goal, done_when):
        log.emit("fission_blocked", {"reason": "trivial", "done_when": done_when})
        board["plan"] = []
        board["done_when"] = ""
        board["consecutive_failures"] = int(board.get("consecutive_failures", 0)) + 1
        return
    if done_when:
        completed.append(done_when)
    board["completed"] = completed[-50:]
    start_time = float(board.get("start_time", time.time()))
    elapsed = max(1.0, time.time() - start_time)
    board["power"] = len(completed) / elapsed
    board["plan"] = []
    board["done_when"] = ""
    board["consecutive_failures"] = 0
    board["progress_history"] = []
    board["pid_integral"] = 0.0
    log.emit("fission", {"power": board["power"], "completions": len(completed)})


def _save(board: dict[str, Any]) -> None:
    data = {
        "goal": board.get("goal", ""),
        "plan": board.get("plan", []),
        "done_when": board.get("done_when", ""),
        "completed": board.get("completed", [])[-10:],
        "power": board.get("power", 0.0),
        "consecutive_failures": board.get("consecutive_failures", 0),
        "stagnation": board.get("stagnation", 0),
        "lorenz_x": board.get("lorenz_x", 0),
        "lorenz_y": board.get("lorenz_y", 0),
        "lorenz_z": board.get("lorenz_z", 0),
        "energy": board.get("energy", 1),
        "pid_output": board.get("pid_output", 0),
        "pid_integral": board.get("pid_integral", 0),
        "wing_crossed": board.get("wing_crossed", False),
        "reflect_trigger": board.get("reflect_trigger", {}),
        "focused_window": board.get("focused_window", ""),
        "math_trace": board.get("math_trace", [])[-12:],
        "events": log.count(),
        "work_events": log.work_count(),
        "budget": log.budget(),
    }
    config.SNAPSHOT_PATH.write_text(json.dumps(data), encoding="utf-8")