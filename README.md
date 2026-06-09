# endgame-ai

Self-regulating Windows desktop automation. Pure Python 3.13, zero dependencies, raw ctypes.

Nine agents — four math, one observer, one scheduler, three LLMs — communicate through a unified blackboard. The organism has a heartbeat: math agents pulse every cycle, even with no goal. Mathematics provides controlled chaos. LLMs provide intelligence. Python provides working memory.

---

## Current State (math-pulse branch, 2026-06-09)

Working system. Proven on both cloud (ACP/Claude) and local (LM Studio/gemma-4-e2b-it 2B).

### Proven Results

| Goal | ACP (Claude) | LM Studio (2B) |
|------|-------------|-----------------|
| write_file output.txt (text) | 7 events, EXIT=0 | 7 events, EXIT=0 |
| open notepad type hello | cmd notepad.exe (correct) | clicked wrong element (planning) |
| write hello world to output.txt | 9 events, EXIT=0 | self-corrected via deny-replan |

Both backends produce **identical event traces** for file tasks: start → plan → action → actor → plan(done) → verify → complete.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BLACKBOARD (board.py)                      │
│              pure state — no computation, no methods              │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ♥ HEARTBEAT          SCHEDULER           LLM AGENTS
   (always pulse)        (Python)           (on demand)
   ┌──────────┐       ┌──────────┐       ┌──────────┐
   │observer  │       │picks next│       │planner   │
   │stagnation│──────►│LLM based │──────►│actor     │
   │lorenz    │       │on math   │       │verifier  │
   │pid       │       │signals   │       │reflector │
   │jacobian  │       └──────────┘       └──────────┘
   └──────────┘
        │                                      │
        └──────────► TUI (viewer + toggle) ◄───┘
                         │
                         ▼
                    disabled.json ──► orchestrator skips agent
```

All agents implement the same protocol:
```python
should_run(board) → bool
run(board) → AgentResult{writes, next_agent, event_phase, event_data}
```

The orchestrator applies `writes` to the blackboard. The blackboard is the single source of truth.

### Agents

| Agent | Type | Runs | Purpose |
|-------|------|------|---------|
| observer | sys | every cycle | Screen scan via UIA + cursor probe |
| stagnation | math | every cycle | Repetition + stagnation signals |
| lorenz | math | every cycle | Chaos attractor, wing cross → force replan |
| pid | math | every cycle | Error integration, gates reflector |
| jacobian | math | when verb exists | Verb effectiveness tracking |
| scheduler | python | every cycle | Routes to next LLM based on math signals |
| planner | llm | on demand | Generates multi-step plan (once per plan) |
| actor | llm | on demand | Executes actions (with direct-execute bypass) |
| verifier | llm | on demand | Confirms goal complete with evidence |
| reflector | llm | on demand | Diagnoses loops, writes lessons, mutates prompts |

### Event System

- `log.emit(phase, data)` — budget events (LLM work). Counted toward event budget.
- `log.trace(phase, data)` — heartbeat telemetry. Not counted. Full observability.
- Both written to `events.jsonl`. TUI displays all.
- Budget only limits LLM-related work — math agents pulse freely.

### Direct-Execute

When a planner step starts with a known verb and Python can parse arguments, the actor LLM is skipped. Python executes directly. Saves 1 LLM call per step.

### Agent Toggle

Human can disable any agent via TUI (writes `disabled.json`). Orchestrator reads it each cycle. A disabled agent causes the system to adapt, not crash. Disable lorenz → no chaos replan. Disable pid → no reflector gate. The organism evolves around constraints.

---

## Usage

```
python main.py "goal" --backend acp --event-budget 20
python main.py "goal" --backend lmstudio --event-budget 20
python tui.py
python analyze_run.py events.jsonl
```

Cleanup between runs:
```
del events.jsonl snapshot.json output.txt lessons.txt
```

TUI keys: `1`=Agents `2`=Events `3`=Math `4`=Plan `↑↓`=navigate `Enter`=toggle `Space`=pause `q`=quit

---

## Files

```
main.py              Entry point, CLI, signal handling
orchestrator.py      Heartbeat pulse + scheduler + LLM dispatch loop
board.py             Pure state blackboard (no computation)
context.py           Renders blackboard to text for LLM context
config.py            All constants, CONTEXT_POLICY, math params
log.py               emit (budget) + trace (telemetry) to events.jsonl
observer.py          Full-screen probe (UIA + cursor), element tree render
actions.py           10 verb handlers (click, write, hotkey, press, scroll, wait, focus, read_file, write_file, cmd)
dispatch.py          LLM call wrapper + JSON extraction
llm.py               Backend transport (LM Studio HTTP / ACP JSON-RPC)
acp_client.py        ACP protocol client (session, streaming)
win32.py             Raw ctypes: UIA COM, SendInput, window management
tui.py               Blackboard viewer with agent panel + toggle
analyze_run.py       Post-execution statistics
agents/__init__.py   Agent protocol (AgentResult dataclass)
agents/observer_agent.py  Screen observation agent
agents/stagnation.py      Stagnation/repetition computation
agents/lorenz.py          Lorenz attractor (chaos replan)
agents/pid.py             PID controller (reflector gate)
agents/jacobian.py        Verb effectiveness tracking
agents/scheduler.py       Python intelligence (role selection)
agents/planner.py         LLM planner agent
agents/actor.py           LLM actor + direct-execute
agents/verifier.py        LLM verifier agent
agents/reflector.py       LLM reflector + prompt mutation
prompts/             System prompts (mutable at runtime by reflector)
schemas/             JSON schemas for constrained decoding
```

---

## Design Rules

1. One loop. Mathematics controls scheduling via heartbeat.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py.
4. No fallback modes. Dead code is wrong code.
5. The three mathematical laws are non-negotiable.
6. Prompts are mutable by the organism at runtime.
7. The blackboard is the single source of truth. All agents communicate through it.
8. Fewer moving parts beats theatrical autonomy.
9. Python IS working memory — what can be parsed deterministically should be.
10. Budget events measure LLM work. Trace events measure heartbeat. Both are visible.

---

## Mathematical Pipelines

### Lorenz Attractor (controlled chaos)

Stagnation feeds Lorenz ODE. Wing cross (x sign change) AND stagnation > 0.4 → force completely different approach.

### PID Controller (reflection gate)

Accumulates stagnation error. Gates reflector when output > threshold. Integral resets on step advance.

### Jacobian (sensitivity analysis)

Tracks screen-change per verb. Exposed to reflector for diagnosis. Alpha-blended running average.

### Self-Evolution Tiers

- Tier 1: Lessons persist to lessons.txt across runs
- Tier 2: Reflector mutates prompts at runtime (min 200 chars enforced)
- Tier 3: Code modification — future
- Tier 4: Resurrection — future

---

## Handover Prompt

```
You are working on endgame-ai — a self-regulating Windows desktop automation system.

