# endgame-ai

Event-driven Windows desktop automation organism. Pure Python 3.13, zero dependencies, raw ctypes.

## Architecture

```
goal → [observe → plan → act] × N → verify → done
         │                              │
         └── Lorenz/PID math ──────────┘
              (chaos fork, reflection gate)
```

The system is a pipeline of **events**. Each event is one line in `events.jsonl`.
The **event budget** (default 100) is the only execution boundary.

## Usage

```
python main.py "open notepad and type hello world" --backend acp --event-budget 50
python main.py "open chrome" --backend lmstudio
python analyze_run.py events.jsonl
```

## Files

| File | Lines | Purpose |
|------|-------|---------|
| main.py | 65 | CLI entry point |
| orchestrator.py | 236 | Event pipeline: observe→plan→act→verify |
| state.py | 197 | Blackboard + Lorenz/PID/stagnation math |
| observer.py | 675 | Win32 UIA screen capture |
| actions.py | 208 | GUI verb execution |
| dispatch.py | 93 | LLM role dispatch + JSON extraction |
| llm.py | 136 | Backend transport (LM Studio / ACP) |
| acp_client.py | 252 | Kiro ACP JSON-RPC client |
| win32.py | 319 | Raw ctypes Win32 bindings |
| config.py | 207 | All constants in one flat file |
| log.py | 56 | JSONL event emitter + budget counter |
| analyze_run.py | 72 | Post-run metrics |

## Math Pipeline

- **Lorenz attractor**: When stagnation causes a wing crossing (x changes sign), the plan is cleared and a DIVERGE signal forces trying a different approach.
- **PID controller**: Accumulates error from failures, gates reflection calls.
- **Stagnation score**: Weighted combination of failures + repetition + screen stagnation.

## Event Budget

Every `log.emit()` call = 1 event. Budget exhausted → graceful stop.
This creates evolutionary pressure: accomplish MORE in FEWER events.

Reflection is suppressed when >75% budget consumed (preserve events for action).
Budget remaining is shown to the planner when <50% remains.
