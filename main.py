"""Entry point for a single persona process."""
from __future__ import annotations
import argparse
import json
import os
import signal
import sys
import time
import types
from typing import Any

import config
import log
from llm import set_backend
from engine import run

_interrupted = False


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(130)
    _interrupted = True


def main() -> None:
    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="?", default="")
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--event-budget", type=int, default=config.EVENT_BUDGET)
    parser.add_argument("--events-path", type=str, default=None)
    parser.add_argument("--model-profile", type=str, default=None)
    parser.add_argument("--priority", type=int, default=config.PRI_MAINTENANCE)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)

    if args.model_profile:
        config.apply_model_profile(args.model_profile)
    set_backend(args.backend)
    log.init(args.events_path, args.event_budget)

    # Load personality goal if not given directly
    goal = args.goal
    if not goal:
        personality = os.environ.get("ENDGAME_PERSONALITY", "")
        if personality:
            pfile = config.PROMPTS_DIR / "personalities" / f"{personality}.txt"
            if pfile.exists():
                goal = pfile.read_text(encoding="utf-8").strip()

    board: dict[str, Any] = {
        "goal": goal,
        "priority": args.priority,
        "plan": [],
        "history": [],
        "completed": [],
        "fissions": 0,
        "_last_msg_id": 0,
    }

    log.emit("start", {"goal": goal[:120], "personality": os.environ.get("ENDGAME_PERSONALITY", ""),
                        "profile": config.active_model_profile()})

    run(board, lambda: _interrupted)

    log.emit("stop", {"fissions": board.get("fissions", 0)})


if __name__ == "__main__":
    main()
