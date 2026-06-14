# AGENTS.md - AI session handover for endgame-ai

Read this first when continuing the repo.

| File | Purpose |
|---|---|
| `AGENTS.md` | AI handover, current state, rules, validation record |
| `KNOWLEDGE.md` | Protocol and architecture details |
| `README.md` | Human quick start |

Work branch: `unify-rewrite`.

## Vision

Endgame: self-evolving colony on consumer hardware. Small models. Real actions. A breeding reactor selects what survives.

The LLM is a subroutine, not the organism. The organism is the deterministic Python control loop: pressure fields, MoE routing, blackboard state, process slots, plugin hot-swap, verification, and breeder scoring.

## Architecture Summary

```text
reactor.py
  s1 comms_operator  fixed, deterministic MoE router
  s2 architect       worker
  s3 implementor     worker
  s4 reviewer        worker
  s5 devops          worker
```

Worker pipeline:

```text
scheduler -> planner -> actor -> verifier -> fission_judge -> reflector -> mutator
```

Rules:

- Blackboard-only coordination through `comms.py`.
- Workers idle until routed or human-interrupted.
- `engine._update_pressure()` runs every cycle.
- `engine._moe_route()` routes from `comms_operator` without LLM calls.
- Reactor consumes `evolve` candidates and emits `breed.*` outcomes.

## Research Sources Verified 2026-06-14

| Source | Confirmed fact | Code |
|---|---|---|
| Bause et al., arXiv:2605.25929, https://arxiv.org/abs/2605.25929 | Multi-agent deliberation can be viewed as input-dependent MoE; competence is observed through proxies such as confidence | `comms.softmax_route()`, `engine._moe_route()` |
| Han and Zhang, arXiv:2507.01701, https://arxiv.org/abs/2507.01701 | Blackboard MAS shares all role messages, selects acting agents from blackboard content, repeats selection/execution | `comms.py` v1 |
| Rodriguez, arXiv:2601.08129, https://arxiv.org/abs/2601.08129 | Pressure fields beat hierarchy in cited benchmark: 48.5% vs 1.5% aggregate solve rate | `engine._update_pressure()` |
| Rosser and Foerster, arXiv:2502.00757, https://arxiv.org/abs/2502.00757 | AgentBreeder evolves scaffolds and exposes safety/capability tradeoffs | `reactor.py`, `agents.MutatorAgent` |
| arXiv:2605.10907, https://arxiv.org/abs/2605.10907 | Robust agents need hardened workflows and traceable reusable behavior beyond ad hoc loops | schemas, py_compile, session JSONL |

Unverified label corrections:

- "Oxford 2026 AgentBreeder" was not verified; public arXiv result is AgentBreeder arXiv:2502.00757.
- Exact "Beyond the Agentic Loop 2025" was not found; the closest verified source used for documentation is arXiv:2605.10907.

## Current Status

Colony Alpha is runnable and selection-loop evidence exists.

Latest important commits:

| Commit | Meaning |
|---|---|
| `0a5b128` | Closed breeder selection trial loop |
| `8cd57b6` | Removed dead mutator fallback shims before 10-minute autonomous run |

10-minute validation after `8cd57b6`:

| Item | Result |
|---|---|
| Profile | `nemotron_parallel` |
| GUI mode | on |
| LM Studio model | `nvidia-nemotron-3-nano-4b@q6_k_xl` |
| Session | `sessions/20260614_112843` |
| Child session events | 728 |
| LLM reasoning | 46/46 `llm.response` events had reasoning |
| Planner errors | 1 |
| Plans | 16 |
| Confirmed verifies | 7 |
| Fissions | 5 |
| MoE | 29 routes, 1 escalation |
| Breeder | 8 selection outcomes: 4 improve, 3 neutral, 1 regress |
| Audit | `python comms.py breeder` -> `closed_loop: yes` |

