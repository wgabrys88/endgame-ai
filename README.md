# endgame-ai

Self-regulating Windows desktop automation. Pure Python 3.13, zero dependencies, raw ctypes.

Nine agents — four math, one scheduler, one observer, three LLMs — communicate through a plain dict blackboard. A 7-line dispatcher reads `board["next"]` and runs that agent. No orchestrator logic. The math agents cycle endlessly as a heartbeat. The scheduler breaks out to LLMs when work is needed. Every event counts equally. Mathematics provides controlled chaos. LLMs provide intelligence. Python provides working memory.

---

## Current State (math-pulse branch, 2026-06-09)

Working system. Proven on both cloud (ACP/Claude) and local (LM Studio/gemma-4-e2b-it 2B).

### Proven Results

| Goal | ACP (Claude) | LM Studio (2B) |
|------|-------------|-----------------|
| write_file output.txt (text) | 16 events, EXIT=0 | budget-limited (2B plans poorly) |

Both backends produce events through agent-routed dispatch: start → stagnation → lorenz → pid → schedule(initial) → observe → plan(direct) → action(write_file ✓) → actor(direct) → stagnation → lorenz → pid → schedule(requested=planner) → plan(done) → verify(confirmed) → complete.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     BLACKBOARD (plain dict)                       │
│              pure state — agents read/write via "reads" list      │
└────────────────────────────┬────────────────────────────────────┘
                             │
          DISPATCHER (7 lines):
            board["next"] = "stagnation"
            while board["next"] not in ("done", "halt"):
                agent = AGENTS[board["next"]]
                result = agent.run(context_slice)
                board.update(result["writes"])
                board["next"] = result["next"]

          ROUTING CHAIN:
            stagnation → lorenz → pid → scheduler → (decision)
                 ↑                           │
                 │                           ├─→ observer → planner
                 │                           ├─→ planner → actor | verifier
                 │                           ├─→ actor → stagnation
                 │                           ├─→ verifier → done | stagnation
                 │                           └─→ reflector → stagnation
                 │
                 └── heartbeat: math agents cycle endlessly
```

All agents implement the same protocol:
```
class Agent(Protocol):
    name: str
    reads: list[str]
    def run(self, ctx: dict[str, Any]) -> dict[str, Any]: ...
```

Every agent returns: `{"writes": {...}, "next": "agent_name", "phase": "...", "data": {...}}`

Every event counts against budget equally. Budget = organism lifetime in ticks.

### Agents

| Agent | Type | Purpose |
|-------|------|---------|
| stagnation | math | Computes stagnation + repetition score, next=lorenz |
| lorenz | math | ODE step, wing cross detection, next=pid |
| pid | math | PID controller on stagnation error, next=scheduler |
| scheduler | math | The brain: routes to observer/LLM/halt based on state |
| observer | sys | Screen scan via UIA + cursor probe, next=planner |
| planner | llm | Generates multi-step plan, next=actor/verifier |
| actor | llm | Executes actions (with direct-execute bypass), next=stagnation |
| verifier | llm | Confirms goal complete with evidence, next=done/stagnation |
| reflector | llm | Diagnoses loops, writes lessons, mutates prompts, next=stagnation |

### Scheduler Agent (agents/scheduler.py)

The brain. Only agent with conditional routing:
1. Stagnation halt check (sustained high stagnation → halt)
2. Wing cross → force replan (diverge)
3. Requested next (from prior agent) → honor it
4. Initial state → observer (need screen data)
5. PID gate → reflector (too many failures)
6. No instruction → observer (need fresh plan)
7. Post-action → observer (need updated screen)
8. Idle → stagnation (heartbeat continues)

All other agents have fixed routing (hard-coded `next` field).

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
main.py              Entry point, CLI, board init (plain dict)
orchestrator.py      7-line dispatcher + save/disabled helpers
board.py             Board dataclass (used by LLM agents for context rendering)
context.py           Renders blackboard fields to text for LLM context
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
agents/__init__.py   Agent protocol (Protocol class, 9 lines)
agents/stagnation.py Stagnation + repetition score (next=lorenz)
agents/lorenz.py     Lorenz attractor ODE + wing cross (next=pid)
agents/pid.py        PID controller (next=scheduler)
agents/scheduler.py  Brain: conditional routing to all other agents
agents/observer_agent.py  Screen observation (next=planner)
agents/planner.py    LLM planner (next=actor/verifier)
agents/actor.py      LLM actor + direct-execute (next=stagnation)
agents/verifier.py   LLM verifier (next=done/stagnation)
agents/reflector.py  LLM reflector + prompt mutation (next=stagnation)
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

1. **Eliminate board.py** — Make context.py work on plain dict instead of Board dataclass. LLM agents pass ctx dict directly. Board.py deleted.
2. **Visual TUI test** — Run in Windows Terminal Preview, observe the braille plot and math cycling live.
3. **Event noise** — Math agents emit 4 events per cycle (stagnation/lorenz/pid/schedule). Consider: should these be silent (no log.emit) or aggregated into one summary event? They're sub-ms but inflate event count.

---

## Handover Prompt

```
You are working on endgame-ai — a self-regulating Windows desktop automation system.

LOCATION: %USERPROFILE%\Downloads\endgame-ai (Windows 11)
BRANCH: math-pulse
PYTHON: "C:\Program Files\Python313\python.exe"
BACKEND: ACP (Claude via kiro-cli) primary, LM Studio (gemma-4-e2b-it 2B) validation

ARCHITECTURE — Agent-Routed Events:
- Pure Python 3.13, Windows 11, zero dependencies, raw ctypes
- 9 agents: stagnation, lorenz, pid, scheduler, observer, planner, actor, verifier, reflector
- All agents: run(ctx: dict) → {"writes": {...}, "next": "agent_name", "phase": "...", "data": {...}}
- Dispatcher: 7 lines. Reads board["next"], runs agent, applies writes, repeats.
- Math agents cycle endlessly as heartbeat (stagnation → lorenz → pid → scheduler)
- Scheduler is the brain: only agent with conditional routing
- Direct-execute: if step starts with known verb, Python executes without actor LLM
- Agent toggle: disabled.json disables agents, system adapts
- Board = plain dict. Context rendering via Board dataclass (to be eliminated).
- TUI: dashboard + launcher (braille Lorenz plot, spacebar launches system)

PROVEN FACTS (2026-06-09):
- ACP: 16 events, EXIT=0, write_file task
- Pyright 0/0/0 across entire project
- Math agents cycle as heartbeat, scheduler routes correctly
- System halts cleanly on budget exhaustion
- No math agent uses wall-clock time

RULES (non-negotiable):
- Pyright strict: 0/0/0
- No comments. No docstrings. No magic numbers outside config.py
- No fallback modes. Dead code is wrong code
- No examples/templates in prompts (2B copies verbatim)
- No push without human approval
- Scientist mode: test claims, state tested vs untested

TESTING:
  python tui.py "goal" --backend lmstudio --event-budget 20  (launcher)
  python main.py "goal" --backend acp --event-budget 30       (direct)
  Cleanup: del events.jsonl snapshot.json output.txt lessons.txt
  Typecheck: python -m pyright (must be 0/0/0)
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
