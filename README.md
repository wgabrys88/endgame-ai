# endgame-ai

A self-regulating Windows desktop automation organism. Pure Python 3.13, zero dependencies, raw ctypes.

Three mathematical pipelines (Lorenz, PID, Jacobian) govern behavior. LLMs provide intelligence. Mathematics provides stability and controlled chaos.

---

## Architecture

```
observe(screen) → math.decide_next_role() → dispatch(role) → loop
                         │
         ┌───────────────┼───────────────────┐
         │               │                   │
    Lorenz fork     PID pressure      Jacobian sensitivity
    (chaos replan)  (reflector gate)  (verb effectiveness)
```

The **blackboard** (`Board` in state.py) holds all truth. The **context pipeline** (`CONTEXT_POLICY` in config.py) controls what each LLM role sees — a deterministic projection of the blackboard per role.

Math decides WHO acts. LLMs decide WHAT to do. Each LLM has a `recipient` field to request who goes next. Math can override.

### The Pulse

```
loop:
  observe()                        # screen capture via UIA + cursor probe
  role = board.decide_next_role()  # Lorenz/PID/recipient routing
  dispatch(role)                   # call LLM, apply response to blackboard
```

Natural flow: `planner → actor → planner → actor ...`

Interventions (math-only):
- **Lorenz wing cross** → force planner with DIVERGE (clear plan, try different approach)
- **PID > threshold** → inject reflector (diagnose stagnation)
- **Stagnation sustained** → halt

### Roles

| Role | Reads | Writes | Purpose |
|------|-------|--------|---------|
| Planner | goal, screen, plan, history, budget, failures, roles | plan_steps, next_action | Decides what to do next |
| Actor | instruction, screen, roles | actions, observations | Executes GUI primitives |
| Verifier | goal, screen, history, plan, roles | verdict | Confirms goal complete |
| Reflector | goal, screen, plan, history, math, roles | diagnosis, lesson | Diagnoses stuck patterns |

Each role sees what other roles last produced (mutual awareness via `roles` context field).

---

## Usage

```
python main.py "goal" --backend acp --event-budget 50
python main.py "goal" --backend lmstudio --event-budget 100
python analyze_run.py events.jsonl
python tui.py events.jsonl
```

`acp`: Claude via kiro-cli (fast, reliable).
`lmstudio`: Local LLM at localhost:1234.

---

## Mathematical Pipelines

### Lorenz Attractor (controlled chaos)

Stagnation feeds into Lorenz ODE parameters. When the trajectory crosses wings (x changes sign), the system forces a completely different approach. This prevents loops — there is always a way forward.

```
rho_eff = 28 + stagnation * 1.5 * 28    # more stagnation = more chaos
wing_cross → clear plan, inject DIVERGE
attractor_energy → scales LLM temperature (stuck = more creative)
```

### PID Controller (reflection gate)

Accumulates stagnation error. When output crosses threshold, promotes the reflector role. Anti-windup: integral resets on step advance.

```
error = stagnation_score
pid_output = Kp*error + Ki*integral + Kd*slope
pid > 0.5 → reflector fires
```

### Jacobian (sensitivity analysis)

Tracks which verbs cause screen changes: `∂(screen_change)/∂(action_type)`. Exponential moving average per verb. Exposed to reflector for informed diagnosis.

```
update_jacobian(verb, screen_changed: bool)
# hotkey=0.875, write=1.0, click=0.25 (typical)
```

---

## Files

```
main.py           Entry point, CLI, signal handling
orchestrator.py   Math-driven loop, role dispatch, action execution
state.py          Blackboard (Board), 3 math pipelines, context rendering
config.py         All constants, CONTEXT_POLICY, no magic numbers elsewhere
observer.py       UIA tree walk + cursor probe scan, element classification
actions.py        10 verb handlers (click, write, hotkey, press, scroll, wait, focus, read_file, write_file, cmd)
dispatch.py       LLM call wrapper + JSON extraction
llm.py            Backend transport (LM Studio HTTP / ACP JSON-RPC)
acp_client.py     ACP protocol client (Kiro CLI via WSL2)
win32.py          Raw ctypes: UIA COM, SendInput, window management
log.py            JSONL event emitter + budget counter
tui.py            Event-driven TUI (watches events.jsonl live)
analyze_run.py    Post-execution statistics (timing, math state, Jacobian)
prompts/          System prompts (4 roles)
schemas/          JSON schemas with recipient field (4 roles)
```

---

## Design Rules

1. One loop. Mathematics controls scheduling. No mode switching.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py.
4. No fallback modes. Dead code is wrong code.
5. The three mathematical laws are non-negotiable.
6. Prompts are mutable by the organism at runtime.
7. The blackboard is the single source of truth. CONTEXT_POLICY controls projection.
8. Fewer moving parts beats theatrical autonomy.
9. Each LLM knows what other LLMs are (mutual awareness).
10. Events are the measurement of behavior — every `log.emit()` = 1 event toward budget.

---

## Evolution Roadmap

### Current: v6 — Math-Pulse (this branch)

Working system. Math schedules roles. LLMs route via recipient. Lorenz/PID/Jacobian all active. Proven: completes multi-step GUI tasks in 20-40 events.

### Next: v7 — Event-Driven Blackboard

Events become the communication substrate, not just a log. Each LLM emits events that other LLMs consume. The event stream IS the blackboard truth. Python becomes minimal glue — math + event routing only.

### Future: v8 — 3-Tier Self-Evolution

```
Tier 1: Prompt mutation     — reflector rewrites prompts at runtime (min 200 chars enforced)
Tier 2: Code modification   — git branch + clone + regression test + swap
Tier 3: Resurrection        — scheduled task resurrects with new code after self-termination
```

The organism modifies itself, tests the modification, and replaces itself with a better version. Decoupled resurrection ensures it cannot permanently die.

---

## Development Protocol

### Scientist Mode

1. Before claiming behavior, state if tested-in-this-session or untested-prior.
2. Untested-prior claims require a minimal falsification experiment.
3. Never invent results.
4. Treat counter-intuitive requests as hypotheses to test.
5. When results arrive, update plainly.

### After Implementation

```
pyright (strict, 0/0/0)  →  run with simple goal  →  analyze_run.py  →  commit
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
