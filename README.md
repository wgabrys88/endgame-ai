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

## Session Handover

### Last Session Results (2026-06-09)

Architecture rewrite: 5,752 → 2,698 lines (53% reduction). Event-driven pipeline proven with ACP (30 events, goal COMPLETE). LM Studio tested — local model loops on Win+R due to plan-state blindness.

### Next Session Focus: LLM Event Awareness

The next evolution: **every LLM must know what event it is emitting and what other LLMs have done**. Currently the LLMs are stateless tools called by Python. The goal is to make events the PRIMARY communication mechanism — LLMs emit events, consume events, and the blackboard is completely self-regulated.

Key changes needed:
1. **Event identity in context**: Each LLM call should include `EVENT_N: 15/40` so the model knows its position in the budget stream.
2. **Cross-role awareness**: The actor should see what the planner decided (not just the instruction). The planner should see what the actor observed. Events flow between roles.
3. **Self-emitted events**: LLMs should be able to emit custom events (signals, annotations, state changes) that become part of the blackboard truth.
4. **Math as event pressure**: Lorenz/PID should modify which events get emitted (suppress expensive paths, amplify divergent exploration) based on the event stream itself.
5. **Unpredictable self-regulation**: The event sequence becomes emergent — not a fixed observe→plan→act pipeline, but a dynamic graph where any role can trigger any other based on event content.

### Continuation Prompt

```
You are working on endgame-ai at %USERPROFILE%\Downloads\endgame-ai (Windows 11, Python 3.13, zero dependencies, raw ctypes).
Branch: codex/event-driven-v2

The system is an event-driven blackboard organism. 12 Python files, 2698 lines total.
Architecture: observe → plan → act → verify, bounded by --event-budget N.
Math: Lorenz attractor (chaos fork), PID (reflection gate), stagnation score.
Backends: ACP (Kiro CLI) and LM Studio (local).

PROVEN: ACP completes "open notepad and type hello world" in 30 events.
PROBLEM: LM Studio loops — model doesn't track plan state, repeats step 1.

GOAL: Make events the communication substrate. Each LLM knows its event number,
sees other LLMs' events, and can emit its own events. The pipeline becomes
self-regulating — not Python-controlled but event-controlled. The math
(Lorenz/PID) operates ON the event stream to create adaptation pressure.

Read all files before proposing changes. SCIENTIST MODE.
```
