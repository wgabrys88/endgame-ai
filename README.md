# endgame-ai

A local multi-agent colony: five Python processes, one local small model, a blackboard, pressure math, and a breeding reactor that decides which behaviors survive.

The LLM is not the organism. The deterministic Python loop is the organism: pressure updates, MoE routing, blackboard state, plugin execution, verification, and breeder scoring run outside the model.

Current work branch: `unify-rewrite`.

## Quick Start

```bash
git checkout unify-rewrite && git pull
python tui.py --model-profile nemotron
```

Profiles:

| Profile | Use |
|---|---|
| `nemotron` | Default maintenance, LM Studio max concurrent predictions = 1 |
| `nemotron_parallel` | Burst validation, LM Studio max concurrent predictions = 5 |
| `gemma` | Faster alternate profile without thinking |
| `--backend acp` | Sequential ACP backend |
| `--gui` | Enables desktop observation/actions by writing `gui_mode` |
| `--unconstrained` | Operator mode: GUI + relaxed planner decline; pri=3 human delivery without `@colony` |

TUI controls: Enter sends a human message, `f` cycles phase filters, `1`-`5` select `all`/`verify`/`breed`/`human`/`error`, `g` toggles GUI mode, Space toggles pause, `q` exits, `@persona message` targets a worker.

Human steering: TUI posts `from=human`, pri=3. Workers receive human goals via `comms.inbox_match` (mention, `@colony`, or pri=3 broadcast). `@colony` still helps routing clarity but is no longer required for delivery. Declines and max-retry exhaustion post at pri=0 with `human_ack` so they do not re-interrupt the colony. Pri=3 changes the active goal, not schemas, verifier/fission gates, or file rules unless `--unconstrained` is on. See `OBSERVATIONS.md` for session evidence.

## Architecture

```text
python tui.py --model-profile nemotron_parallel --gui
  -> reactor.py
       s1 comms_operator  fixed MoE router
       s2 architect       worker
       s3 implementor     worker
       s4 reviewer        worker
       s5 devops          worker
```

Worker pipeline:

```text
scheduler -> planner -> actor -> verifier -> fission_judge -> reflector -> mutator
```

Coordination is blackboard-only through `comms.py`. Personas do not call each other directly. The comms operator routes with softmax over live pressure telemetry; workers idle until routed or interrupted by a human message.

## Research Map

| Source | Project interpretation |
|---|---|
| Multi-Agent Systems are Mixtures of Experts, Bause et al., arXiv:2605.25929, https://arxiv.org/abs/2605.25929 | Route work by observable confidence/power instead of static roles |
| Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture, Han and Zhang, arXiv:2507.01701, https://arxiv.org/abs/2507.01701 | Shared blackboard, repeated selection/execution, no direct agent chat |
| Emergent Coordination in Multi-Agent Systems via Pressure Fields and Temporal Decay, Rodriguez, arXiv:2601.08129, https://arxiv.org/abs/2601.08129 | Pressure gradients and temporal decay replace manager hierarchy |
| AgentBreeder, Rosser and Foerster, arXiv:2502.00757, https://arxiv.org/abs/2502.00757 | Evolutionary scaffold search with safety/capability tradeoffs |
| Engineering Robustness into Personal Agents with the AI Workflow Store, arXiv:2605.10907, https://arxiv.org/abs/2605.10907 | Real agents need hardened workflows, tests, and traceable reusable behavior instead of only on-the-fly plans |

Note: the requested "Oxford 2026 AgentBreeder" and exact "Beyond the Agentic Loop 2025" labels were not verified on arXiv during the 2026-06-14 review. The verified AgentBreeder paper is arXiv:2502.00757.

## Golden Run (primary evidence)

**Session `20260614_132940`** — 1h49m live human-steered run. Tag: `golden-run-20260614`.

| Item | Result |
|---|---|
| Baseline commit | `c897385` |
| Profile | `nemotron_parallel`, MC=5 |
| Events | 4,137 |
| Verify confirmed | 32 |
| Fission credit | 0 (31 deny — fail-closed) |
| Breeder | 91 evict, 13 trial, 23 neutral, 6 regress |
| Human interrupts | 10 (pri=3) |

**Documentation:** `sessions/20260614_132940/README.md` (forensic), `ENDGAME_GOLDEN_RUN.html` (interactive), `AGENTS.md` (handover + fix roadmap).

## Current Validation (10-minute smoke)

Prior 10-minute validation:

| Item | Result |
|---|---|
| Baseline commit before autonomous run | `8cd57b6` (`Remove dead mutator fallback shims`) |
| Mode | `nemotron_parallel`, GUI mode enabled, LM Studio at `localhost:1234` |
| Model observed | `nvidia-nemotron-3-nano-4b@q6_k_xl` |
| Session | `sessions/20260614_112843` |
| Session events | 728 |
| LLM responses with reasoning | 46/46 |
| Planner errors | 1 |
| Plans | 16 |
| Confirmed verifications | 7 |
| Fissions | 5 |
| Actor ok/fail | 11 ok / 4 fail |
| MoE routing | 29 routes, 1 escalation |
| Breeder outcomes | 8 selection outcomes: 4 improve, 3 neutral, 1 regress |
| Breeder audit | `closed_loop: yes` |

The run also proved selection pressure can reject bad self-modification. The colony patched `plugins/telemetry.py` into a no-op during the run; review removed that dead plugin afterward and kept `plugins/comms_beacon.py` as the protected telemetry source.

Follow-up architecture work on 2026-06-14 added persistent breeder memory in `runtime/breed_archive.json`. The reactor now loads elite niches, survivor scores, slot survivors, and evictions at boot, saves them after selection feedback, and mirrors archive load/save as `breed.archive` bus evidence.

## Useful Commands

```bash
python comms.py state
python comms.py breeder
python agents.py --fission-smoke
python reactor.py --archive-smoke
python reactor.py --breed-improve-smoke
python -m py_compile reactor.py agents.py comms.py colony_env.py config.py actions.py tui.py
```

If `python` is not on PATH on this machine, use:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -m py_compile reactor.py agents.py comms.py colony_env.py config.py actions.py tui.py
```

## Known Bottlenecks

- Persistent elite archive is implemented; restart survival and long-run MAP-Elites convergence are still not proven by a long autonomous run.
- `python agents.py --fission-smoke` deterministically checks the verifier -> fission -> breeder retain path for a durable file milestone without calling the LLM.
- `python reactor.py --archive-smoke` deterministically checks archive save/load/respawn selection, but it is not a substitute for restart survival under a long autonomous run.
- `python reactor.py --breed-improve-smoke` deterministically checks `breed.improve` scoring from improved telemetry, but it is not a substitute for long-run MAP-Elites convergence.
- Reflection now fails closed with `reflect.error` when reflector JSON is invalid or incomplete.
- Fission credit now fails closed: invalid fission-judge JSON denies credit instead of retaining behavior.
- LLM transport failure now returns empty output instead of a fabricated planner `done` response.
- Browser plugin startup is currently blocked in this Windows sandbox with `CreateProcessAsUserW failed: 5`; GUI validation was performed through `gui_mode` and `observer.py`, not through the in-app Browser surface.
