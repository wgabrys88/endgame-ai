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
4. If `human_task_active()` → skip maintenance route (`moe.yield`); human pri=3 yields LLM + bus
5. Else → `route()` to highest softmax-power worker (if weight ≥ `MOE_GATE_MIN`)

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

**GUI blocked** (`python_code.validate_python`): `notepad`, `calc`, `mspaint`, `os.startfile`, `pyautogui`, etc. Colony has no GUI agent — planner must decline GUI goals via `bus_post` or `goal_needs_gui()` short-circuit in `agents.py`.

Actor timeout: `actions.run_python` runs `taskkill /F /T` on runner PID to kill orphan GUI children.

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
| `HUMAN_GOAL_MAX_DENIALS` | 3 | Stop replanning human pri=3 after N failures |
| `PLANNER_ERROR_RAW_MAX` | 2000 | Session log cap for `planner.error` raw LLM |

## Model profiles

```bash
python tui.py --model-profile nemotron   # thinking on, 1 concurrent, 600s timeout
python tui.py --model-profile gemma      # thinking off, 2 concurrent
python tui.py --backend acp              # sequential WSL/Kiro lock
```

## Event phases (session JSONL)

Per-slot: `sessions/<timestamp>/events-child-sN.jsonl`  
Operator slot: `events-child-s1.jsonl` holds `moe.route` / `moe.yield` / `moe.escalate`.

### Log tiers (vision vs debug noise)

| Tier | Phases | Keep? | Where |
|------|--------|-------|-------|
| **Pillar** | `moe.route`, `moe.yield`, `moe.escalate`, `pressure`, `interrupt`, `plan`, `actor`, `verify`, `fission` | **Yes** — proves MoE + pressure + pipeline | Session JSONL; pillar phases also on `events_bus.jsonl` |
| **Pipeline** | `schedule`, `planner.pending`, `planner.error`, `human.decline` | Yes for debugging | Session JSONL; `schedule` skipped on bus |
| **Noise** | `plugin.web_sentinel`, `plugin.telemetry` | Optional — not pillar-critical | Session only (`_SKIP_PHASES` — not mirrored to bus) |

`moe.route` every ~20s on s1 and `pressure` every ~10 cycles (~20s) are **intentional**: live-test pass criteria and Rodriguez/Bause telemetry. Noisy for humans, required for proving the math loop.

`plugin.web_sentinel` (~30s/slot) is connectivity hygiene only — safe to throttle further later; does not affect bus or MoE.

### Phase list

`start`, `schedule`, `planner.pending`, `planner.error`, `plan`, `actor`, `verify`, `fission`, `pressure`, `moe.route`, `moe.yield`, `moe.escalate`, `interrupt`, `human.decline`, `stop`

Bus mirror skips: `schedule`, `plugin.telemetry`, `plugin.web_sentinel` (`comms._SKIP_PHASES`).

## Not built yet

- `evolve` kind writer (AgentBreeder loop)
- reflector/mutator in pipeline
- LLM fission_judge
- quality_critic in default slot rotation