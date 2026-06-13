"""Entry point for a single agent fuel rod."""
from __future__ import annotations
import argparse
import json
import signal
import time
import sys
import types
from typing import Any

from config import PROCESS_DPI_AWARENESS_CONTEXT, RESPAWN_PATH, SIGINT_EXIT_CODE
from llm import set_backend, close_backend
from engine import run
import log
import config

_interrupted = False


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(SIGINT_EXIT_CODE)
    _interrupted = True


def main() -> None:
    global _interrupted
    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="?", default="")
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--event-budget", type=int, default=None)
    parser.add_argument("--events-path", type=str, default=None)
    parser.add_argument("--model-profile", type=str, default=None,
                        help="Model profile to apply (e.g. nemotron, gemma)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        import ctypes
        ctypes.WinDLL("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(PROCESS_DPI_AWARENESS_CONTEXT))
    except (OSError, AttributeError):
        pass

    if args.event_budget is not None:
        config.EVENT_BUDGET = args.event_budget
    if args.events_path:
        config.EVENTS_PATH = config.BASE_DIR / args.events_path
    if args.model_profile:
        activated, _ = config.apply_model_profile(args.model_profile)
        if activated:
            print(f"  [profile] {activated}")
    set_backend(args.backend)
    log.init(config.EVENT_BUDGET)

    if not args.events_path:
        config.GOAL_PATH.write_text(args.goal, encoding="utf-8")
    RESPAWN_PATH.write_text(json.dumps({"goal": args.goal, "backend": args.backend, "budget": config.EVENT_BUDGET}), encoding="utf-8")

    board: dict[str, Any] = {
        "goal": args.goal, "plan": [], "done_when": "", "history": [], "completed": [],
        "power": 0.0, "start_time": time.time(), "screen": "", "screen_elements": {},
        "desktop_summary": "", "focused_window": "", "consecutive_failures": 0,
        "stagnation": 0.0, "activity_events": 0, "progress_history": [],
        "lorenz_x": 8.0, "lorenz_y": 8.0, "lorenz_z": 27.0, "energy": 1.0,
        "wing_crossed": False, "pid_output": 0.0, "pid_integral": 0.0, "pid_prev": 0.0,
        "last_reflect_time": 0.0, "last_mutator_at": 0.0,
        "reflect_trigger": {}, "mutator_trigger": {}, "math_trace": [],
        "denied_goals": [],
    }

    try:
        run(board, interrupted=lambda: _interrupted)
    finally:
        close_backend()
        log.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
