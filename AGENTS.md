# AGENTS.md — Colony Architecture Map

## Protocol

Every agent implements: `name`, `reads` (board keys), `run(ctx) → {writes, next, phase, data}`

## Pipeline

```
[math thread]  stagnation → lorenz → PID
                    ↓
[main loop]   scheduler → planner → actor → verifier → fission_judge → fission
                    ↓           ↓                            ↓
               reflector    mutator                     credit/deny
```

## Roster (6 agents)

| Slot | ID | Branch | Mission |
|------|----|--------|---------|
| n1 | architect | colony/architect | Design refactors, code structure |
| n2 | implementor | colony/implementor | Execute code changes, fix bugs |
| n3 | reviewer | colony/reviewer | Review changes, catch regressions |
| n4 | comms_operator | colony/comms | Route work, status updates |
| n5 | devops | colony/devops | Git ops, branch hygiene |
| n6 | quality_critic | colony/quality | Audit, enforce standards |

## Colony Rules

1. NEVER create new .py files
2. Commit to `colony/{personality}` branch
3. `py_compile` before commit
4. Bus @mentions for coordination
5. Self-review: read own logs, fix own errors

## Math Stack

- **Stagnation** (0→1): progress_history window + failure_weight * failures
- **Lorenz** (chaotic): wing-cross triggers replanning
- **PID** (control): integrates stagnation → escalation thresholds

Tuning for slow LLM (20-60s responses):
- MATH_INTERVAL=12s, STAGNATION_CYCLES_WINDOW=8
- FAILURE_WEIGHT=0.12, FAILURE_CAP=0.6
- PID: Kp=1.2, Ki=0.3, Kd=0.4

## Bus

- `comms.post(from, role, text, kind)` → messages.json
- `@mention` in text → parsed to `mentions[]` list
- `format_bus_context()` → injected into planner context as "MESSAGE BUS"
- `drain_inject()` → reads inject.jsonl for external posts
- Events mirror to `events_bus.jsonl`

## Backends

- **lmstudio**: parallel HTTP calls to OpenAI-compatible API
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
desktop:  observer.py win32.py desktop.py (available but unused by default)
ui:       tui.py (spectrogram + bus console)
infra:    reactor.py acp_client.py run_test.py
```
