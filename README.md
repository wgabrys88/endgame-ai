# endgame-ai

Self-regulating Windows desktop automation. Pure Python 3.13, zero dependencies, raw ctypes.

Six agents — one pulse (all math + scheduling), one observer, four LLMs — communicate through a unified blackboard. The organism has a heartbeat: every cycle emits observe + pulse + work. Every event counts equally. Mathematics provides controlled chaos. LLMs provide intelligence. Python provides working memory.

---

## Current State (math-pulse branch, 2026-06-09)

Working system. Proven on both cloud (ACP/Claude) and local (LM Studio/gemma-4-e2b-it 2B).

### Proven Results

| Goal | ACP (Claude) | LM Studio (2B) |
|------|-------------|-----------------|
| write_file output.txt (text) | 15 events, EXIT=0 | 15 events, EXIT=0 |
| open notepad type hello | cmd notepad.exe (correct) | clicked wrong element (planning) |
| write hello world to output.txt | 9 events, EXIT=0 | self-corrected via deny-replan |

Both backends produce **identical event traces** for file tasks: start → observe → pulse → plan → observe → pulse → action → actor → observe → pulse → plan(done) → observe → pulse → verify → complete.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BLACKBOARD (board.py)                      │
│              pure state — no computation, no methods              │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
     OBSERVER            PULSE            LLM AGENTS
     (screen scan)   (math+schedule)     (on demand)
          │                  │                  │
          ▼                  ▼                  ▼
       1 event           1 event           1 event
          └──────────────────┼──────────────────┘
                             │
                    3 events per cycle
                             │
                         TUI (viewer + launcher + agent toggle)
                             │
                    disabled.json ──► orchestrator skips agent
