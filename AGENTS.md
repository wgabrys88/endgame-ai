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

## Repository & Workflow Policy (Critical)

- Always work exclusively in the single main directory `C:\Users\ewojgab\Downloads\endgame-ai` on branch `codex-unify-bus`.
- **Never create or use git worktrees.** They force detached HEAD states and branch checkout conflicts. The main checkout must remain on the active development branch at all times.
- After any git operation, immediately run `git status` and `git branch --show-current` and confirm you are on `codex-unify-bus` (not detached).
- Before every commit or push, enforce the essential-files-only rule: only the 7 core .py modules, 3 .md docs, prompts/, LICENSE, and git control files may remain. Delete all _test_*.py, __pycache__/, and logs/ first.
- Keep `AGENTS.md` and `MANAGER.md` in the manager repo only.

## Parallel Execution & Monitoring

When running multiple endgame-ai instances at the same time:

- Launch each instance in its own directory using `python tui.py "goal"`.
- Use background jobs or subprocesses to run them in parallel.
- Each instance writes its own logs into its local `logs/` folder (timestamped `.txt` files).
- To monitor progress, periodically read the newest log file from each instance’s `logs/` directory.
- The outer controller is responsible for starting, observing, and terminating the instances.

## Launching Instances with Complex Goals

When starting an instance with a long or complex goal:

- Use this reliable pattern:
  ```powershell
  $job = Start-Job -ScriptBlock { cd "path\to\instance"; python tui.py "long goal here" 2>&1 | Out-File "$env:TEMP\name.log" }; Start-Sleep 20; Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -ErrorAction SilentlyContinue
  ```
- The `Start-Sleep` + self-kill inside the job ensures the TUI has time to initialize and begin writing logs even with complex goals.
- Always verify logs appear in the instance’s `logs/` directory after launch.

## Session Handoff & Bootstrap

Any new AI coding agent (Grok, Claude, Cursor, etc.) must be able to resume with zero prior context.

### Bootstrap Prompt (copy and paste verbatim after starting a fresh session)

```
You are an AI coding agent resuming development of endgame-ai.

Overall objective: Build a closed self-evolution loop in which one endgame-ai instance (Manager) can fully observe, launch, monitor, and iteratively improve a completely independent second instance (Student) using only desktop observation and actions — exactly the same interface the agent uses to control any Windows application. No shared files, no direct process communication; everything happens through the Windows desktop.

Current environment:
- Windows 11 + PowerShell
- Single main repository: C:\Users\ewojgab\Downloads\endgame-ai on branch codex-unify-bus
- Local LM Studio (4B-class Nemotron model recommended)
- Unified single-agent mode is the proven default
- Strict essential-files-only policy (no test scripts or runtime artifacts in the repo)
- MANAGER.md defines the Manager role and the temporary outer-controller pattern until the Manager can self-orchestrate

First actions (do these immediately):
1. git status && git branch --show-current
2. If not on codex-unify-bus: git checkout codex-unify-bus
3. Read in full: AGENTS.md, MANAGER.md, and the "Self-Evolution Architecture: Two Independent Instances" section of README.md
4. Confirm the working tree contains only essential files (7 core .py + 3 .md + prompts/ + LICENSE + git files)
5. Current active task: test launching the Manager with a goal that includes the absolute path to MANAGER.md so the Manager begins orchestrating the Student

Follow every rule in AGENTS.md and MANAGER.md exactly. Continue the manager-student evolution work.
```

Keep this file updated as operational knowledge evolves.