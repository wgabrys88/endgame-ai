# KNOWLEDGE — endgame-ai Colony

Architecture and protocol reference. Humans: `README.md`. AI tools: **`AGENTS.md` first**, then this file when editing `comms.py`, `engine.py`, `llm.py`, or schemas.

**Tip:** `grok-dev` @ reasoning + KV-stable prompts (2026-06-14).

## Process tree

```
python tui.py --model-profile nemotron [--gui]
  └── reactor.py
        ├── s1 comms_operator  (MoE router, fixed)
        ├── s2 architect
        ├── s3 implementor
        ├── s4 reviewer
        └── s5 devops
```

## Five research pillars → code

| Paper | Concept | Implementation |
|-------|---------|----------------|
| MoE (Bause 2026) | Softmax gating | `engine._moe_route()` + `comms.softmax_route()` |
| Blackboard (CAS 2025) | Shared coordination | `comms.py` v1 |
| Pressure fields (Rodriguez 2026) | Stagnation, escalation | `engine._update_pressure()` |
| AgentBreeder (Oxford 2026) | Evolution scaffold | reflector, mutator, reactor elites/trials |
| Orchestrator pattern | One LLM gate | `LLM_MAX_CONCURRENT=1` + `runtime/.lmstudio.lock` |

## LLM layer (`llm.py`, `agents.py`, `config.py`)

### Prompt shape (KV-stable)

| Message | Contents | Must NOT contain |
|---------|----------|------------------|
| **system** | Static role prompt (`prompts/<role>.txt`) | Persona, bus, goal, JSON schema |
| **user** | Schema contract header + task state | — |

Helpers: `_stable_system()`, `_user_with_schema()`, `_SCHEMA_USER_HEADERS` in `agents.py`.

### Reasoning capture

- `call_llm()` returns `LLMResult(text, reasoning, reasoning_tokens, …)`
- Sources: API `reasoning_content`, `` blocks, JSON preamble before `{`
- Logged: `llm.request`, `llm.response`, and phase events (`plan`, `verify`, `reflect`, `mutate`, `fission`) via `_llm_event_data()`
- Cap: `LLM_REASONING_LOG_MAX` (default 12000 chars in session JSONL)

### Reasoning-aware prompts

- **System** (`prompts/<role>.txt`): role rules + "reasoning trace vs JSON output" split
- **User** (`_user_with_schema`): `_REASONING_CONTRACT` + schema header + task state
- **Personas** (`prompts/personalities/*.txt`): one line — reasoning logged, JSON is output only

### LM Studio API parameters (all wired in `llm.call_llm`)

| Parameter | nemotron | Purpose | Tuning note |
|-----------|----------|---------|-------------|
| `messages` | system + user | KV-stable system; dynamic user | — |
| `temperature` | 0.12 | JSON reliability | Lower = more deterministic; avoid >0.3 for structured work |
| `top_p` | 0.88 | nucleus sampling | Slightly below 1.0 reduces rambling |
| `top_k` | 40 | tail cutoff | 20–40 typical for Nemotron |
| `max_tokens` | role `BUDGET` | Output cap | Separate from `thinking_budget` |
| `thinking_budget` | role `THINKING_BUDGET` | Reasoning tokens | Planner highest; verifier lowest |
| `enable_thinking` | true | Reasoning channel | Requires LM Studio reasoning stripping **off** |
| `stream` | false | Full response parse | Must stay false for colony |
| `stop` | `[]` | Early stop sequences | Empty — JSON schema handles shape |
| `presence_penalty` | 0.0 | Repeat topic penalty | Keep 0 — JSON keys repeat legitimately |
| `frequency_penalty` | 0.0 | Repeat token penalty | Keep 0 for JSON |
| `repeat_penalty` | 1.06 | llama.cpp anti-loop | 1.05–1.08 sweet spot |
| `seed` | 3407 | Reproducibility | -1 = random per call |
| `logit_bias` | `{}` | Token forcing | Unused; reserve for emergency token suppression |
| `response_format` | off (`LLM_API_SCHEMA=false`) | Constrained JSON | On = faster JSON, kills `reasoning_content` |

Logged on `llm.request`: temperature, top_p, top_k, max_tokens, thinking_budget, seed, concurrent_gate, global_lock.

### Nemotron profile flags

| Key | Value | Notes |
|-----|-------|-------|
| `LLM_API_SCHEMA` | `false` | Schema in user message; reasoning in `reasoning_content` |
| `LLM_THINKING_ENABLED` | `true` | Per-role `THINKING_BUDGET` |
| `LLM_MAX_CONCURRENT` | `1` | Match LM Studio Max Concurrent Predictions |
| `LMS_USE_GLOBAL_LOCK` | `true` | Cross-process lock at `runtime/.lmstudio.lock` |
| `nemotron_parallel` | MC=5, lock off | **Experimental** — validated 2026-06-14 |

