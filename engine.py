"""Engine — runs the agent pipeline with priority interrupts."""
from __future__ import annotations
import json
import time
from typing import Any, Callable

from agents import SchedulerAgent, PlannerAgent, ActorAgent, VerifierAgent, FissionJudgeAgent
import config
import comms
import log


AGENTS: dict[str, Any] = {
    "scheduler": SchedulerAgent(),
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "fission_judge": FissionJudgeAgent(),
}


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> None:
    """Main loop: work on goal, check bus for priority interrupts each cycle."""
    while not log.exhausted() and not interrupted():
        # --- Priority interrupt check ---
        _check_interrupt(board)

        # --- Pipeline ---
        scheduler = AGENTS["scheduler"]
        result = scheduler.run(board)
        nxt = (result or {}).get("next")
        if not nxt:
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        log.emit("schedule", {"next": nxt, "reason": result.get("data", {}).get("reason", "")})

        # Walk the pipeline chain
        while nxt and nxt in AGENTS and not interrupted():
            agent = AGENTS[nxt]
            result = agent.run(board)
            if result:
                phase = result.get("phase", nxt)
                log.emit(phase, result.get("data"))
                # Apply writes to board
                for k, v in (result.get("writes") or {}).items():
                    board[k] = v
                nxt = result.get("next")
            else:
                nxt = None
            # Check interrupt between pipeline stages
            if _check_interrupt(board):
                break

        time.sleep(config.DELAY_BETWEEN_CYCLES)


def _check_interrupt(board: dict[str, Any]) -> bool:
    """Check bus for priority messages. Returns True if goal was switched."""
    try:
        comms.drain_inject()
    except Exception:
        pass
    me = comms.agent_id()
    inbox = comms.pending_for(me, 3)
    current_pri = board.get("priority", config.PRI_MAINTENANCE)

    for msg in inbox:
        msg_id = int(msg.get("id", 0))
        if msg_id <= board.get("_last_msg_id", 0):
            continue
        # Determine priority of incoming message
        msg_pri = _msg_priority(msg)
        if msg_pri > current_pri:
            # INTERRUPT: switch goal
            board["_last_msg_id"] = msg_id
            board["goal"] = str(msg.get("text", ""))
            board["priority"] = msg_pri
            board["plan"] = []
            board["history"] = []
            log.emit("interrupt", {"from": msg.get("from"), "pri": msg_pri, "text": str(msg.get("text", ""))[:120]})
            return True
        board["_last_msg_id"] = msg_id
    return False


def _msg_priority(msg: dict) -> int:
    """Determine priority from message metadata."""
    # Explicit priority in data
    data = msg.get("data") or {}
    if isinstance(data, dict) and "priority" in data:
        return int(data["priority"])
    # Human messages are always highest
    if str(msg.get("from", "")) == "human":
        return config.PRI_HUMAN
    # Requests from comms_operator are normal work
    if str(msg.get("kind", "")) == "request":
        return config.PRI_NORMAL
    return config.PRI_MAINTENANCE