LOCATION: %USERPROFILE%\Downloads\endgame-ai (Windows 11)
BRANCH: math-pulse
PYTHON: "C:\Program Files\Python313\python.exe"
BACKEND: ACP (Claude via kiro-cli) primary, LM Studio (gemma-4-e2b-it 2B) validation

ARCHITECTURE — Unified Agent Protocol:
- Pure Python 3.13, Windows 11, zero dependencies, raw ctypes
- 9 agents: 4 math (stagnation, lorenz, pid, jacobian) + observer + scheduler + 3 LLMs
- All agents: should_run(board) → run(board) → AgentResult{writes, next_agent}
- Heartbeat: math agents pulse every cycle, emit trace events (don't consume budget)
- Scheduler (Python) picks next LLM based on math signals
- Direct-execute: if step starts with known verb, Python executes without actor LLM
- Agent toggle: disabled.json disables agents, system adapts
- Board is pure state. Context rendering is separate. No computation in Board.

LOOP: observe → stagnation → lorenz → pid → jacobian → scheduler → [LLM agent] → repeat

PROVEN FACTS (2026-06-09):
- Both backends: 7 budget events for file-write task (optimal path)
- Heartbeat: 22 trace events per run (full observability, zero budget cost)
- Actor schema: 2 fields (actions, conclusion). 60% token reduction from original 4.
- Full-screen probe = single most impactful change for 2B behavior
- Direct-execute reduces events AND removes actor confusion
- 2B weakness is PLANNING, not perception or execution
- Agent toggle works: disabled agents cause adaptation, not failure

RULES (non-negotiable):
- Pyright strict: 0/0/0
- No comments. No docstrings. No magic numbers outside config.py
- No fallback modes. Dead code is wrong code
- No examples/templates in prompts (2B copies verbatim)
- No push without human approval
- Scientist mode: test claims, state tested vs untested, update plainly on contradiction

TESTING:
  python main.py "goal" --backend acp --event-budget 20
  python main.py "goal" --backend lmstudio --event-budget 20
  python tui.py
  Cleanup: del events.jsonl snapshot.json output.txt lessons.txt
  Typecheck: python -m pyright (must be 0/0/0)
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
