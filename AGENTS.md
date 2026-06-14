# AGENTS.md — AI session handover (endgame-ai)

**Read this first** if you are any AI continuing work on this repo (Codex, Cursor, Grok, OpenCode, or other).

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | **You** — vision, distance-to-goal, rules, handover prompt |
| `KNOWLEDGE.md` | Protocol and architecture (cite when editing comms/engine/llm) |
| `README.md` | Human quick start only |

**Trunk branch:** `unify-rewrite` @ `2b20732` (2026-06-14)  
**Grok workspace memory:** `~/.grok/memory/wgabrys88-endgame-ai/MEMORY.md` (not in git)  
**Human vision doc:** `ENDGAME_VISION.html` (local, not in git — read for paper refs and inception layers)

---

## The endgame vision

**Endgame:** Self-evolving colony on consumer hardware. Small models. Real actions. Breeding reactor selects what lives.

### Core insight

The LLM is **not** the organism. It is a subroutine inside a deterministic Python control loop. Pressure math, MoE routing, and priority run every cycle regardless of LLM state. Math agents are the immune system — chaos with guardrails.

### Why this architecture (not the usual patterns)

| Not this | Because |
|----------|---------|
| RAG memory | Blackboard is alive — decays, evicts, routes. Not frozen embeddings. |
| One big agent | Small model cannot run 5 planners; orchestrator gates one LLM at a time (or MC=5 burst). |
| Provider agents | Full Python on local machine: git, files, subprocess. No cage. |
| Manager/worker hierarchy | Pressure fields outperform hierarchy (Rodriguez 2026: 48.5% vs 1.5%). |

### Five papers → your code

| Paper | Concept | Code |
|-------|---------|------|
| Bause 2026 — MAS as MoE | Softmax gating on confidence | `engine._moe_route()`, `comms.softmax_route()` |
| Han & Zhang CAS 2025 — Blackboard | Shared coordination, no direct agent talk | `comms.py` v1 (`messages.json`, `events_bus.jsonl`) |
| Rodriguez 2026 — Pressure fields | Stagnation, velocity, escalation | `engine._update_pressure()` |
| Oxford 2026 — AgentBreeder | MAP-Elites evolution scaffold | `reactor.py` elites/trials; reflector/mutator pipeline |
| Orchestrator pattern 2025 | Workers idle until routed | `LLM_MAX_CONCURRENT` + `runtime/.lmstudio.lock` |

### Inception layers (outside → inside)

```
L0 Vision        → living organism on consumer hardware
L1 Reactor       → reactor.py keeps 5 slots alive; breeding chamber
L2 Blackboard    → comms.py v1 intent + observation stores
L3 MoE gate      → comms_operator routes by softmax(power)
L4 Pressure math → stagnation/velocity every cycle; escalation at stag≥0.7
L5 Orchestrator  → LLM gated; workers idle until inbox has work
L6 Pipeline      → scheduler→planner→actor→verifier→fission→[reflect→mutate]
L7 Future        → consistent breed.improve; MAP-Elites convergence; plugin hot-swap
```

---

## How far from the endgame

Honest scorecard (2026-06-14, post branch consolidation):

| Layer | Status | ~% |
|-------|--------|-----|
| Colony skeleton (5 slots, reactor, no false respawn) | **Done** | 95 |
| Blackboard v1 + MoE closed loop | **Done** | 90 |
| Pressure + escalation + human yield | **Done** | 85 |
| Orchestrator + KV-stable prompts + reasoning capture | **Done** | 85 |
| Live Nemotron validation (MC=1 + MC=5 burst) | **Validated** | 80 |
| AgentBreeder scaffold (reflect/mutate/evolve/trials) | **Wired** | 70 |
| `breed.improve` multi-cycle evidence | **Once only** | 35 |
| MAP-Elites / persistent elites / long-run convergence | **Not proven** | 15 |

**Colony Alpha milestone:** ~**88%** — runnable, testable, papers mapped to code.  
**Endgame vision milestone:** ~**55%** — breeding must produce repeatable logged improvement, not one-off events.

### What works (verified `unify-rewrite` 2026-06-14)

- 5 slots without false respawn; MoE closed loop + human yield
- KV-stable planner/verifier; reasoning in session JSONL
- `nemotron` (MC=1) + `nemotron_parallel` (MC=5, validated `sessions/20260614_032059`)
- AgentBreeder: reflector, mutator, evolve, elites, trials; `breed.improve` ≥1 historical run
- GUI opt-in; `python llm.py bench`, `python comms.py breeder`

### Not built / not proven (do not claim done)

- **GOAL:** Consistent multi-cycle `breed.improve` with pressure/fission deltas
- Unified KV policy with A/B evidence for MC=1
- LLM-only fission_judge (deterministic fallback exists)
- MAP-Elites convergence over long runs
- Persistent elite archive across reactor restarts

---

## Branch model

```
REMOTE (GitHub):

    main ─────────────► a439a0d  (GitHub default label)
         |
         |  +152 commits colony work
         v
    unify-rewrite ────► 2b20732  ★ WORK HERE ★

    grok-dev, codex-dev  → deleted (2026-06-14 consolidation)
```

**Rules**

- Daily work and commits: **`unify-rewrite`**
- Tool-specific session: `git checkout -b <name>` from `unify-rewrite` tip
- One AI agent commits at a time on the shared branch
- Do **not** merge colony work into `main` without explicit human direction
- Ask human before creating long-lived parallel branches

---

## What this project is (runtime)

