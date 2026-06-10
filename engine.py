from __future__ import annotations
import json
import threading
import time
from typing import Any, Callable

from agents import (
    StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
    ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
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
            log.emit("halt", {"events": log.count()})
            return False

        if target == "idle":
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        if target not in AGENTS:
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        if target in LLM_AGENTS:
            obs = AGENTS["observer"]
            obs_ctx = {k: board[k] for k in obs.reads if k in board}
            obs_result: dict[str, Any] = obs.run(obs_ctx)
            board.update(obs_result.get("writes", {}))
            log.emit(obs_result.get("phase", "observe"), obs_result.get("data"))

        agent = AGENTS[target]
        ctx = {k: board[k] for k in agent.reads if k in board}
        result = agent.run(ctx)
        board.update(result.get("writes", {}))
        log.emit(result.get("phase", target), result.get("data"))

        agent_next = str(result.get("next", ""))
        if agent_next == "done":
            _fission(board)
            if board.get("goal"):
                log.emit("complete", {"goal": board["goal"], "events": log.count(), "power": board.get("power", 0.0)})
                _save(board)
                return True
            log.emit("fission_sustain", {"power": board.get("power", 0.0), "completions": len(board.get("completed", []))})

        _save(board)
        time.sleep(config.DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count(), "power": board.get("power", 0.0)})
    return False


def _fission(board: dict[str, Any]) -> None:
    completed: list[str] = board.get("completed", [])
    done_when = str(board.get("done_when", ""))
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
        "events": log.count(),
        "budget": log.budget(),
    }
    config.SNAPSHOT_PATH.write_text(json.dumps(data), encoding="utf-8")
