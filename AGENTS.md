# AGENTS.md — AI session handover (endgame-ai)

**Read this first** if you are Codex, Cursor, Grok, OpenCode, or any AI continuing work on this repo.

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | **You** — rules, state, handoff, test procedure |
| `KNOWLEDGE.md` | Protocol and architecture (cite when editing comms/engine/llm) |
| `README.md` | Human quick start only |

**Grok Build memory index:** `~/.grok/memory/wgabrys88-endgame-ai/MEMORY.md` (workspace knowledge, not in git)

**Integration trunk:** `unify-rewrite`  
**Active work branch:** `grok-dev` — tip updates on each session commit  
**Codex branch:** `codex-dev` — merged into `grok-dev` 2026-06-14  
**Future branch:** `open-code-dev` — **does not exist yet**; if the human creates it for OpenCode development, branch from current `grok-dev` tip and develop there; merge back when stable  
**Parallel lineage:** `main` (organism M4) — not parent/child of `unify-rewrite`

**Milestone:** Colony Alpha ~90% — KV-stable prompts, reasoning capture live, `breed.improve` proven once (GOAL: repeat across cycles)

---

## Handoff for the next agent

### If you are **Codex**

1. `git fetch && git checkout grok-dev && git pull`
2. Read this file + `KNOWLEDGE.md` LLM layer section
3. Do **not** recreate work on `codex-dev` unless coordinating a parallel experiment — `grok-dev` is integration point for this lineage
4. Run test procedure below before claiming stability
5. One agent commits per branch at a time

### If you are **OpenCode** (future `open-code-dev`)

1. Human may create `open-code-dev` from `grok-dev` — if absent, ask before creating
2. Same hard rules as below; no new `.py` files
3. Document your tip in this file's session history when merging
4. Do not fork architecture toward `main` without explicit human direction

### If you are **Grok**

- Workspace memory: `~/.grok/memory/wgabrys88-endgame-ai/MEMORY.md`
- Local vision: `ENDGAME_VISION.html`, transcript: `Codex-log.md` (not in git)

---

## What this project is

Five parallel **slots** (OS processes). Each slot runs one **persona** with an internal agent pipeline. Coordination is **blackboard-only** (`comms.py`). Routing is **MoE softmax** on pressure telemetry (`engine._moe_route`). Default Nemotron: `nemotron` profile (MC=1 + global lock). Burst: `nemotron_parallel` (MC=5, lock off, LM Studio MC=5 + Unified KV).

**Core insight:** The LLM is a subroutine inside a deterministic Python loop. Math (pressure, priority, MoE) runs every cycle regardless of LLM state.

**Endgame GOAL:** Self-evolving colony on consumer hardware. Breeding reactor must produce **logged, multi-cycle** `breed.improve` evidence (pressure/fission deltas). One event proven — needs repetition.

---

## Process tree

```
python tui.py --model-profile nemotron [--gui]
  └── reactor.py
        ├── main.py [s1 comms_operator]  — MoE router, never reassigned
        ├── main.py [s2 architect]
        ├── main.py [s3 implementor]
        ├── main.py [s4 reviewer]
        └── main.py [s5 devops]
```

---

## Pipeline (per persona)

```
scheduler → planner → actor → verifier → fission_judge → [reflector → mutator]
```

| Stage | LLM? | Notes |
|-------|------|-------|
| planner | Yes | Stable system prompt; schema + persona in **user** message |
| verifier | Yes | Same pattern; reasoning logged on `verify` |
| reflector / mutator | Yes | After verifier denial |
| actor | No | `run_python()` sandbox |
| fission_judge | Partial | LLM review + deterministic fallback |
| comms_operator MoE | No | `_moe_route()` every 20s; yields on human task |

---

## LLM / KV / reasoning (2026-06-14 — implemented, partly open)

### Done

| Item | Where |
|------|-------|
| Stable system prompt per role | `agents._stable_system()` |
| JSON schema contract in user message | `_user_with_schema()`, `_SCHEMA_USER_HEADERS` |
| Cross-process LLM lock | `llm._global_llm_lock()` → `runtime/.lmstudio.lock` |
| Reasoning capture | `llm.LLMResult`, `llm.response`, phase `reasoning` field |
| `LLM_API_SCHEMA=false` on nemotron | Schema in user only — enables `reasoning_content` from LM Studio |
| LM Studio: reasoning stripping off | User setting — required for API reasoning field |

### Validated single-flight (`sessions/20260614_024645`, 2 min)

- 10/10 `llm.response` with reasoning; 0 errors

### Validated parallel MC=5 (`sessions/20260614_032059`, 4 min + 5 human injects)