Five parallel **slots** (OS processes). Each slot runs one **persona** with an internal agent pipeline. Coordination is **blackboard-only** (`comms.py`). Routing is **MoE softmax** on pressure telemetry (`engine._moe_route`).

```
python tui.py --model-profile nemotron [--gui]
  └── reactor.py
        ├── s1 comms_operator  — MoE router, never reassigned
        ├── s2 architect
        ├── s3 implementor
        ├── s4 reviewer
        └── s5 devops
```

| Stage | LLM? | Notes |
|-------|------|-------|
| planner | Yes | Stable system prompt; schema + persona in **user** message |
| verifier | Yes | Same pattern; reasoning logged |
| reflector / mutator | Yes | After verifier denial |
| actor | No | `run_python()` sandbox |
| fission_judge | Partial | LLM review + deterministic fallback |
| comms_operator MoE | No | `_moe_route()` ~every 20s; yields on human task |

---

## LLM / KV / reasoning (2026-06-14)

| Item | Where |
|------|-------|
| Stable system prompt per role | `agents._stable_system()` |
| JSON schema in user message | `_user_with_schema()`, `_SCHEMA_USER_HEADERS` |
| Cross-process LLM lock | `llm._global_llm_lock()` → `runtime/.lmstudio.lock` |
| Reasoning capture | `llm.LLMResult`, phase `reasoning` field |
| `LLM_API_SCHEMA=false` | Enables `reasoning_content` from LM Studio |

**Validated MC=5** (`sessions/20260614_032059`): 29 `llm.request`, 26/26 reasoning, 0 `planner.error`, 9 plans, 3 verify confirmed, 2 fissions, actor 5 ok / 3 fail.

**Open questions:** reasoning in TUI/bus mirror? Unified KV for MC=1? API schema vs JSON error rate? Nemotron hybrid full-reprocess rate (see `lm-studio-server-log.md`).

**LM Studio default:** MC=1, reasoning stripping off. **Burst:** MC=5 + Unified KV on for `nemotron_parallel`.

---

## Hard rules

1. **Never create new `.py` files** — edit existing modules only
2. **No env vars for runtime colony config** — CLI + `config.py` (`.env` for LMS hosts OK)
3. **Personas coordinate via bus only**
4. **Do not add markdown to repo** — only `README.md`, `KNOWLEDGE.md`, `AGENTS.md`
5. **`python -m py_compile <file>`** after Python changes
6. **GUI default OFF** — `--gui` or `g` key
7. **`reactor.is_alive()`** uses `OpenProcess(0x1000)` — do not regress

---

## Test procedure

**Before start:** `git checkout unify-rewrite && git pull` · LM Studio nemotron MC=1 · no stale processes · fresh `runtime/comms/`

```bash
python tui.py --model-profile nemotron
```

- [ ] `5/5 slots` > 30s
- [ ] `moe.route` ~every 20s on s1
- [ ] Session JSONL: `llm.response` with `has_reasoning: true`
- [ ] `python comms.py breeder` after 6+ min

Smoke: `python run_test.py 120` · Parallel: `nemotron_parallel` + 5 `@persona` injects · inspect `sessions/<ts>/events-child-s*.jsonl`

---

## Provider-agnostic handover prompt (copy-paste)

Use as the **first user message** in any new AI session. Replace `<TIP>` with `git rev-parse --short HEAD` after pull.

```
You are continuing endgame-ai on branch unify-rewrite (tip <TIP>).

VISION: Self-evolving colony on consumer hardware. Small models. Real actions.
Breeding reactor selects what lives. The LLM is a subroutine inside deterministic
Python loops (pressure, MoE, blackboard) — not the organism.

Read in order: AGENTS.md → KNOWLEDGE.md → README.md.
Optional local context (not in git): ENDGAME_VISION.html, lm-studio-server-log.md,
sessions/20260614_032059 (MC=5 validation).

WHERE WE ARE: Colony Alpha ~88% (runnable, validated). Endgame ~55%.
Infrastructure works. GOAL: repeat breed.improve across multiple live cycles
with logged pressure/fission deltas — proven once, not yet consistent.

HARD RULES: no new .py files; only README/KNOWLEDGE/AGENTS markdown;
bus-only coordination; commit to unify-rewrite (or human-approved session branch).

LLM: nemotron (MC=1 maintenance) or nemotron_parallel (MC=5 burst).
Preserve: stable system prompts, schema in user message, LLM_API_SCHEMA=false.

Before claiming done: py_compile changed files; reactor 2–4 min; sessions JSONL
must show has_reasoning and planner.error=0. Execute yourself — do not tell
the human what to run.
```

---

## File traceability

| Component | Files |
|-----------|-------|
| LLM + reasoning | `llm.py`, `config.py` |
| Prompts / agents | `agents.py`, `prompts/*.txt` |
| MoE / pressure | `engine.py`, `comms.py`, `plugins/comms_beacon.py` |
| Breeding | `reactor.py`, `agents.py` |
| GUI | `tui.py`, `python_code.py`, `observer.py`, `actions.py` |

---

## Session history (`unify-rewrite`)

| Date | Summary |
|------|---------|
| 2026-06-14 | Fast-forward unify-rewrite; delete grok-dev/codex-dev; rewrite handover docs |
| 2026-06-14 | MC=5 validated; reasoning capture; KV-stable prompts; breed.improve once |
| 2026-06-14 | GUI mode; global LLM lock; comms breeder audit |

**Python on this machine:** `C:\Users\px-wjt\AppData\Local\Python\bin\python.exe` if `python` not on PATH.