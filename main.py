from __future__ import annotations
from config import ZERO_INT, ONE_INT, TWO_INT
import argparse, json, signal, sys, time, traceback, types
from typing import Protocol, cast

from config import DELAY_STARTUP, BASE_DIR, SIGINT_EXIT_CODE, PROCESS_DPI_AWARENESS_CONTEXT
from state import Blackboard
from llm import set_backend, close_backend
from goal_wrapper import extract_human_goal, wrap_goal
from orchestrator import run
from persistence import save_snapshot, load_snapshot, append_to_evolution_ledger
from log import open_log, log, close_log, set_tui_hook
import tui

_interrupted = False


class _StdoutReconfigure(Protocol):
    def reconfigure(self, *, encoding: str) -> None:
        ...


def _handle_sigint(sig: int, frame: types.FrameType | None) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(SIGINT_EXIT_CODE)
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
    parser.add_argument("--tui-mode", choices=["auto", "visual", "json"], default="auto")
    parser.add_argument("--wt-launch", action="store_true", help="Open a Windows Terminal tab running this goal with visual TUI")
    parser.add_argument("--enable-prompt-mutations", dest="prompt_mutations_enabled", action="store_true", default=False, help="Allow guarded one-line prompt mutations after enough lessons accumulate")
    parser.add_argument("--disable-prompt-mutations", dest="prompt_mutations_enabled", action="store_false", help="Keep lessons extraction enabled but disable prompt mutations")
    args = parser.parse_args()

    if args.wt_launch:
        if not args.goal:
            print("usage: python main.py 'goal' --wt-launch")
            return
        pid = tui.launch_windows_terminal_preview(args.goal, args.backend, str(BASE_DIR))
        if pid <= ZERO_INT:
            print("wt.exe not found; run from Windows Terminal or pass --tui-mode visual")
            return
        print(f"launched Windows Terminal tab pid={pid}")
        return

    tui.set_mode(args.tui_mode)

    signal.signal(signal.SIGINT, _handle_sigint)
    cast(_StdoutReconfigure, sys.stdout).reconfigure(encoding="utf-8")

    try:
        import ctypes
        ctypes.WinDLL("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(PROCESS_DPI_AWARENESS_CONTEXT))
    except (OSError, AttributeError):
        pass

    set_backend(args.backend)
    import config
    config.PROMPT_MUTATIONS_ENABLED = bool(args.prompt_mutations_enabled)

    board = Blackboard()
    board.agent_id = args.agent_id

    if args.resume:
        snap = load_snapshot(args.agent_id)
        if snap:
            board.load_from_snapshot(snap)
        elif not args.goal:
            print("No snapshot found and no goal provided.")
            return

    if args.goal:
        board.goal = wrap_goal(args.goal)
        board.original_goal = extract_human_goal(args.goal)

    if not board.goal:
        print("usage: python main.py 'goal' [--backend lmstudio|acp] [--resume]")
        return

    time.sleep(DELAY_STARTUP)

    lessons_path = BASE_DIR / "lessons.json"
    if not lessons_path.exists():
        lessons_path.write_text(json.dumps({"insights": []}, indent=TWO_INT, ensure_ascii=False), encoding="utf-8")

    log_path = open_log(board.agent_id)
    tui_enabled = board.agent_id == "main"
    if tui_enabled:
        set_tui_hook(tui.event)
        tui.enter()
    success = False
    try:
        log(ZERO_INT, "run.start", "run started", {"goal": board.goal, "backend": args.backend, "agent_id": board.agent_id, "log_path": log_path, "prompt_mutations_enabled": args.prompt_mutations_enabled})
        success = run(board, interrupted=lambda: _interrupted, prompt_mutations_enabled=args.prompt_mutations_enabled)
        log(board.iteration, "run.end", "run ended", {"success": success, "stagnation_score": board.stagnation_score, "iterations": board.iteration, "done_claimed": board.done_claimed, "done_evidence": board.done_evidence})
        save_snapshot(board.get_persistable_snapshot())

        summary = (
            f"goal={board.goal} | iterations={board.iteration} | "
            f"stagnation={board.stagnation_score:.2f} | done={board.done_claimed}"
        )
        if board.done_evidence:
            summary += f" | evidence={board.done_evidence}"
        append_to_evolution_ledger(summary, source_run=board.agent_id)
    except Exception as e:
        log(board.iteration, "run.error", "run failed", {"exception_type": type(e).__name__, "exception": str(e), "traceback": traceback.format_exc()})
        raise
    finally:
        terminated = board.terminate_running_children()
        if terminated:
            log(board.iteration, "child.terminate", "terminated child processes before exit", {"children": terminated})
        close_backend()
        if tui_enabled:
            tui.exit()
        set_tui_hook(None)
        close_log()
    if _interrupted:
        sys.stderr.write("[endgame-ai] Stopped by user. Start a new goal without --resume for a clean run.\n")
        sys.exit(SIGINT_EXIT_CODE)
    sys.exit(ZERO_INT if success else ONE_INT)


if __name__ == "__main__":
    main()
