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
    parser.add_argument("--persona", type=str, default=None)
    parser.add_argument("--slot", type=int, default=None)
    parser.add_argument("--priority", type=int, default=config.PRI_MAINTENANCE)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)

    if args.persona:
        os.environ["ENDGAME_PERSONALITY"] = args.persona.strip()
    if args.slot is not None:
        os.environ["ENDGAME_SLOT"] = str(args.slot)
    if args.model_profile:
        config.apply_model_profile(args.model_profile)
    set_backend(args.backend)
    log.init(args.events_path, args.event_budget)

    personality = config.Personality.from_env(args.goal)
    goal = personality.mission
    if not goal:
        import comms
        goal = comms.colony_goal_text()

    board: dict[str, Any] = {
        "goal": goal,
        "personality": personality.name,
        "slot": personality.slot,
        "_personality_mission": personality.mission[:200],
        "priority": args.priority,
        "plan": [],
        "history": [],
        "completed": [],
        "fissions": 0,
        "_last_msg_id": 0,
    }

    log.emit("start", {"goal": goal[:120], "personality": personality.name, "slot": personality.slot,
                        "profile": config.active_model_profile(),
                        "run_mode": os.environ.get("ENDGAME_RUN_MODE", "single"),
                        "ablation_run_id": os.environ.get("ENDGAME_ABLATION_RUN_ID", "")})

    run(board, lambda: _interrupted)

    log.emit("stop", {"fissions": board.get("fissions", 0)})


if __name__ == "__main__":
    main()
