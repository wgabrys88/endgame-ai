from __future__ import annotations
import argparse
import signal
import time
import sys
import types
from typing import Any

from config import PROCESS_DPI_AWARENESS_CONTEXT, SIGINT_EXIT_CODE
from llm import set_backend, close_backend
from engine import run
import log
import config

_interrupted = False

GOAL_MUTABLE = True


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(SIGINT_EXIT_CODE)
    _interrupted = True
    sys.stderr.write("\n[endgame-ai] Ctrl+C — finishing current cycle.\n")


def set_goal(board: dict, new_goal: str) -> bool:
    global GOAL_MUTABLE
    if GOAL_MUTABLE:
        board["goal"] = new_goal
        return True
    return False


def main() -> None:
    global _interrupted, GOAL_MUTABLE

    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="?", default=None)
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--event-budget", type=int, default=None)
    args = parser.parse_args()

    if args.goal is None:
        args.goal = ""

    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        import ctypes
        ctypes.WinDLL("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(PROCESS_DPI_AWARENESS_CONTEXT))
    except (OSError, AttributeError):
        pass

    if args.event_budget is not None:
        config.EVENT_BUDGET = args.event_budget
    set_backend(args.backend)

    log.init(config.EVENT_BUDGET)

    GOAL_MUTABLE = True

    board: dict[str, Any] = {
        "goal": args.goal,
        "plan": [],
        "done_when": "",
        "history": [],
        "completed": [],
        "power": 0.0,
        "start_time": time.time(),
        "screen": "",
        "screen_elements": {},
        "desktop_summary": "",
        "focused_window": "",
        "consecutive_failures": 0,
        "stagnation": 0.0,
        "progress_history": [],
        "lorenz_x": 8.0,
        "lorenz_y": 8.0,
        "lorenz_z": 27.0,
        "energy": 1.0,
        "wing_crossed": False,
        "pid_output": 0.0,
        "pid_integral": 0.0,
        "pid_prev": 0.0,
        "last_reflect_time": 0.0,
        "reflect_trigger": {},
        "behavioral_stagnation": 0.0,
        "math_trace": [],
    }

    try:
        success = run(board, interrupted=lambda: _interrupted)
    finally:
        close_backend()
        log.close()

    sys.exit(0)


if __name__ == "__main__":
    main()
