# KNOWLEDGE — endgame-ai Colony

Architecture and protocol reference for `grok-dev`. Humans: start with `README.md`. AI tools: read `AGENTS.md` first, then use this file when editing `comms.py`, `engine.py`, or schemas.

## Process tree

```
python tui.py --model-profile nemotron
  └── reactor.py
        ├── s1 comms_operator  (MoE router)
        ├── s2 architect         (idle until routed)
        ├── s3 implementor
        ├── s4 reviewer
        └── s5 devops
```

## Five research pillars → code

| Paper | Concept | Implementation |
|-------|---------|----------------|
| MoE (Bause 2026) | Softmax gating | `engine._moe_route()` + `comms.softmax_route()` + `comms.route()` |
| Blackboard (CAS 2025) | Shared coordination | `comms.py` v1, `messages.json` + `events_bus.jsonl` |
| Pressure fields (Rodriguez 2026) | Stagnation, escalation | `engine._update_pressure()` → `moe.escalate` |
| AgentBreeder (Oxford 2026) | Scaffold evolution | `kind=evolve` reserved; reflector/mutator schemas ready |
| Orchestrator pattern | One LLM gate | `LLM_MAX_CONCURRENT=1`, workers idle until inbox |

## Blackboard protocol v1

**Envelope** (every entry):

```
v, id, ts, from, slot, kind, pri, mentions?, to?, text, payload
```

Schema: `schemas/bus_v1.json`

### Stores

| File | Layer | Trim |
|------|-------|------|
| `runtime/comms/messages.json` | Intent | 200 entries |
| `runtime/comms/events_bus.jsonl` | Observation | 500 lines |
| `runtime/comms/control.jsonl` | Reactor commands | drained each 5s |
| `runtime/comms/inject.jsonl` | Human/TUI inject | drained each cycle |

### Kinds

| kind | Writer | Payload | Purpose |
|------|--------|---------|---------|
| `message` | anyone | free | chat |
| `ping` | @mention | — | wake persona |
| `request` | comms, actors | `{to, status, goal?}` | assign task |
| `route` | comms_operator | `schemas/route.json` | MoE decision |
| `telemetry` | beacon plugin | `schemas/telemetry.json` | pressure snapshot |
| `event` | log.mirror | `{phase, ...}` | pipeline mirror |
| `evolve` | mutator (future) | `{target, action, fitness?}` | AgentBreeder |
| `verdict` | verifier | `{verdict, evidence}` | audit |
| `status` | reactor/tui | `{action, ...}` | control channel |

### MoE signals

- **power** = `1 - stagnation` (confidence)
- **velocity** = `prev_stag - stag` (positive = improving)
- **stuck** = `stag >= 0.7` AND `|vel| <= 0.01` for 5 consecutive readings

### MoE cycle (`engine._moe_route`, every 20s)

1. `colony_state()` — latest telemetry per persona
2. Increment stuck ticks per worker; reset when improving
3. If stuck ≥ 5 ticks → `route(escalate=True)` + `post_control(reassign)`
4. Else → `route()` to highest softmax-power worker (if weight ≥ `MOE_GATE_MIN`)

Workers wake via `pending_for()` on `route`, `request`, `ping`.

## Pressure math (`engine._update_pressure`)

Per cycle (not during LLM waits):

```
fail_pressure = min(1.0, failures * 0.15)
time_pressure = min(1.0, max(0, since_fission - 60) / 240)
stagnation = min(1.0, fail_pressure * 0.6 + time_pressure * 0.4)
velocity = prev_stag - stagnation
power = 1.0 - stagnation
```

Resets on fission or goal switch (temporal decay).

## Prompt ↔ schema traceability

| Stage | Prompt | Schema |
|-------|--------|--------|
| planner | `prompts/planner.txt` | `schemas/planner.json` |
| verifier | `prompts/verifier.txt` | `schemas/verifier.json` |
| reflector | `prompts/reflector.txt` | `schemas/reflector.json` (future) |
| mutator | `prompts/mutator.txt` | `schemas/mutator.json` (future) |
| fission_judge | — | `schemas/fission_judge.json` |
| route | comms_operator personality | `schemas/route.json` |
| telemetry | — | `schemas/telemetry.json` |

Persona overlays: `prompts/personalities/*.txt`

## Actor sandbox (`colony_env.py`)

Pre-imported in `run_python()`:

`bus_post`, `bus_id`, `bus_request`, `bus_route`, `Path`, `subprocess`, `os`, `sys`, `json`, `time`

## Config knobs (`config.py`)

| Key | Default | Meaning |
|-----|---------|---------|
| `COMMS_ROUTE_INTERVAL` | 20s | MoE cadence |
| `STAG_ESCALATE` | 0.7 | Escalation threshold |
| `VEL_STUCK` | 0.01 | Zero-progress velocity |
| `STUCK_TICKS_ESCALATE` | 5 | Stuck readings before reassign |
| `MOE_GATE_MIN` | 0.10 | Min softmax weight to route |
| `LLM_MAX_CONCURRENT` | 1 | Orchestrator LLM gate (nemotron) |
| `DELAY_BETWEEN_CYCLES` | 2.0s | Persona tick |
| `BUS_POLL_INTERVAL` | 3.0s | Inbox poll |

## Model profiles

```bash
python tui.py --model-profile nemotron   # thinking on, 1 concurrent, 600s timeout
python tui.py --model-profile gemma      # thinking off, 2 concurrent
python tui.py --backend acp              # sequential WSL/Kiro lock
```

## Event phases (session JSONL)

Per-slot: `sessions/*/events-child-sN.jsonl`

`start`, `schedule`, `planner.pending`, `plan`, `actor`, `verify`, `fission`, `pressure`, `moe.route`, `moe.escalate`, `interrupt`, `stop`

Mirrored to `events_bus.jsonl` as `kind=event`.

## Not built yet

- `evolve` kind writer (AgentBreeder loop)
- reflector/mutator in pipeline
- LLM fission_judge
- quality_critic in default slot rotation