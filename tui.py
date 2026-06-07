from __future__ import annotations

import sys
from typing import Any, Protocol, cast

from config import TUI_WRITE_CHUNK_SIZE, ZERO_INT


class _BinaryStdout(Protocol):
    def write(self, data: bytes) -> int:
        ...

    def flush(self) -> None:
        ...


class _BufferedStdout(Protocol):
    buffer: _BinaryStdout


def event(record: dict[str, Any], line: str) -> None:
    data = (line + "\n").encode("utf-8", errors="surrogatepass")
    stream = cast(_BufferedStdout, sys.stdout).buffer
    for start in range(ZERO_INT, len(data), TUI_WRITE_CHUNK_SIZE):
        stream.write(data[start:start + TUI_WRITE_CHUNK_SIZE])
    stream.flush()


def poll_commands() -> list[str]:
    return []


def enter() -> None:
    sys.stdout.flush()


def exit() -> None:
    sys.stdout.flush()


def render(board: Any, stagnation_history: list[float], last_event: str = "") -> None:
    if last_event.startswith("COORD:"):
        return
    from log import log
    log(
        board.iteration,
        "tui.render",
        "live state projection",
        {
            "last_event": last_event,
            "agent_id": board.agent_id,
            "mode": board.mode,
            "screen_valid": board.screen_valid,
            "focused_window": board.focused_window,
            "stagnation_score": board.stagnation_score,
            "pid_output": board.pid_output,
            "pid_integral": board.pid_integral,
            "pid_slope": board.pid_slope,
            "repetition_score": board.repetition_score,
            "screen_stagnation": board.screen_stagnation,
            "consecutive_failures": board.consecutive_failures,
            "attractor_energy": board.attractor_energy,
            "plan_steps": board.plan_steps,
            "plan_step_index": board.plan_step_index,
            "last_instruction": board.last_instruction,
            "last_verb": board.last_verb,
            "last_success": board.last_success,
            "last_observation": board.last_observation,
            "actor_observe": board.actor_observe,
            "actor_conclusion": board.actor_conclusion,
            "last_plan_because": board.last_plan_because,
            "goal": board.goal,
            "stagnation_history": stagnation_history,
            "children": board.children,
        },
    )
