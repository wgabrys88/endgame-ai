# KNOWLEDGE - endgame-ai Colony

Technical reference for agents editing the colony. Read `AGENTS.md` first, then this file when touching `comms.py`, `engine.py`, `agents.py`, `reactor.py`, `llm.py`, prompts, schemas, or plugins.

## Verified Research Inputs

The 2026-06-14 web review found these authoritative or closest matching sources:

| Source | Mechanism | Code mapping |
|---|---|---|
| arXiv:2605.25929, https://arxiv.org/abs/2605.25929, "Multi-Agent Systems are Mixtures of Experts: Who Becomes an Influencer?" | Multi-agent deliberation behaves like input-dependent MoE; routing should reflect observable competence/confidence | `comms.softmax_route()`, `engine._moe_route()` |
| arXiv:2507.01701, https://arxiv.org/abs/2507.01701, "Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture" | Agents share state through a blackboard; action selection is based on blackboard contents and repeats until consensus | `comms.py`, `runtime/comms/messages.json`, `runtime/comms/events_bus.jsonl` |
| arXiv:2601.08129, https://arxiv.org/abs/2601.08129, "Emergent Coordination in Multi-Agent Systems via Pressure Fields and Temporal Decay" | Pressure gradients outperform hierarchy in the cited meeting-room benchmark: 48.5% vs 1.5% aggregate solve rate | `engine._update_pressure()`, pressure fields in telemetry payloads |
| arXiv:2502.00757, https://arxiv.org/abs/2502.00757, "AgentBreeder" | Multi-objective self-improving evolutionary search over scaffolds; safety and capability both matter | `agents.MutatorAgent`, `reactor.process_evolve_candidates()`, selection trials |
| arXiv:2605.10907, https://arxiv.org/abs/2605.10907, "Engineering Robustness into Personal Agents with the AI Workflow Store" | Robust agents need hardened workflows, reusable behavior, deterministic checks, and traceability | py_compile gates, schemas, session JSONL, breeder evidence |

The exact labels "Oxford 2026 AgentBreeder" and "Beyond the Agentic Loop 2025" were not verified from the public web search; docs should use the verified arXiv facts above.

## Process Tree

```text
python tui.py --model-profile nemotron_parallel --gui
  -> reactor.py
       s1 comms_operator  fixed MoE router
       s2 architect       worker slot
       s3 implementor     worker slot
       s4 reviewer        worker slot
       s5 devops          worker slot
```

Slot 1 is never reassigned. Slots 2-5 can respawn or be reassigned by MoE escalation.

## Control Loop

`engine.run()` owns the persona loop:

```text
interrupt check
plugin hot-swap
pressure update
MoE route if comms_operator
scheduler -> planner -> actor -> verifier -> fission_judge -> reflector -> mutator
```

The model is called only by planner, verifier, fission judge, reflector, and mutator. Routing, pressure, plugin execution, breeder scoring, bus persistence, and process management are deterministic Python.

## Blackboard Protocol

Protocol version: v1.

Envelope fields:

```text
v, id, ts, from, slot, kind, pri, text, payload, optional mentions, optional to
```

Stores:

| File | Meaning |
|---|---|
| `runtime/comms/messages.json` | Intent: messages, requests, routes, evolve candidates, status |
| `runtime/comms/events_bus.jsonl` | Observation: telemetry and mirrored phase events |
| `runtime/comms/control.jsonl` | Reactor commands |
| `runtime/comms/inject.jsonl` | Human/TUI injection |

Important kinds:

```text
message, ping, request, route, telemetry, event, beacon, evolve, verdict, status
```

## Pressure Math

Implemented in `engine._update_pressure()`:

```text
fail_pressure = min(1.0, failures * 0.15)
time_pressure = min(1.0, max(0, since_fission - 60) / 240)
stagnation = min(1.0, fail_pressure * 0.6 + time_pressure * 0.4)
velocity = prev_stag - stagnation
power = 1.0 - stagnation
```

Escalation condition:

```text
stagnation >= STAG_ESCALATE
and abs(velocity) <= VEL_STUCK
for STUCK_TICKS_ESCALATE MoE cycles
```

## Breeder Loop

Verifier/fission/mutation events produce `evolve` entries through `comms.post_evolve()`.

Reactor behavior:

