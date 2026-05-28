from __future__ import annotations
import argparse, json, signal, sys, time, types

from config import DELAY_STARTUP, MAX_CYCLES_DEFAULT, BASE_DIR, init_trace, close_trace
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
    print("\n[INTERRUPTED] Ctrl+C received. Finishing current cycle...")


def main() -> None:
    global _interrupted

    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="?", default=None)
    parser.add_argument("--cycles", type=int, default=MAX_CYCLES_DEFAULT)
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--agent-id", default="main")
    parser.add_argument("--distill", action="store_true")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)
    sys.stdout.reconfigure(encoding="utf-8")

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
            print(f"[RESUME] Loaded snapshot: goal='{board.goal}' cycle={board.cycle}")
        elif not args.goal:
            print("No snapshot found and no goal provided.")
            return

    if args.goal:
        board.goal = args.goal
        board.original_goal = args.goal

    if args.distill:
        board.goal = (
            "DISTILLATION: Analyze recent execution history. Synthesize evolutionary trajectory. "
            "Output refined long-term goal and evolution_ledger entries."
        )
        board.original_goal = board.goal
        print("[LIVING] Autonomous distillation mode engaged.")

    if not board.goal:
        print("usage: python main.py 'goal' [--cycles N] [--backend lmstudio|acp] [--resume] [--watch]")
        return

    print(f"[ENDGAME] goal='{board.goal}' cycles={args.cycles} backend={args.backend} agent={args.agent_id}")
    print(f"[STARTUP] Waiting {DELAY_STARTUP}s...")
    time.sleep(DELAY_STARTUP)

    lessons_path = BASE_DIR / "lessons.json"
    if not lessons_path.exists():
        lessons_path.write_text(json.dumps({"insights": [
            "Fresh run. Proceed with main goal.",
            "On repeated failures, use parallel agents instead of looping."
        ]}, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.watch:
        run_count = 0
        while not _interrupted:
            run_count += 1
            print(f"\n[WATCH] Run #{run_count} starting...")
            journal = create_execution_journal(BASE_DIR, board.goal)
            init_trace(journal.execution_id)

            success = run(board, journal, args.cycles,
                          interrupted=lambda: _interrupted)

            if success:
                journal.append("run.end", {"success": True}, ph="system")
            journal.close()

            save_snapshot(board.get_persistable_snapshot())
            _distill_end_of_run(board, journal)
            close_trace()

            if _interrupted:
                break

            board.cycle = 0
            board.consecutive_failures = 0
            board.done_claimed = False
            print(f"[WATCH] Run #{run_count} complete. Checking inbox for new goal...")
            time.sleep(3)

            inbox = board.poll_inbox()
            for cmd in inbox:
                if cmd.get("type") == "goal_rewrite":
                    board.rewrite_goal(cmd["payload"])
                    print(f"[WATCH] New goal from inbox: {board.goal}")
                elif cmd.get("type") == "kill":
                    _interrupted = True

            if not _interrupted and not board.goal:
                print("[WATCH] No goal. Waiting for inbox...")
                while not _interrupted:
                    time.sleep(5)
                    inbox = board.poll_inbox()
                    for cmd in inbox:
                        if cmd.get("type") == "goal_rewrite":
                            board.rewrite_goal(cmd["payload"])
                            print(f"[WATCH] New goal from inbox: {board.goal}")
                        elif cmd.get("type") == "kill":
                            _interrupted = True
                    if board.goal != board.original_goal or _interrupted:
                        break
    else:
        journal = create_execution_journal(BASE_DIR, board.goal)
        init_trace(journal.execution_id)

        success = run(board, journal, args.cycles,
                      interrupted=lambda: _interrupted)

        if success:
            journal.append("run.end", {"success": True}, ph="system")
        journal.close()

        save_snapshot(board.get_persistable_snapshot())
        _distill_end_of_run(board, journal)
        close_trace()

        sys.exit(0 if success else 1)


def _distill_end_of_run(board: Blackboard, journal) -> None:
    summary_parts = [
        f"goal={board.goal}",
        f"cycles_completed={board.cycle}",
        f"final_chaos={board.chaos_level:.2f}",
        f"final_failures={board.consecutive_failures}",
        f"done_claimed={board.done_claimed}",
    ]
    if board.done_evidence:
        summary_parts.append(f"evidence={board.done_evidence}")
    if board.history:
        last_3 = board.history[-3:]
        for h in last_3:
            summary_parts.append(f"  {h['verb']}->{'ok' if h['success'] else 'FAIL'}")

    entry = " | ".join(summary_parts)
    append_to_evolution_ledger(entry, source_run=getattr(journal, "execution_id", "unknown"))


if __name__ == "__main__":
    main()