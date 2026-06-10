# endgame-ai

A self-sustaining Windows desktop automation reactor built in pure Python 3.13 with zero dependencies.

## What It Is

endgame-ai is a nuclear reactor analogy made real in software. Give it a goal and it plans, executes, verifies, and self-corrects. Give it nothing and it explores autonomously — each verified completion is a fission event that powers the next.

No frameworks. No pip install. Just Python and raw ctypes talking to Win32.

## How It Works

```
┌──────────────────────────────────────────────────────┐
│ MATH THREAD (3s heartbeat, independent)              │
│   Stagnation → Lorenz ODE → PID controller           │
│   Writes continuous signals to blackboard             │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ MAIN THREAD (reactive, event-driven)                 │
│   Scheduler reads board → invokes agent → board      │
│   mutates → scheduler reads again                    │
│                                                      │
│   Planner ──→ Actor ──→ Verifier ──→ ★ FISSION      │
│       ↑                      │                       │
│       └── denied ────────────┘                       │
│                                                      │
│   Reflector fires when PID pressure accumulates      │
└──────────────────────────────────────────────────────┘
```

### Reactor Concepts

| Reactor | endgame-ai |
|---------|-----------|
| Fuel rods | LLM agents (planner, actor) |
| Fission | Verifier-confirmed completion |
| Power | Verified completions / elapsed time |
| Prompt neutrons | Lorenz wing cross → immediate replan |
| Delayed neutrons | Reflector lessons → prompt mutations |
| Control rods | PID output → modulates reflection |
| Fuel depletion | Completed list prevents repeats |
| Chain reaction | Success → plan next → succeed → repeat |

### Headless-First

The system operates headless by default — no screen scanning, pure cmd/file operations. If a task needs GUI interaction, the planner creates a `gui_mode` file to enable Win32 screen scanning, then removes it when done.

## Usage

```
python main.py "your goal here" --backend acp --event-budget 50
python main.py --backend acp --event-budget 200        # goalless reactor mode
python tui.py "goal" --backend acp --event-budget 100  # with live dashboard
```

Backends:
- `acp` — Kiro CLI / Claude (recommended)
- `lmstudio` — local LM Studio server

## Architecture

```
main.py          Entry point, board initialization
engine.py        Reactor core: math thread + reactive main loop + fission logic
agents.py        All agents: math (3), scheduler, observer, planner, actor, verifier, reflector
config.py        All constants, no magic numbers elsewhere
llm.py           LLM backend abstraction (LM Studio / ACP)
actions.py       Verb execution (click, write, cmd, file ops)
observer.py      Win32 UI Automation tree scanner
win32.py         Raw ctypes Win32 bindings
log.py           Event logger (events.jsonl)
tui.py           Live terminal dashboard with Lorenz plot
acp_client.py    Kiro CLI ACP protocol client
```

## Requirements

- Windows 11
- Python 3.13
- Nothing else

## License

MIT
