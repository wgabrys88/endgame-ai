from __future__ import annotations
import json
import time
from typing import Any, Callable, cast

from agents.stagnation import StagnationAgent
from agents.lorenz import LorenzAgent
from agents.pid import PidAgent
from agents.scheduler import SchedulerAgent
from agents.observer_agent import ObserverAgent
from agents.planner import PlannerAgent
from agents.actor import ActorAgent
from agents.verifier import VerifierAgent
from agents.reflector import ReflectorAgent
from config import DELAY_BETWEEN_CYCLES, DISABLED_PATH, SNAPSHOT_PATH
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


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.get("goal", ""), "budget": log.budget()})
    board["next"] = "stagnation"

    while board.get("next") not in ("done", "halt") and not log.exhausted() and not interrupted():
        name = str(board["next"])
        disabled = _load_disabled()

        if name in disabled:
            board["next"] = "stagnation"
            continue

        if name not in AGENTS:
            board["next"] = "stagnation"
            continue

        agent = AGENTS[name]
        ctx = {k: board[k] for k in agent.reads if k in board}
        result: dict[str, Any] = agent.run(ctx)

        board.update(result.get("writes", {}))
        board["next"] = result.get("next", "stagnation")
        log.emit(result.get("phase", name), result.get("data"))
        _save(board)

        if name in ("observer", "planner", "actor", "verifier", "reflector"):
            time.sleep(DELAY_BETWEEN_CYCLES)

    next_val = board.get("next", "")
    if next_val == "done":
        log.emit("complete", {"goal": board.get("goal", ""), "events": log.count()})
        return True
    if next_val == "halt":
        log.emit("halt", {"stagnation": board.get("stagnation_score", 0), "events": log.count()})
        return False
    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count()})
    return False


def _load_disabled() -> set[str]:
    if not DISABLED_PATH.exists():
        return set()
    try:
        raw: object = json.loads(DISABLED_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return {str(v) for v in cast(list[Any], raw)}
    except (json.JSONDecodeError, OSError):
        pass
    return set()


def _save(board: dict[str, Any]) -> None:
    data = {
        "goal": board.get("goal", ""),
        "plan_steps": board.get("plan_steps", []),
        "plan_index": board.get("plan_index", 0),
        "history": board.get("history", [])[-20:],
        "consecutive_failures": board.get("consecutive_failures", 0),
        "stagnation_score": board.get("stagnation_score", 0),
        "repetition_score": board.get("repetition_score", 0),
        "lorenz_x": board.get("lorenz_x", 0),
        "lorenz_y": board.get("lorenz_y", 0),
        "lorenz_z": board.get("lorenz_z", 0),
        "attractor_energy": board.get("attractor_energy", 1),
        "lorenz_wing_crossed": board.get("lorenz_wing_crossed", False),
        "pid_output": board.get("pid_output", 0),
        "pid_integral": board.get("pid_integral", 0),
        "screen_stagnation": board.get("screen_stagnation", 0),
        "halt_count": board.get("halt_count", 0),
        "jacobian": board.get("jacobian", {}),
        "last_verb": board.get("last_verb", ""),
        "last_instruction": board.get("last_instruction", ""),
        "focused_window": board.get("focused_window", ""),
        "events": log.count(),
        "budget": log.budget(),
    }
    SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
