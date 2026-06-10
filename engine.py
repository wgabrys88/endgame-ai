from __future__ import annotations
import json
import time
from typing import Any, Callable

from agents import (
    StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
    ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
)
import config
import log


AGENTS: dict[str, Any] = {
    "stagnation": StagnationAgent(),
    "lorenz": LorenzAgent(),
    "pid": PidAgent(),
    "scheduler": SchedulerAgent(),
    "observer": ObserverAgent(),
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "reflector": ReflectorAgent(),
}

LLM_AGENTS: frozenset[str] = frozenset({"planner", "actor", "verifier", "reflector"})


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.get("goal", ""), "budget": log.budget()})
    board["next"] = "stagnation"
    board["cycle"] = 0

    while board.get("next") not in ("done", "halt") and not log.exhausted() and not interrupted():
        name = str(board["next"])
        if name not in AGENTS:
            board["next"] = "stagnation"
            continue

        if name in LLM_AGENTS:
            obs = AGENTS["observer"]
            obs_ctx = {k: board[k] for k in obs.reads if k in board}
            obs_result: dict[str, Any] = obs.run(obs_ctx)
            board.update(obs_result.get("writes", {}))
            log.emit(obs_result.get("phase", "observe"), obs_result.get("data"))

        agent = AGENTS[name]
        ctx = {k: board[k] for k in agent.reads if k in board}
        result: dict[str, Any] = agent.run(ctx)
        board.update(result.get("writes", {}))
        board["next"] = result.get("next", "stagnation")
        log.emit(result.get("phase", name), result.get("data"))
        board["cycle"] = board.get("cycle", 0) + 1
        _save(board)

        if name in LLM_AGENTS:
            time.sleep(config.DELAY_BETWEEN_CYCLES)

    final = board.get("next", "")
    if final == "done":
        log.emit("complete", {"goal": board.get("goal", ""), "events": log.count()})
        return True
    if final == "halt":
        log.emit("halt", {"events": log.count()})
        return False
    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count()})
    return False


def _save(board: dict[str, Any]) -> None:
    data = {
        "goal": board.get("goal", ""),
        "plan": board.get("plan", []),
        "history": board.get("history", [])[-20:],
        "consecutive_failures": board.get("consecutive_failures", 0),
        "stagnation": board.get("stagnation", 0),
        "lorenz_x": board.get("lorenz_x", 0),
        "lorenz_y": board.get("lorenz_y", 0),
        "lorenz_z": board.get("lorenz_z", 0),
        "energy": board.get("energy", 1),
        "pid_output": board.get("pid_output", 0),
        "pid_integral": board.get("pid_integral", 0),
        "cycle": board.get("cycle", 0),
        "events": log.count(),
        "budget": log.budget(),
    }
    config.SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