Important observation: the autonomous run patched `plugins/telemetry.py` into a no-op. That mutation was not kept. The dead secondary telemetry plugin was deleted after the run; `plugins/comms_beacon.py` remains the protected telemetry source.

## Current Files That Matter

| Layer | Files |
|---|---|
| LLM and reasoning | `llm.py`, `config.py` |
| Agents and prompts | `agents.py`, `prompts/*.txt`, `prompts/personalities/*.txt`, `schemas/*.json` |
| Blackboard | `comms.py`, `runtime/comms/*` |
| Pressure and MoE | `engine.py`, `plugins/comms_beacon.py` |
| Breeding | `reactor.py`, `agents.py`, `plugins/fission_log.py` |
| GUI | `tui.py`, `observer.py`, `actions.py`, `desktop.py`, `python_code.py`, `colony_env.py` |

## Hard Rules

1. Never create new `.py` files.
2. Only `README.md`, `KNOWLEDGE.md`, and `AGENTS.md` may be added or edited as Markdown tracked docs.
3. Runtime colony configuration belongs in CLI flags and `config.py`; `.env` is only for local LM Studio hosts.
4. Personas coordinate via the bus only.
5. After Python changes, run `python -m py_compile <changed files>`.
6. GUI default is off; use `--gui`, TUI `g`, or `enable_gui()`.
7. `reactor.is_alive()` must keep using `OpenProcess(0x1000)`.
8. Commit before long autonomous colony runs; the colony can execute real code by design.

## Validation Commands

Default smoke:

```bash
python tui.py --model-profile nemotron
python comms.py state
python comms.py breeder
```

Parallel GUI validation shape used on 2026-06-14:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -c "import log; log.cleanup_runtime()"
Set-Content -LiteralPath gui_mode -Value 1
$env:ENDGAME_BOOTSTRAPPED='1'
$env:ENDGAME_BACKEND='lmstudio'
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" reactor.py --model-profile nemotron_parallel
```

For controlled validation, start reactor hidden, inject `@architect`, `@implementor`, `@reviewer`, and `@devops` tasks through `comms.py post`, wait 10 minutes, then stop the reactor process tree.

## Cleanup Policy

Disposable:

- `__pycache__/`
- `plugins/__pycache__/`
- `gui_mode`
- empty `validation-*.out` / `validation-*.err`

Keep unless intentionally archiving or rotating evidence:

- `sessions/`
- `runtime/comms/` immediately after validation
- `ENDGAME_VISION.html`
- `lm-studio-server-log.md`
- local research/log markdown files not tracked by git

## Remaining Bottlenecks

- Persistent elite archive across reactor restarts.
- Long-run MAP-Elites convergence.
- Better semantic mutation scoring: a no-op plugin patch can be neutral over short windows and still be architecturally bad.
- Fission/reflection still include deterministic fallbacks for invalid or empty LLM output.
- Browser plugin startup is blocked in this Windows sandbox (`CreateProcessAsUserW failed: 5`), so Browser-surface validation is not complete even though GUI mode validation is.

## Handover Prompt

```text
You are continuing endgame-ai on branch unify-rewrite.

Vision: self-evolving colony on consumer hardware. Small models. Real actions.
Breeding reactor selects what lives. The LLM is a subroutine inside deterministic
loops, not the organism.

Read AGENTS.md, then KNOWLEDGE.md, then README.md.

Current proof: session 20260614_112843 was a 10-minute nemotron_parallel GUI run
after commit 8cd57b6. It produced 728 child events, 46/46 LLM reasoning traces,
5 fissions, 29 MoE routes, 1 escalation, and breeder closed_loop=yes with
8 selection outcomes. The run also exposed and removed a dead telemetry plugin.

Hard rules: no new .py files, bus-only coordination, config via config.py/CLI,
py_compile changed Python, commit before long autonomous runs.

Do not claim MAP-Elites convergence or persistent elite archive until proven.
```