- 29 `llm.request`, 26 `llm.response` (26/26 reasoning), **0 planner errors**
- All 5 slots used LLM; 5 interrupts; 9 plans; 3 verify confirmed; **2 fissions**
- Actor: 5 ok / 3 fail (2 `not python` — down from prior runs after planner.txt fix)
- Planner `THINKING_BUDGET=1536` under parallel — no budget-truncation empty JSON

### Open questions (do not claim resolved)

1. **Reasoning everywhere?** Currently all LLM roles log reasoning to session JSONL. Unknown if bus mirror / TUI should show it, or if some roles should omit it for noise.
2. **Unified KV Cache:** Human **disabled** Unified KV. Hypothesis: Unified KV mainly helps **parallel** slots (MC>1), not single-flight MC=1 orchestrator. **Not A/B tested** — needs LM Studio log comparison (restore vs shallow prefix) on identical prompt series.
3. **API schema vs user schema:** `LLM_API_SCHEMA=false` trades constrained decoding for reasoning. Occasional `planner.error` on malformed JSON — monitor rate before re-enabling API schema.
4. **Nemotron hybrid architecture:** Partial KV reuse expected even when tuned (LM Studio "full reprocess" on hybrid memory).

### LM Studio load (human, 2026-06-14)

- Max Concurrent Predictions: **1**
- Unified KV Cache: **off** (user choice — see open question #2)
- Reasoning stripping: **off**
- Reference screenshot: `image-options.jpg` (local, not in git)

---

## Blackboard v1 (`comms.py`)

| Store | Path |
|-------|------|
| Intent | `runtime/comms/messages.json` |
| Observation | `runtime/comms/events_bus.jsonl` |
| Control | `runtime/comms/control.jsonl` |
| Inject | `runtime/comms/inject.jsonl` |

Breeder audit: `python comms.py breeder`

Full kind table: `KNOWLEDGE.md`

---

## Session logs — required phases

Per-slot: `sessions/<timestamp>/events-child-sN.jsonl`

| Phase | Required? |
|-------|-----------|
| `moe.route`, `pressure` | Yes |
| `llm.response` with `reasoning` | Yes (debug / adaptation) |
| `plan`, `actor`, `verify`, `fission` | Yes |
| `reflect`, `mutate` | Yes (breeder loop) |
| `plugin.web_sentinel` | No (noise) |

---

## Hard rules

1. **Never create new `.py` files** — edit existing modules only
2. **No env vars for runtime colony config** — CLI + `config.py` (`.env` for LMS hosts OK)
3. **Personas coordinate via bus only**
4. **Do not add markdown to repo** — only `README.md`, `KNOWLEDGE.md`, `AGENTS.md`
5. **`python -m py_compile <file>`** after Python changes
6. **GUI default OFF** — `--gui` or `g` key
7. **`reactor.is_alive()`** uses `OpenProcess(0x1000)` — do not regress to `0x00100000`

---

## What works (verified grok-dev 2026-06-14)

- 5 slots without false respawn
- MoE closed loop + human yield
- KV-stable planner/verifier system prompts (1 fingerprint per role)
- Reasoning in session logs (`reasoning_content` + phase events)
- `nemotron` single-flight + `nemotron_parallel` MC=5 burst mode
- AgentBreeder: reflector, mutator, evolve, elites, trials, `breed.improve` (≥1 run)
- GUI opt-in; human file task deterministic path
- `python llm.py bench`, `python comms.py breeder`

## Not built / not proven

- Consistent multi-cycle `breed.improve`
- Unified KV / reasoning policy decision with evidence
- LLM fission_judge only (fallback exists)
- Long-run MAP-Elites convergence
- Merge `grok-dev` → `unify-rewrite` (human decides)

---

## Test procedure

**Before start**

- [ ] `git checkout grok-dev && git pull`
- [ ] LM Studio: nemotron loaded, MC=1, reasoning stripping off
- [ ] No stale tui/reactor processes
- [ ] Fresh `runtime/comms/` (TUI wipes on start)

**Launch**

```bash
python tui.py --model-profile nemotron
```

- [ ] `5/5 slots` > 30s
- [ ] `moe.route` ~every 20s on s1
- [ ] Session JSONL: `llm.response` with `has_reasoning: true` after planner runs
- [ ] `python comms.py breeder` after 6+ min

**Smoke:** `python run_test.py 120`  
**Reactor 2 min:** `python reactor.py --model-profile nemotron`  
**Parallel burst 4 min:** `python reactor.py --model-profile nemotron_parallel` + inject 5 `@persona` tasks via `comms.post(..., priority=PRI_HUMAN)`; inspect `sessions/<ts>/events-child-s*.jsonl` for `llm.request` overlap across slots

**Behavioral analysis checklist**

- [ ] `llm.request`: `concurrent_gate` matches profile; `global_lock` false for parallel
- [ ] `llm.response`: `has_reasoning: true`, `reasoning_tokens` > 0
- [ ] `plan` events include `reasoning_chars`; actor `ok` not mostly `not python`
- [ ] `planner.error` count = 0 under load
- [ ] TUI header shows profile tag; slot lines show `think=N` on plan / `llm.response`

---

## Suggested next work

1. A/B Unified KV on/off with MC=1 — same prompt series, compare LM Studio checkpoint logs
2. Repeat `breed.improve` across multiple live cycles
3. Tune `LLM_API_SCHEMA` / JSON error rate vs reasoning visibility
4. Reduce `web_sentinel` / `plugin.error` noise on idle slots
5. Merge stable `grok-dev` → `unify-rewrite` when human decides

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

## Multi-agent branching

```
unify-rewrite
├── grok-dev           ← ACTIVE (this session)
├── codex-dev          ← merged into grok-dev
├── open-code-dev      ← create when human starts OpenCode work
└── main               ← parallel species
```

**Do not** have two agents commit to the same branch without coordination.

---

## Session history (grok-dev)

| Date | Summary |
|------|---------|
| 2026-06-14 | Merge codex-dev; GUI mode; breed.improve; KV research |
| 2026-06-14 | Stable system + user schema; global LLM lock; `llm.py bench` |
| 2026-06-14 | Reasoning capture; parallel MC=5 validated; TUI LLM visibility; planner code rules |
| 2026-06-14 | `52b47a0` planner budget + TUI; `c9a7655` MC=5 profile; `b83db59` reasoning prompts |

**Python on this machine:** `C:\Users\px-wjt\AppData\Local\Python\bin\python.exe` if `python` not on PATH.

---

## Provider handover meta-prompts (copy-paste)

Use these as the **first user message** when starting a new session. Replace `<TIP>` with `git rev-parse --short HEAD` after pull.

### Grok → branch `grok-dev`

```
You are continuing endgame-ai on branch grok-dev (tip <TIP>).
Read AGENTS.md, KNOWLEDGE.md, ~/.grok/memory/wgabrys88-endgame-ai/MEMORY.md.
Hard rules: no new .py files; only README/KNOWLEDGE/AGENTS markdown; bus-only coordination.
LLM: nemotron (MC=1 maintenance) or nemotron_parallel (MC=5 burst). Reasoning in llm.response + plan events.
Test before claiming done: py_compile changed files; reactor 2–4 min; check sessions JSONL for reasoning + planner.error=0.
Execute yourself — do not tell the human what to run. GOAL: repeat breed.improve across cycles.
```

### Codex → branch `grok-dev` (codex-dev merged; do not fork unless coordinated)

```
You are Codex continuing endgame-ai. Work on grok-dev (codex-dev already merged).
Read AGENTS.md + KNOWLEDGE.md first. Cite comms.py/engine.py/llm.py when editing protocol code.
Never add .py files. Commit only to grok-dev unless human explicitly revives codex-dev for an experiment.
Validation: python -m py_compile <file>; python reactor.py --model-profile nemotron_parallel for parallel work;
inspect sessions/*/events-child-s*.jsonl — llm.response must show has_reasoning.
Preserve: stable system prompts, schema in user message, LLM_API_SCHEMA=false for reasoning.
```

### OpenCode → branch `open-code-dev` (create from grok-dev tip when human approves)

```
You are OpenCode on endgame-ai. Branch: open-code-dev (create from grok-dev if missing).
Read AGENTS.md + KNOWLEDGE.md. Same architecture as grok-dev — blackboard colony, no cross-process shared state.
Hard rules identical to AGENTS.md. Push to open-code-dev only; merge to grok-dev via human review.
Test methodology: behavioral runs with comms.post human pri=3 injects; document session IDs in AGENTS session history.
Do not merge toward main (organism M4) — that is a parallel species.
```

### Branch consolidation (human decision — pending)

| Target | Action when approved |
|--------|---------------------|
| `unify-rewrite` | Fast-forward or merge `grok-dev` → integration trunk |
| `codex-dev` | Archive or reset to `grok-dev` tip (already superseded) |
| `open-code-dev` | `git checkout -b open-code-dev grok-dev` for OpenCode-only work |

**Ask the human** before any merge to `unify-rewrite` or creating `open-code-dev`.