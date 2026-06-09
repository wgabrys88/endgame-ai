from __future__ import annotations
import argparse
import signal
import sys
import types

from config import PROCESS_DPI_AWARENESS_CONTEXT, SIGINT_EXIT_CODE
from board import Board
from llm import set_backend, close_backend
from orchestrator import run
import log
import config

_interrupted = False


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(SIGINT_EXIT_CODE)
    _interrupted = True
    sys.stderr.write("\n[endgame-ai] Ctrl+C — finishing current cycle.\n")


def main() -> None:
    global _interrupted

    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="?", default=None)
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--event-budget", type=int, default=None)
    args = parser.parse_args()

    if not args.goal:
        print("usage: python main.py 'goal' [--backend lmstudio|acp] [--event-budget N]")
        return

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

    board = Board()
    board.goal = args.goal

    try:
        success = run(board, interrupted=lambda: _interrupted)
    finally:
        close_backend()
        log.close()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
