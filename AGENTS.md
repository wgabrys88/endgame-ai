# AGENTS.md — Colony Architecture Map

## Terminology

- **Persona** — a named identity (architect, implementor, reviewer, comms_operator, devops, quality_critic). Each runs as a separate OS process.
- **Agent** — a pipeline stage inside each persona (scheduler, planner, actor, verifier, fission_judge, reflector, mutator). All personas share the same agent pipeline.
- **Reactor** — spawns and monitors all 6 personas. Restarts dead ones.
- **TUI** — fixed 45-line terminal UI showing all personas, their active agent, math state, and the message bus.

## Pipeline (inside each persona)

```
[math thread]  stagnation → lorenz → PID       (runs every 12s)
                    ↓
[main loop]   scheduler → planner → actor → verifier → fission_judge → fission
                    ↓           ↓                            ↓
               reflector    mutator                     credit/deny
```

Each persona runs this pipeline independently. `comms_operator` is always active; others sleep until @mentioned or on first boot.

## Roster (6 personas)

| Slot | Persona | Mission |
|------|---------|---------|
| n1 | architect | Design refactors, code structure decisions |
| n2 | implementor | Execute code changes, fix bugs |
| n3 | reviewer | Review changes, catch regressions |
| n4 | comms_operator | Route work via bus, post status, @mention others |
| n5 | devops | Git ops, branch management |
| n6 | quality_critic | Audit health, enforce standards |

## Event-Driven Sleep/Wake

- `comms_operator` — always active (orchestrator)
- All others — run one planning cycle on boot, then sleep
- Sleeping personas poll the message bus every 10s for @mentions
- When @mentioned, persona wakes and runs a full pipeline cycle
- After completing work (no active plan), persona sleeps again

## Model Profiles

Hyperparameter sets per local model, selected via CLI:

```bash
python tui.py --model-profile nemotron    # nvidia nemotron (reasoning)
python tui.py --model-profile gemma       # google gemma (fast)
python tui.py                             # auto-detect from LM Studio
```

Profiles define: temperature, top_p, top_k, repeat_penalty, seed, per-agent budgets.  
Defined in `config.py MODEL_PROFILES`. Auto-detected from model id if not specified.

## Math Stack

- **Stagnation** (0→1): progress_history window + failure_weight * failures
- **Lorenz** (chaotic): wing-cross triggers replanning
- **PID** (control): integrates stagnation → escalation thresholds

Tuning for slow LLM (20-60s responses):
- MATH_INTERVAL=12s, STAGNATION_CYCLES_WINDOW=8
- FAILURE_WEIGHT=0.12, FAILURE_CAP=0.6
- PID: Kp=1.2, Ki=0.3, Kd=0.4

**Known issue**: Math clock ticks during LLM wait time, causing false stagnation. Future fix: pause math timer during pending LLM calls.

## Message Bus

- `comms.post(from, role, text, kind)` → messages.json
- `@mention` in text → parsed to `mentions[]` list
- `format_bus_context()` → injected into planner context
- `drain_inject()` → reads inject.jsonl for external posts
- Events mirror to `events_bus.jsonl`

## Backends

- **lmstudio**: parallel HTTP calls to OpenAI-compatible API (default)
- **acp**: sequential via file lock, one kiro-cli session shared across 6 processes

## Self-Evolution

- Reflector → `RULE:` appended to planner prompt (max 6)
- Personality files get `EVOLVE:` lines (max 4)
- Mutator writes plugins to `plugins/` (hot-loaded by engine)

## Files

```
core:     main.py engine.py agents.py llm.py comms.py log.py config.py
actions:  actions.py colony_env.py python_code.py
bus:      runtime/comms/{messages.json, events_bus.jsonl, inject.jsonl}
prompts:  prompts/{planner,verifier,reflector,mutator}.txt
          prompts/personalities/{architect,implementor,reviewer,comms_operator,devops,quality_critic}.txt
schemas:  schemas/{planner,verifier,reflector,mutator,fission_judge}.json
plugins:  plugins/*.py (hot-swap, def run(board))
ui:       tui.py (fixed 45-line layout + bus console)
infra:    reactor.py acp_client.py run_test.py
```

## Process Tree

```
python tui.py --model-profile nemotron
  └── reactor.py --model-profile nemotron
        ├── main.py [n1 architect]      --model-profile nemotron
        ├── main.py [n2 implementor]    --model-profile nemotron
        ├── main.py [n3 reviewer]       --model-profile nemotron
        ├── main.py [n4 comms_operator] --model-profile nemotron
        ├── main.py [n5 devops]         --model-profile nemotron
        └── main.py [n6 quality_critic] --model-profile nemotron
```

## Colony Rules

1. NEVER create new .py files — modify existing only
2. Bus @mentions for coordination
3. `py_compile` before commit
4. Self-review: read own logs, fix own errors
5. No env vars for config — use CLI args only