**Open (not settled):** Whether to enable API schema for stricter JSON at the cost of empty reasoning; whether every pipeline stage should attach full reasoning to bus mirror; whether Unified KV Cache helps when MC=1 (user disabled it — hypothesis: Unified KV mainly helps parallel slots).

### JSON extraction

`extract_json()` strips thinking, then `json.JSONDecoder().raw_decode()` for first object (handles preamble + trailing prose).

## Blackboard protocol v1

**Envelope:** `v, id, ts, from, slot, kind, pri, text, payload` — schema `schemas/bus_v1.json`

### Stores

| File | Layer | Trim |
|------|-------|------|
| `runtime/comms/messages.json` | Intent | 200 |
| `runtime/comms/events_bus.jsonl` | Observation | 500 |
| `runtime/comms/control.jsonl` | Reactor commands | drained 5s |
| `runtime/comms/inject.jsonl` | Human/TUI | drained each cycle |

### Key kinds

`message`, `ping`, `request`, `route`, `telemetry`, `event`, `evolve`, `verdict`, `status`

MoE: `colony_state()`, `softmax_route()`, `route()`, `post_control()`, `human_task_active()`

## Pressure math

```
fail_pressure = min(1.0, failures * 0.15)
time_pressure = min(1.0, max(0, since_fission - 60) / 240)
stagnation = min(1.0, fail_pressure * 0.6 + time_pressure * 0.4)
velocity = prev_stag - stagnation
power = 1.0 - stagnation
```

**Stuck:** `stag >= 0.7` AND `|vel| <= 0.01` for 5 MoE cycles → escalate + reassign.

## AgentBreeder loop

```
verifier denial → reflector → mutator (≥ MUTATE_AFTER_FAILURES)
  → patch_plugin → post_evolve → reactor breed.elite / breed.evict / trial
  → after BREED_TRIAL_EVAL_SECONDS: breed.improve | breed.regress | breed.neutral
```

Audit: `python comms.py breeder`

## Prompt ↔ schema

| Stage | Prompt | Schema (user header + optional API) |
|-------|--------|-------------------------------------|
| planner | `prompts/planner.txt` | `schemas/planner.json` |
| verifier | `prompts/verifier.txt` | `schemas/verifier.json` |
| reflector | `prompts/reflector.txt` | `schemas/reflector.json` |
| mutator | `prompts/mutator.txt` | `schemas/mutator.json` |
| fission_judge | `prompts/fission_judge.txt` | `schemas/fission_judge.json` |

Personas: `prompts/personalities/*.txt` — in **user** message only.

## Event phases (session JSONL)

Path: `sessions/<timestamp>/events-child-sN.jsonl`

| Tier | Phases |
|------|--------|
| Pillar | `moe.route`, `pressure`, `plan`, `actor`, `verify`, `fission`, `reflect`, `mutate` |
| LLM debug | `llm.request`, `llm.response`, `prompt_signature`, `prompt_drift` |
| Breeder | `evolve` (bus), reactor `breed.*` |

Bus mirror skips: `schedule`, `plugin.telemetry`, `plugin.web_sentinel`

## Model profiles

```bash
python tui.py --model-profile nemotron
python llm.py bench
```

**nemotron (optimized):** temp 0.15, seed 3407, thinking_budget 1536, `LLM_API_SCHEMA=false`, role budgets in `config.BUDGET`.

**LM Studio (manual):** MC=1 + reasoning stripping off for default `nemotron`.

### Parallel LLM (experimental `nemotron_parallel`)

The blackboard makes parallel inference plausible: slots wake on independent inbox messages.

```bash
python tui.py --model-profile nemotron_parallel
```

| Colony | LM Studio (required) |
|--------|----------------------|
| `LLM_MAX_CONCURRENT=5` | Max Concurrent Predictions **5** |
| `LMS_USE_GLOBAL_LOCK=false` | Unified KV Cache **on** (recommended for MC>1) |
| Lower per-role `BUDGET` / `THINKING_BUDGET` | More VRAM per slot |

**Validated** (`sessions/20260614_031018`): 5 human injects → 27 `llm.request`, all 5 slots, max 5 concurrent within 60s. Use for multi-`@persona` bursts; `nemotron` (MC=1) for idle maintenance.

## GUI mode

| Mode | Trigger | Behavior |
|------|---------|----------|
| Safe (default) | no `gui_mode` file | Declines GUI goals |
| GUI | `--gui`, `g`, or `enable_gui()` | `observer.py` context in planner user message |

## Not built yet

- Consistent multi-cycle `breed.improve` (GOAL)
- LLM fission_judge (deterministic fallback only)
- KV/Unified-KV A/B evidence for MC=1 workload
- Persistent elite archive across reactor restarts