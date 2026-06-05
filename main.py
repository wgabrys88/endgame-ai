from __future__ import annotations
import argparse, json, signal, sys, time, types

from config import DELAY_STARTUP, BASE_DIR
from state import Blackboard
from llm import set_backend
from orchestrator import run
from persistence import save_snapshot, load_snapshot, append_to_evolution_ledger
from log import open_log, log, close_log

_interrupted = False


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(130)
    _interrupted = True
    sys.stderr.write("\n[endgame-ai] Ctrl+C — finishing current step, then exit (no --resume unless you intend it).\n")
    sys.stderr.flush()


def main() -> None:
    global _interrupted

    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="?", default=None)
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--agent-id", default="main")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    try:
        import ctypes
        ctypes.WinDLL("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (OSError, AttributeError):
        pass

    set_backend(args.backend)

    board = Blackboard()
    board.agent_id = args.agent_id

    if args.resume:
        snap = load_snapshot()
        if snap:
            board.load_from_snapshot(snap)
        elif not args.goal:
            print("No snapshot found and no goal provided.")
            return

    if args.goal:
        board.goal = args.goal
        board.original_goal = args.goal

    if not board.goal:
        print("usage: python main.py 'goal' [--backend lmstudio|acp] [--resume]")
        return

    time.sleep(DELAY_STARTUP)

    lessons_path = BASE_DIR / "lessons.json"
    if not lessons_path.exists():
        lessons_path.write_text(json.dumps({"insights": []}, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = open_log(board.agent_id)
    log(0, "run.start", f"goal={board.goal} backend={args.backend} agent={board.agent_id} log={log_path}")

    success = run(board, interrupted=lambda: _interrupted)

    log(board.iteration, "run.end", f"success={success} stagnation={board.stagnation_score:.2f} iterations={board.iteration}")
    save_snapshot(board.get_persistable_snapshot())

    summary = (
        f"goal={board.goal} | iterations={board.iteration} | "
        f"stagnation={board.stagnation_score:.2f} | done={board.done_claimed}"
    )
    if board.done_evidence:
        summary += f" | evidence={board.done_evidence}"
    append_to_evolution_ledger(summary, source_run=board.agent_id)

    close_log()
    if _interrupted:
        sys.stderr.write("[endgame-ai] Stopped by user. Start a new goal without --resume for a clean run.\n")
        sys.exit(130)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
