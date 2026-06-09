from __future__ import annotations
import json
import time
from typing import Any, Callable, cast

from board import Board
from agents import AgentResult
from agents.observer_agent import ObserverAgent
from agents.pulse import PulseAgent
from agents.planner import PlannerAgent
from agents.actor import ActorAgent
from agents.verifier import VerifierAgent
from agents.reflector import ReflectorAgent
from config import DELAY_BETWEEN_CYCLES, DISABLED_PATH
import log


OBSERVER = ObserverAgent()
PULSE = PulseAgent()

AGENTS: dict[str, PlannerAgent | ActorAgent | VerifierAgent | ReflectorAgent] = {
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "reflector": ReflectorAgent(),
}


def run(board: Board, interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.goal, "budget": log.budget()})

    while not log.exhausted() and not interrupted():
        _sync_disabled(board)

        if "observer" not in board.disabled_agents:
            _emit_agent(OBSERVER, board)
            if log.exhausted():
                break

        next_name = _emit_agent(PULSE, board)
        if next_name == "halt":
            board.save()
            return False
        if log.exhausted():
            break

        if not board.goal:
            board.save()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        if next_name in board.disabled_agents or next_name not in AGENTS:
            board.save()
            time.sleep(DELAY_BETWEEN_CYCLES)
            continue

        llm_result = _emit_agent(AGENTS[next_name], board)
        if llm_result == "done":
            board.save()
            return True

        board.save()
        time.sleep(DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count()})
    board.save()
    return False


def _emit_agent(agent: Any, board: Board) -> str:
    result: AgentResult = agent.run(board)
    board.apply(result.writes)
    if result.event_phase:
        log.emit(result.event_phase, result.event_data)
    if result.next_agent == "halt":
        log.emit("halt", {"stagnation": board.stagnation_score, "events": log.count()})
        return "halt"
    if result.next_agent == "done":
        log.emit("complete", {"goal": board.goal, "events": log.count()})
        return "done"
    return result.next_agent


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
