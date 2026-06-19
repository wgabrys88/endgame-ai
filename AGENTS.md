# AGENTS.md

Critical operational knowledge for any AI or agent working with endgame-ai.

## How to Run

Use the direct Python entry point:

```powershell
python tui.py "your goal text here"
python tui.py "your goal text here" --no-desktop     # disable desktop/GUI observation
```

The TUI starts an interactive session. The goal is set automatically on launch.

## How to Stop

- Inside the TUI: press `q`
- From keyboard: `Ctrl+C`
- The console is automatically restored on exit.

If the process is running in the background (PowerShell job or external process), terminate it using the job/process management commands of your environment.

## PowerShell Navigation Tips

- Use `cd` to change into the project directory before running.
- Use `Get-ChildItem` (or `ls`) and `Get-Content` (or `cat`) for inspection.
- Background jobs: `Start-Job`, `Stop-Job`, `Get-Job`, `Receive-Job`.
- To kill a stuck process: `Stop-Process` or `taskkill`.

## Grok Build / TUI Workflow (Important)

When using Grok Build (this TUI environment) to develop endgame-ai:

- Always ensure you are on the correct branch (`codex-unify-bus` or the active development branch) before making changes.
- Never work in a **detached HEAD** state. If you find yourself in one, switch back to the branch immediately (`git checkout <branch>`).
- Use worktrees only when you intentionally want an isolated copy. The main worktree should stay on the development branch.
- After any session that involves git operations, verify the current branch and HEAD state before committing.
- Keep `AGENTS.md` in sync between the manager and any student instances.

## Parallel Execution & Monitoring

When running multiple endgame-ai instances at the same time:

- Launch each instance in its own directory using `python tui.py "goal"`.
- Use background jobs or subprocesses to run them in parallel.
- Each instance writes its own logs into its local `logs/` folder (timestamped `.txt` files).
- To monitor progress, periodically read the newest log file from each instance’s `logs/` directory.
- The outer controller is responsible for starting, observing, and terminating the instances.

Keep this file updated as operational knowledge evolves.