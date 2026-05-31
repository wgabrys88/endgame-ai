from __future__ import annotations
import argparse, json, signal, sys, time, types

from config import DELAY_STARTUP, BASE_DIR, ENABLE_FILE_TRACING, init_trace, close_trace
from state import Blackboard, EventBus
from journal import create_execution_journal
from llm import set_backend
from orchestrator import run
from persistence import save_snapshot, load_snapshot, append_to_evolution_ledger

_interrupted = False


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(1)
    _interrupted = True
    print("\n[INTERRUPTED] Ctrl+C received. Finishing current iteration...")


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
    board.events = EventBus()
    board.agent_id = args.agent_id

    if args.resume:
        snap = load_snapshot()
        if snap:
            board.load_from_snapshot(snap)
            print(f"[RESUME] Loaded snapshot: goal='{board.goal}' iteration={board.iteration}")
        elif not args.goal:
            print("No snapshot found and no goal provided.")
            return

    if args.goal:
        board.goal = args.goal
        board.original_goal = args.goal

    if not board.goal:
        print("usage: python main.py 'goal' [--backend lmstudio|acp] [--resume]")
        return

    print(f"[ENDGAME] goal='{board.goal}' backend={args.backend} agent={args.agent_id}")
    print(f"[STARTUP] Waiting {DELAY_STARTUP}s...")
    time.sleep(DELAY_STARTUP)

    lessons_path = BASE_DIR / "lessons.json"
    if not lessons_path.exists():
        lessons_path.write_text(json.dumps({"insights": [
            "Fresh run. Proceed with main goal.",
            "On repeated failures, use parallel agents instead of looping.",
            "For file operations, prefer cmd verb with PowerShell over GUI navigation."
        ]}, indent=2, ensure_ascii=False), encoding="utf-8")

    journal = create_execution_journal(BASE_DIR, board.goal)
    if ENABLE_FILE_TRACING:
        init_trace(journal.execution_id)

    success = run(board, journal, interrupted=lambda: _interrupted)

    if success:
        journal.append("run.end", {"success": True}, ph="system")
    journal.close()

    save_snapshot(board.get_persistable_snapshot())
    _distill_end_of_run(board, journal)
    close_trace()

    sys.exit(0 if success else 1)


def _distill_end_of_run(board: Blackboard, journal: object) -> None:
    from config import CONTEXT_HISTORY_LIMIT
    summary_parts = [
        f"goal={board.goal}",
        f"iterations={board.iteration}",
        f"final_chaos={board.chaos_level:.2f}",
        f"final_failures={board.consecutive_failures}",
        f"done_claimed={board.done_claimed}",
    ]
    if board.done_evidence:
        summary_parts.append(f"evidence={board.done_evidence}")
    if board.history:
        for h in board.history[-CONTEXT_HISTORY_LIMIT:]:
            summary_parts.append(f"  {h['verb']}->{'ok' if h['success'] else 'FAIL'}")

    entry = " | ".join(summary_parts)
    append_to_evolution_ledger(entry, source_run=getattr(journal, "execution_id", "unknown"))


if __name__ == "__main__":
    main()