```

All agents implement the same protocol:
```
should_run(board) → bool
run(board) → AgentResult{writes, next_agent, event_phase, event_data}
```

Every event counts against budget equally. Budget = organism lifetime in ticks.

### Agents

| Agent | Type | Purpose |
|-------|------|---------|
| observer | sys | Screen scan via UIA + cursor probe |
| pulse | math | Stagnation + Lorenz + PID + Jacobian + Scheduling — all in one tick |
| planner | llm | Generates multi-step plan (once per plan) |
| actor | llm | Executes actions (with direct-execute bypass) |
| verifier | llm | Confirms goal complete with evidence |
| reflector | llm | Diagnoses loops, writes lessons, mutates prompts |

### Pulse Agent (agents/pulse.py)

Single agent that computes all math and makes the scheduling decision:
1. Stagnation: repetition window + failure weight + screen stagnation
2. Lorenz: ODE step, wing cross detection (forces replan)
3. PID: error integration, gates reflector
4. Jacobian: verb effectiveness tracking
5. Schedule: picks next LLM (planner/actor/verifier/reflector/halt)

Returns `next_agent` field — orchestrator dispatches that LLM.

### Direct-Execute

When a planner step starts with a known verb and Python can parse arguments, the actor LLM is skipped. Python executes directly. Saves 1 LLM call per step.

### Agent Toggle

Human can disable any agent via TUI (writes `disabled.json`). Orchestrator reads it each cycle. A disabled agent causes the system to adapt, not crash.

---

## Usage

**TUI launcher (starts paused, spacebar runs):**
```
python tui.py "goal" --backend lmstudio --event-budget 20
```

**TUI viewer only (watches existing run):**
```
python tui.py
```

**Direct execution (no TUI):**
```
python main.py "goal" --backend acp --event-budget 20
```

**Analysis:**
```
python analyze_run.py events.jsonl
```

Cleanup between runs:
```
del events.jsonl snapshot.json output.txt lessons.txt
```

TUI controls: `Space`=launch `↑↓`=select agent `Enter`=toggle `q`=quit

---

## Files

```
main.py              Entry point, CLI, signal handling
orchestrator.py      observe + pulse + LLM dispatch loop (no branching)
board.py             Pure state blackboard (no computation)
context.py           Renders blackboard to text for LLM context
config.py            All constants, CONTEXT_POLICY, math params
log.py               Single emit function, every event counts
observer.py          Full-screen probe (UIA + cursor), element tree
actions.py           10 verb handlers (click, write, hotkey, press, scroll, wait, focus, read_file, write_file, cmd)
dispatch.py          LLM call wrapper + JSON extraction
llm.py               Backend transport (LM Studio HTTP / ACP JSON-RPC)
acp_client.py        ACP protocol client (session, streaming)
win32.py             Raw ctypes: UIA COM, SendInput, window management
tui.py               Dashboard + launcher (braille Lorenz plot, agent toggle)
analyze_run.py       Post-execution statistics
agents/__init__.py   Agent protocol (AgentResult dataclass)
agents/observer_agent.py  Screen observation agent
agents/pulse.py           All math + scheduling in one tick
agents/planner.py         LLM planner agent
agents/actor.py           LLM actor + direct-execute
agents/verifier.py        LLM verifier agent
agents/reflector.py       LLM reflector + prompt mutation
prompts/             System prompts (mutable at runtime by reflector)
schemas/             JSON schemas for constrained decoding
```

---

## Design Rules

1. One loop. One dispatch function for all agents. No branching by type.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py.
4. No fallback modes. Dead code is wrong code.
5. The three mathematical laws are non-negotiable.
6. Prompts are mutable by the organism at runtime.
7. The blackboard is the single source of truth.
8. Every event counts equally. Budget = lifetime.
9. Python IS working memory — what can be parsed deterministically should be.
10. Fewer moving parts beats theatrical autonomy.

---

## Next Session Focus

**Pulse-driven observation:** Currently observer runs every cycle unconditionally. The pulse agent should determine whether observation is needed based on events. When no LLM is working (idle state), pulse decides the next recipient — which could be observer OR an LLM. Observer becomes demand-driven, not always-on. This reduces events-per-cycle from 3 to 2 when observation isn't needed (e.g., after a write_file where screen didn't change).

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
- 6 agents: pulse (stagnation+lorenz+pid+jacobian+scheduler) + observer + 4 LLMs
- All agents: should_run(board) → run(board) → AgentResult{writes, next_agent}
- Every event counts equally. Budget = organism lifetime in ticks.
- Pattern per cycle: observe(1) + pulse(1) + work(1) = 3 events
- Orchestrator: single _emit_agent() dispatches any agent identically, zero branching
- Direct-execute: if step starts with known verb, Python executes without actor LLM
- Agent toggle: disabled.json disables agents, system adapts
- Board is pure state. Context rendering is separate. No computation in Board.
- TUI: dashboard + launcher (braille Lorenz plot, spacebar launches system)

NEXT SESSION GOAL: Make observer demand-driven. Pulse decides next recipient
(observer OR LLM). When pulse determines no observation needed (screen unchanged,
no LLM pending), it skips observer. Every agent event has a "next" field that
tells orchestrator who runs next. This unifies the pipeline completely — pulse
is the brain that routes ALL agents, not just LLMs.

PROVEN FACTS (2026-06-09):
- Both backends: 15 events for file-write task (EXIT=0, identical traces)
- No math agent uses wall-clock time (all tick per call)
- Single pulse event replaces 5 separate math events
- Actor schema: 2 fields (actions, conclusion). 60% token reduction.
- Full-screen probe = single most impactful change for 2B behavior
- Direct-execute reduces events AND removes actor confusion
- 2B weakness is PLANNING, not perception or execution

RULES (non-negotiable):
- Pyright strict: 0/0/0
- No comments. No docstrings. No magic numbers outside config.py
- No fallback modes. Dead code is wrong code
- No examples/templates in prompts (2B copies verbatim)
- No push without human approval
- Scientist mode: test claims, state tested vs untested, update plainly

TESTING:
  python tui.py "goal" --backend lmstudio --event-budget 20  (launcher)
  python main.py "goal" --backend acp --event-budget 20       (direct)
  Cleanup: del events.jsonl snapshot.json output.txt lessons.txt
  Typecheck: python -m pyright (must be 0/0/0)
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
