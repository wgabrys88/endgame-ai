from __future__ import annotations
import json
import time
from typing import Any, Callable, cast

from board import Board
from agents import AgentResult
from agents.observer_agent import ObserverAgent
from agents.stagnation import StagnationAgent
from agents.lorenz import LorenzAgent
from agents.pid import PidAgent
from agents.jacobian import JacobianAgent
from agents.scheduler import SchedulerAgent
from agents.planner import PlannerAgent
from agents.actor import ActorAgent
from agents.verifier import VerifierAgent
from agents.reflector import ReflectorAgent
from config import DELAY_BETWEEN_CYCLES, DISABLED_PATH
import log


HEARTBEAT = [
    ObserverAgent(),
    StagnationAgent(),
    LorenzAgent(),
    PidAgent(),
    JacobianAgent(),
]

SCHEDULER = SchedulerAgent()

LLM_AGENTS: dict[str, PlannerAgent | ActorAgent | VerifierAgent | ReflectorAgent] = {
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "reflector": ReflectorAgent(),
}


def run(board: Board, interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.goal, "budget": log.budget()})

    while not log.exhausted() and not interrupted():
        _sync_disabled(board)

        for agent in HEARTBEAT:
            if agent.name in board.disabled_agents:
                continue
            if agent.should_run(board):
                result: AgentResult = agent.run(board)
                board.apply(result.writes)
                if result.event_phase:
                    log.trace(result.event_phase, result.event_data)

        schedule = SCHEDULER.run(board)
        board.apply(schedule.writes)
        if schedule.event_phase:
            log.trace(schedule.event_phase, schedule.event_data)

        next_llm = schedule.next_agent

        if next_llm == "halt":
            log.emit("halt", {"stagnation": board.stagnation_score, "events": log.count()})
            board.save()
            return False

        if not board.goal:
            board.save()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        if log.exhausted():
            break

        if next_llm in board.disabled_agents:
            board.requested_next = ""
            board.save()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        llm_agent = LLM_AGENTS.get(next_llm)
        if llm_agent is None:
            break

        llm_result = llm_agent.run(board)
        board.apply(llm_result.writes)
        if llm_result.event_phase:
            log.emit(llm_result.event_phase, llm_result.event_data)

        if llm_result.next_agent == "done":
            log.emit("complete", {"goal": board.goal, "events": log.count()})
            board.save()
            return True

        board.save()
        time.sleep(DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count()})
    board.save()
    return False


def _sync_disabled(board: Board) -> None:
    if not DISABLED_PATH.exists():
        board.disabled_agents = set()
        return
    try:
        raw: object = json.loads(DISABLED_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            board.disabled_agents = {str(v) for v in cast(list[Any], raw)}
    except (json.JSONDecodeError, OSError):
        pass
