# endgame-ai

A self-sustaining Windows desktop automation reactor. Pure Python 3.13, zero dependencies, raw ctypes Win32.

No agent framework does this. No LangChain, no CrewAI, no AutoGen. This system:
- Runs without a goal and discovers tasks autonomously
- Verifies its own completions (only truth counts as power)
- Self-evolves by mutating its own prompts at runtime
- Uses nuclear reactor math (Lorenz chaos + PID control) to regulate behavior
- Achieved autonomous fission: profiled its own environment without being told

## Architecture

```
          ┌─────────────────────────────────┐
          │  MATH THREAD (3s heartbeat)     │
          │  Stagnation → Lorenz → PID      │
          └────────────┬────────────────────┘
                       │ writes to blackboard
          ┌────────────▼────────────────────┐
          │  SCHEDULER (pure board state)   │
          │  Routes to correct agent        │
          └────────────┬────────────────────┘
                       │
    ┌──────────────────┼──────────────────────┐
    ▼                  ▼                      ▼
 PLANNER           ACTOR              REFLECTOR
 (fuel)         (execution)         (evolution)
    │                  │                      │
    └───────► VERIFIER ◄──────────────────────┘
              (fission = confirmed truth)
```

**Power** = verified completions / elapsed time. That's it. The only metric.

## What Makes This Different

| Other agents | endgame-ai |
|---|---|
| Need a goal to start | Explores autonomously when goalless |
| Trust their own output | Verifier cross-checks against original goal |
| Static prompts | Reflector mutates prompts at runtime (self-evolution) |
| Retry on failure | PID controller modulates reflection pressure |
| Linear execution | Lorenz attractor creates chaotic replanning at wing crosses |
| Screen-dependent | Headless-first; enables GUI only when needed |
| Truncate context | Full observation fidelity — LLM sees everything |

## Reactor Concepts

| Reactor | Code |
|---------|------|
| Fuel rods | LLM agents (planner, actor) |
| Fission | Verifier-confirmed completion |
| Power | completions / elapsed seconds |
| Prompt neutrons | Lorenz wing cross → immediate replan |
| Delayed neutrons | Reflector lessons → prompt mutations |
| Control rods | PID output → modulates reflection |
| Fuel depletion | Completed list prevents repeats |
| Chain reaction | Success → plan next → succeed → repeat |

## Usage

```
python main.py "your goal" --backend acp --event-budget 50
python main.py --backend acp --event-budget 200          # reactor mode (no goal)
python tui.py "goal" --backend acp --event-budget 100    # live reactor dashboard
python debug_context.py planner --goal "text"            # inspect LLM context
```

## Prompt Soul

Every agent opens with: *"You are sitting at a Windows desktop with full control of mouse, keyboard, and shell."*

Then 2 sentences that give it purpose:
- **Planner**: Think before you act. Never downgrade the success condition.
- **Actor**: Understand what you see. Refuse doomed actions.
- **Verifier**: A trivially true condition that doesn't prove the goal is a lie, not fission.
- **Reflector**: Be honest. Only mutate for systemic failures, not noise.

## Proven Results

- **Goal mode**: "write file" → fission in 28 events, exit 0, zero screen scans
- **Reactor mode**: autonomous fission at event 65 — system profiled its own environment, created discovery files, verified them, then immediately planned next task
- **Self-evolution**: reflector mutated planner 3 times in single run, final mutation: "propose exploratory task to keep energy above zero"
- **Self-correction**: hello.py escaping failure → reflector diagnosed → actor adapted → success

## Current State

Branch `refactor-v4`. Reactor architecture complete. Soul added. All truncation removed. Awaiting final integration test with the new prompt soul to validate that the 11-replan Grok failure (caused by context amnesia + soulless prompts) is resolved.

## Files

```
main.py           Entry point, board init
engine.py         Reactor core: math thread + main loop + fission
agents.py         All agents + scheduler + context rendering
config.py         All constants
llm.py            LLM backend (ACP / LM Studio)
actions.py        Verb execution
observer.py       Win32 UI Automation screen scanner
win32.py          Raw ctypes Win32 bindings
log.py            Event logger
tui.py            Live reactor dashboard
acp_client.py     Kiro CLI ACP protocol
debug_context.py  Context dump tool
```

## Requirements

- Windows 11
- Python 3.13
- Nothing else
