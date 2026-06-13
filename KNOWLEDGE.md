# KNOWLEDGE — endgame-ai Colony (grok-dev)

Single source of truth for architecture, blackboard protocol, and research mapping.

## Process tree

```
python tui.py --model-profile nemotron
  └── reactor.py
        ├── s1 comms_operator  (MoE router, pri=1)
        ├── s2 architect         (worker, pri=0 until routed)
        ├── s3 implementor
        ├── s4 reviewer
        └── s5 devops
```

Branch: **grok-dev** (TUI fix + orchestrator + bus v1 + MoE loop)

## Five research pillars → code map

| Paper | Concept | Implementation |
|-------|---------|----------------|
| MoE (Bause 2026) | Softmax gating network | `engine._moe_route()` + `comms.softmax_route()` + `comms.route()` |
| Blackboard (CAS 2025) | Shared coordination space | `comms.py` v1 envelope, `messages.json` + `events_bus.jsonl` |
| Pressure fields (Rodriguez 2026) | Stagnation, velocity, escalation | `engine._update_pressure()` + `STUCK_TICKS_ESCALATE` → `moe.escalate` |
| AgentBreeder (Oxford 2026) | Scaffold evolution | `kind=evolve` reserved; `reflector`/`mutator` schemas ready; plugins hot-swap |
| Orchestrator pattern | One LLM gate at a time | `LLM_MAX_CONCURRENT=1`, workers idle until `route`/`request` inbox |

## Blackboard protocol v1

**Envelope** (every entry):

```
v, id, ts, from, slot, kind, pri, mentions?, to?, text, payload
```

Schema: `schemas/bus_v1.json`

### Stores

| File | Layer | Append |
|------|-------|--------|
| `runtime/comms/messages.json` | Intent | array trim 200 |
| `runtime/comms/events_bus.jsonl` | Observation | jsonl trim 500 |
| `runtime/comms/control.jsonl` | Reactor commands | drain each 5s |
| `runtime/comms/inject.jsonl` | Human/TUI inject | drain each cycle |

### Kinds

| kind | Writer | payload schema | Purpose |
|------|--------|----------------|---------|
| `message` | anyone | free | chat |
| `ping` | auto from @mention | — | wake persona |
| `request` | comms, actors | `{to, status, goal?}` | assign task |
| `route` | comms_operator | `schemas/route.json` | MoE gate decision |
| `telemetry` | beacon plugin | `schemas/telemetry.json` | pressure snapshot |
| `event` | log.mirror | `{phase, ...}` | pipeline mirror |
| `evolve` | mutator (future) | `{target, action, fitness?}` | AgentBreeder |
| `verdict` | verifier | `{verdict, evidence}` | audit result |
| `status` | reactor/tui | `{action, ...}` | control channel |

### MoE signals

- **power** = confidence = `1 - stagnation`
- **velocity** = `prev_stag - stag` (positive = improving)
- **stuck** = `stag >= 0.7` AND `|vel| <= 0.01` for `STUCK_TICKS_ESCALATE` (5) readings

### MoE cycle (`engine._moe_route`, every 20s)

1. `colony_state()` — latest telemetry per persona
2. Track stuck ticks per worker
3. If stuck → `route(escalate=True)` + `post_control(reassign)` → reactor swaps slot persona
4. Else → `route()` to highest-power worker for maintenance

Workers wake via `pending_for()` on `route` kind (inbox includes `KIND_ROUTE`).

## Prompt ↔ schema traceability

| Stage | Prompt | Schema | Persona overlay |
|-------|--------|--------|-----------------|
| planner | `prompts/planner.txt` | `schemas/planner.json` | `prompts/personalities/*.txt` |
| verifier | `prompts/verifier.txt` | `schemas/verifier.json` | — |
| reflector | `prompts/reflector.txt` | `schemas/reflector.json` | plugin (future) |
| mutator | `prompts/mutator.txt` | `schemas/mutator.json` | plugin (future) |
| fission_judge | — | `schemas/fission_judge.json` | not in pipeline yet |
| blackboard | `comms.py` docstring | `schemas/bus_v1.json` | — |
| route | `comms_operator.txt` | `schemas/route.json` | — |
| telemetry | — | `schemas/telemetry.json` | — |

## Actor sandbox (`colony_env.py`)

Pre-imported in `run_python()`:

- `bus_post`, `bus_id`, `bus_request`, `bus_route`
- `Path`, `subprocess`, `os`, `sys`, `json`, `time`

## Config knobs (`config.py`)

| Key | Default | Meaning |
|-----|---------|---------|
| `COMMS_ROUTE_INTERVAL` | 20s | MoE routing cadence |
| `STAG_ESCALATE` | 0.7 | Escalation threshold |
| `VEL_STUCK` | 0.01 | Zero-progress velocity |
| `STUCK_TICKS_ESCALATE` | 5 | Stuck readings before reassign |
| `MOE_GATE_MIN` | 0.10 | Min softmax weight to route |
| `LLM_MAX_CONCURRENT` | 1 (nemotron) | Orchestrator LLM gate |

## Model profiles

```bash
python tui.py --model-profile nemotron   # thinking on, 1 concurrent, 600s timeout
python tui.py --model-profile gemma      # thinking off, 2 concurrent
python tui.py --backend acp              # sequential WSL/Kiro lock
```

## Event phases (session JSONL)

Per-slot: `sessions/*/events-child-sN.jsonl`

Key phases: `start`, `schedule`, `planner.pending`, `plan`, `actor`, `verify`, `fission`, `pressure`, `moe.route`, `moe.escalate`, `interrupt`, `stop`

Mirrored to `events_bus.jsonl` as `kind=event`.

## What's not built yet

- `evolve` kind writer (AgentBreeder loop)
- reflector/mutator in pipeline (schemas + prompts exist)
- fission_judge LLM (currently deterministic +1)
- quality_critic in default slots (available via MoE reassign)