```text
evolve retain/evict/patch_plugin
  -> update elite archive
  -> retain/evict survivor state
  -> start selection trial for retain and patch_plugin
  -> sample telemetry after BREED_TRIAL_EVAL_SECONDS
  -> emit breed.improve / breed.regress / breed.neutral
  -> feed outcome back into survivor fitness
```

Current scoring fields on outcome events:

```text
trial_id, trial_action, sample, max_samples,
baseline_stagnation, current_stagnation, stagnation_delta,
baseline_power, current_power, power_delta,
baseline_fissions, current_fissions, fission_delta
```

Audit command:

```bash
python comms.py breeder
```

Current proof from `runtime/comms/events_bus.jsonl` after `sessions/20260614_112843`:

```text
evolve: 8 evict=5 retain=3
breed: 21
selection outcomes: 8 breed.improve=4 breed.neutral=3 breed.regress=1
best_stagnation_delta=0.0900
best_power_delta=0.0900
fission_delta_total=5
repeated_samples=6
closed_loop: yes
```

## LLM Layer

Stable system prompts are loaded by role from `prompts/*.txt`. Persona text, goal, schema contract, pressure, GUI observation, history, and bus context go in the user message.

Key files:

| Concern | File |
|---|---|
| Backend, reasoning capture, LM Studio/ACP | `llm.py` |
| Prompt assembly and pipeline agents | `agents.py` |
| Model profiles and budgets | `config.py` |

Important profile facts:

| Profile | Concurrency | Lock | Schema mode |
|---|---:|---|---|
| `nemotron` | 1 | global lock on | schema in user message, API schema off |
| `nemotron_parallel` | 5 | global lock off | schema in user message, API schema off |

Reasoning is captured in `LLMResult.reasoning` and mirrored in session JSONL phase data. The 10-minute run produced 46 `llm.response` events and all 46 had reasoning.

## GUI Mode

Default is safe mode: no `gui_mode` file. GUI mode is enabled by `--gui`, `g` in TUI, or `enable_gui()`.

When GUI mode is enabled:

- `agents._desktop_context()` calls `observer.observe()`.
- planner user messages receive focused window and UI element context.
- `actions.py` can use desktop verbs through `desktop.py`.

The Browser plugin was attempted during the 2026-06-14 continuation but the in-app Browser runtime could not start in this Windows sandbox (`CreateProcessAsUserW failed: 5`). The 10-minute GUI validation still used the project GUI path through `gui_mode` and `observer.py`.

## Plugins

Current tracked plugins:

| Plugin | Role |
|---|---|
| `plugins/comms_beacon.py` | Protected telemetry beacon, posts pressure snapshots |
| `plugins/fission_log.py` | Plugin-local fission memory, no file writes |
| `plugins/lessons_decay.py` | Lessons aging |
| `plugins/web_sentinel.py` | Protected connectivity sentinel |

Removed after validation:

- `plugins/telemetry.py`: the autonomous run patched it into a no-op; it was removed as a dead secondary telemetry path because `comms_beacon.py` is the real telemetry source.

Mutation safety:

- Mutator schema allows only `patch_plugin` or `none`.
- Plugin creation is not allowed.
- Existing plugin patches are AST checked, py_compile checked, and restricted to plugin-local writes.
- Protected plugins: `comms_beacon.py`, `web_sentinel.py`.

## Validation Record

10-minute run on 2026-06-14:

| Metric | Value |
|---|---:|
| Baseline commit before run | `8cd57b6` |
| Profile | `nemotron_parallel` |
| GUI mode | on |
| LM Studio model | `nvidia-nemotron-3-nano-4b@q6_k_xl` |
| Session | `sessions/20260614_112843` |
| Total child events | 728 |
| Planner errors | 1 |
| LLM responses | 46 |
| LLM responses with reasoning | 46 |
| Plans | 16 |
| Confirmed verifies | 7 |
| Fissions | 5 |
| Actor results | 11 ok / 4 fail |
| MoE routes/escalations | 29 / 1 |
| Breeder selection outcomes | 8 |

## Still Not Proven

- Persistent elite archive across reactor restarts.
- Long-run MAP-Elites convergence.
- Reflection now fails closed with `reflect.error` when reflector JSON is invalid or incomplete.
- Fission credit fallback was removed after the 10-minute run: invalid fission-judge JSON denies credit.
- LLM transport failure no longer fabricates planner `done` JSON.
- Browser-plugin validation in this desktop sandbox.
