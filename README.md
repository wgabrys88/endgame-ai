# endgame-ai

Event-driven desktop automation organism. Pure Python 3.13 on Windows 11. Zero third-party dependencies. Raw ctypes for Win32 and UI Automation.

The system observes the visible desktop, projects bounded context to an LLM, executes typed actions, and verifies completion from evidence. It is provider-agnostic: ACP (Claude via kiro-cli) or LM Studio as the model backend.

## Quick Start

```powershell
python main.py "Open Notepad via Win+R and type hello world" --backend acp
python main.py "Open Notepad via Win+R and type hello world" --backend lmstudio
python main.py --resume --backend acp
python main.py "your goal" --backend acp --wt-launch
```

Run as Administrator. UIA requires elevation.

## How It Works

Each iteration:

1. **Observe** the desktop through probe-first hover sampling + conditional UIA tree walk.
2. **Decide** the cheapest useful next step:
   - Continue the actor if a real subtask is still producing evidence.
   - Call planner only when evidence changes, an action repeats, or a route blocks.
   - Verify only when planner or actor claims done.
   - Reflect only on real failure/repetition evidence.
3. **Execute** typed actions (click, write, hotkey, focus, etc.).
4. **Record** events, save state, sleep briefly.

The system does NOT run a static planner→actor→verifier→reflector pipeline. The scheduler picks the role that has work to do based on blackboard signals.

## Roles

- **Planner**: decides next step, maintains checklist, gives actor one subtask.
- **Actor**: maps subtask to 0-5 typed actions; emits DONE when subtask is satisfied.
- **Verifier**: confirms or denies done claims from concrete evidence.
- **Reflector**: extracts one reusable lesson when stagnation and failure evidence justify it.

Prompts: `prompts/*.txt`. Schemas: `schemas/*.json`.

## Control Laws

Three mathematical pipelines in `state.py` govern scheduling intensity:

- **Lorenz attractor**: chaos-driven exploration pressure.
- **PID controller**: temporal stagnation memory with anti-windup.
- **Jacobian vector**: per-step sensitivity for replan pressure.

These are toggleable via `config.py` flags (`PIPELINE_LORENZ`, `PIPELINE_PID`, `PIPELINE_JACOBIAN`).

## Actions

Actor verbs: `click`, `write`, `press`, `hotkey`, `scroll`, `wait`, `focus`, `read_file`, `write_file`, `spawn_agent`, `cmd`.

- `cmd` runs Bash through `wsl.exe bash -lc <command>`.
- `spawn_agent` creates a child process with its own goal and reports back via events.
- GUI actions preferred over cmd unless the goal explicitly requires shell work.

## Observation

`observer.py`:
- Enumerates visible windows.
- Probe-samples UI elements through hover regions.
- Falls back to UIA tree walk when needed.
- Renders compact screen context with element IDs for the actor.
- Computes content hash and semantic hash for stagnation detection.

## Backends

**ACP**: Claude via kiro-cli in WSL2. Implemented in `acp_client.py`. Polls `comms/stop.txt` while waiting. Raises explicit errors on setup failure.

**LM Studio**: local LLM at `http://localhost:1234`. OpenAI-compatible API.

## Files

```
main.py           CLI entry point and lifecycle
orchestrator.py   Event scheduler and control loop
state.py          Blackboard, control laws, context builders
config.py         All constants and context policy
observer.py       Desktop observation (probe + UIA)
actions.py        Typed verb execution
dispatch.py       Prompt/schema loading and JSON extraction
llm.py            Backend selection and request logging
acp_client.py     ACP JSON-RPC client over WSL
log.py            Append-only event logging
tui.py            Live terminal dashboard
lessons.py        Lesson persistence
self_evolution.py Reflection pipeline (lesson extraction, optional prompt mutation)
persistence.py    Locked state/event persistence
artifacts.py      Externalized runtime artifact chunks
event_schema.py   Blackboard event records
goal_wrapper.py   Deterministic goal wrapping
sixel.py          Terminal graphics
stop_signal.py    Cooperative stop check
win32.py          Win32/UIA ctypes primitives
prompts/          Role prompts (mutable by reflection)
schemas/          JSON schemas (strict mode)
tests/            Deterministic regression tests
```

## Runtime Files (Ignored)

```
blackboard_events.txt    Append-only event stream (runtime truth)
blackboard_state.json    Blackboard snapshot (for resume)
log-<agent>-*.txt        Per-agent log
lessons.json             Learned lessons
evolution_ledger.json    Run summaries
runtime_artifacts/       Content-addressed artifact chunks
comms/                   Stop signal, screen lock, inbox
```

## Git Policy

Default-ignore-all with explicit unignore for source and docs. Runtime files never committed.

## Validation

Static:
```powershell
python -m compileall -q .
python -m pyright
```

Live regression (60-second bounded):
```powershell
python main.py "Open Notepad via Win+R, replace all text with exactly: SCIENCE EVENT DRIVEN SAMPLE. Use GUI actions only. Do not use cmd. Claim done only when that exact text is visible in Notepad." --backend acp --tui-mode json
```

## Cleanup

```powershell
$root=(Resolve-Path .).Path
$runtimeNames=@('blackboard_state.json','blackboard_state.lock','blackboard_state.tmp','blackboard_events.txt','blackboard_events.jsonl','evolution_ledger.json','lessons.json')
$targets=@()
$targets += Get-ChildItem -LiteralPath $root -Force -File | Where-Object { $_.Name -like 'log-*' -or $_.Name -like 'validation-*' -or $runtimeNames -contains $_.Name }
$targets += Get-ChildItem -LiteralPath $root -Force -Directory | Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq 'runtime_artifacts' }
$commsPath=Join-Path $root 'comms'
if (Test-Path $commsPath) { Get-ChildItem $commsPath -Force | Remove-Item -Recurse -Force }
foreach ($item in $targets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
```

## Handoff

Read `AGENTS.md` before assigning this repository to any AI coding provider.
