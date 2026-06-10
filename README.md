# endgame-ai

Self-regulating Windows desktop automation. Pure Python 3.13, zero dependencies, raw ctypes.

Nine agents — four math, one scheduler, one observer, three LLMs — communicate through a plain dict blackboard. A dispatcher reads `board["next"]` and runs that agent. Mathematics provides controlled chaos. LLMs provide intelligence. Python provides working memory.

---

## Architecture (v4, 2026-06-10)

```
┌──────────────────────────────────────────────────────────────────┐
│                    BLACKBOARD (plain dict)                         │
│            agents read/write via "reads" list                     │
└───────────────────────────┬──────────────────────────────────────┘
                            │
         DISPATCHER (engine.py):
           board["next"] = "stagnation"
           while board["next"] not in ("done", "halt"):
               agent = AGENTS[board["next"]]
               result = agent.run(context_slice)
               board.update(result["writes"])
               board["next"] = result["next"]

         ROUTING:
           stagnation → lorenz → pid → scheduler → (decision)
                ↑                           │
                │                           ├→ planner → actor
                │                           ├→ actor → stagnation
                │                           ├→ verifier → done | stagnation
                │                           └→ reflector → stagnation
                │
                └── heartbeat: math agents cycle endlessly

         OBSERVER fires automatically before every LLM agent.
```

### Files (11 total)

| File | Lines | Purpose |
|------|-------|---------|
| main.py | 85 | Entry point, CLI, signal handling |
| engine.py | 75 | Dispatcher loop, agent registry |
| agents.py | 540 | All 9 agents + context rendering + JSON extraction |
| config.py | 170 | All constants and tuning parameters |
| llm.py | 110 | LLM backend (LM Studio / ACP) |
| actions.py | 190 | Verb execution (click, write, cmd, etc.) |
| observer.py | 500 | UIA screen scanning + cursor probe |
| win32.py | 250 | Raw ctypes Win32/COM bindings |
| log.py | 50 | Event logging (JSONL) |
| tui.py | 350 | Real-time dashboard |
| acp_client.py | 200 | Kiro CLI ACP protocol client |

### Agents

| Agent | Type | Purpose |
|-------|------|---------|
| stagnation | math | Measures plan progress stall |
| lorenz | math | ODE step, wing cross = forced replan |
| pid | math | PID controller on stagnation |
| scheduler | math | Routes to LLM/halt based on state |
| observer | sys | Screen scan via UIA, auto-fired |
| planner | llm | Generates multi-step plan |
| actor | llm | Executes actions (with direct-execute bypass) |
| verifier | llm | Confirms goal complete |
| reflector | llm | Diagnoses loops, mutates prompts |

### Math Signal Chain

```
PLAN PROGRESS = count(done steps) / count(all steps)

STAGNATION:
  0.0  if progress advanced this cycle
  0.3  if advancing slowly over window
  1.0  if flat (no progress in N cycles)
  + 0.15 per consecutive failure

LORENZ: ODE step with stagnation input
  Wing cross (x sign flip) when stag > 0.4 → forces replan

PID: KP*stag + KI*integral + KD*slope
  Output > 0.6 → reflector fires (with min interval 8 cycles)
```

### Proven Results (v4)

| Task | Events | Outcome |
|------|--------|---------|
| write_file test.txt hello | 17 | ✓ confirmed |
| read README + write summary | 31 | ✓ confirmed |
| create 3 files (a,b,c.txt) | 31 | ✓ confirmed |
| create hello.py + run + capture output | 41 | ✓ (self-corrected escaping failure) |

### Self-Correction Example

```
Plan: write hello.py, run it
Step 1: echo print(\"hello\") > hello.py  → OK (but bad escaping)
Step 2: python hello.py > result.txt    → FAIL (syntax error)
Math: stagnation=0.45, PID=1.26 > threshold
Reflector: "cmd echo with improper escaping"
Mutation: actor prompt += "use single quotes in echo"
Replan: echo print('hello world') > hello.py
Step 1: OK
Step 2: python hello.py > result.txt → OK
Result: "hello world"
```

---

## Usage

```
python main.py "goal description" --backend acp --event-budget 50
python main.py "goal description" --backend lmstudio --event-budget 100
```

## Configuration

All tuning in `config.py`. Key parameters:
- `REFLECT_THRESHOLD = 0.6` — PID output needed to trigger reflector
- `REFLECT_MIN_INTERVAL = 8` — minimum cycles between reflections
- `PROMPT_MAX_RULES = 8` — max runtime-mutated rules per prompt (FIFO)
- `STAGNATION_CYCLES_WINDOW = 6` — cycles to measure progress over
- `MAX_PLAN_STEPS = 12` — max steps in a single plan
