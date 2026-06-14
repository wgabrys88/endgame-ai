# AGENTS.md — AI session handover (endgame-ai)

**Read this first** if you are Codex, Cursor, Grok, or any AI continuing work on this repo.

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | **You** — rules, state, next steps, test procedure |
| `KNOWLEDGE.md` | Protocol and architecture reference (cite when editing comms/engine) |
| `README.md` | Human quick start only — do not duplicate here |

**Integration trunk:** `unify-rewrite` · tip `ef30bc7`  
**Active work branch:** `grok-dev` · tip `5ae74ea` (merged from codex-dev + breed.improve evidence)  
**Codex branch:** `codex-dev` · tip `0bb182f` — merge into grok-dev complete  
**Milestone:** Colony Alpha ~88% — LLM tuning + desktop observer + `breed.improve` live
**Parallel lineage:** `main` is a different architecture (organism M4) — not parent/child of unify-rewrite

---

## What this project is

Five parallel **slots** (OS processes). Each slot runs one **persona** with an internal agent pipeline. Coordination is **blackboard-only** (`comms.py`). Routing is **MoE softmax** on pressure telemetry (`engine._moe_route`). One LLM at a time for Nemotron (`LLM_MAX_CONCURRENT=1`).

**Core insight:** The LLM is a subroutine inside a deterministic Python loop. Math (pressure, priority, MoE) runs every cycle regardless of LLM state.

**Vision (papers):** Blackboard (CAS 2025) + Pressure fields (Rodriguez 2026) + MoE gating (Bause 2026) + Orchestrator pattern + AgentBreeder (Oxford 2026, ~45% wired on codex-dev). Full vision text: `ENDGAME_VISION.html` (local, not in git) + `Codex-log.md` session transcript.

**Endgame GOAL:** Self-evolving colony on consumer hardware. Breeding reactor (fission retain + evict + reflector + mutator plugin patches) must produce **logged, multi-cycle improvement evidence** (`breed.improve` with pressure/fission deltas). Not complete until live runs show measurable improvement — not just `evolve`/`breed.elite` events.

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

Slot 1 is fixed. Slots 2–5 can be **reassigned** via `control.jsonl` on MoE escalation (`quality_critic` is default escalation target).

---

## Priority interrupt

| pri | Name | Source |
|-----|------|--------|
| 3 | HUMAN | `@persona` in TUI → `inject.jsonl` |
| 2 | CRITICAL | `moe.escalate` + `post_control(reassign)` |
| 1 | NORMAL | `kind=route` from comms_operator |
| 0 | MAINTENANCE | Default; workers sleep until inbox |

Workers wake on inbox kinds: `route`, `request`, `ping` (`comms.pending_for()`).

---

## Pipeline (per persona)

```
scheduler → planner → actor → verifier → fission_judge → [reflector → mutator]
```

| Stage | LLM? | Notes |
|-------|------|-------|
| scheduler | No | Workers return `None` if no inbox and pri≤0 |
| planner | Yes | JSON plan; nemotron thinking via `extract_json()` |
| actor | No | `run_python()` with `colony_env` sandbox |
| verifier | Yes | Posts `kind=verdict` |
| fission_judge | Partial | Deterministic +1; publishes `evolve` retain/evict |
| reflector | Yes | After verifier denial (wired codex-dev) |
| mutator | Yes | Safe `patch_plugin` after failures (wired codex-dev) |

comms_operator: `_moe_route()` every 20s — **no LLM**. Yields maintenance when `comms.human_task_active()`.

---

## Blackboard v1 (`comms.py`)

Schema: `schemas/bus_v1.json`

| Store | Path | Role |
|-------|------|------|
| Intent | `runtime/comms/messages.json` | chat, route, request, evolve |
| Observation | `runtime/comms/events_bus.jsonl` | telemetry, mirrored events, breeder evidence |
| Control | `runtime/comms/control.jsonl` | reactor `reassign` (drain every 5s) |
| Inject | `runtime/comms/inject.jsonl` | human/TUI input |

Envelope: `v, id, ts, from, slot, kind, pri, text, payload`

Key kinds: `message`, `ping`, `request`, `route`, `telemetry`, `event`, `evolve`, `verdict`, `status`

MoE APIs: `colony_state()`, `softmax_route()`, `route()`, `post_control()`, `post_telemetry()`, `human_task_active()`

Breeder audit: `python comms.py breeder` — summarizes `evolve` + `breed.*` from observation bus.

Full kind table and payloads: `KNOWLEDGE.md`

---

## Session logs — what must appear (vision)

Per-slot JSONL under `sessions/<timestamp>/events-child-sN.jsonl`.

| Phase | Slot | Required for vision? | Notes |
|-------|------|---------------------|-------|
| `moe.route` | s1 | **Yes** | ~every 20s; proves Bause MoE closed loop |
| `pressure` | all | **Yes** | ~every 10 cycles; Rodriguez stagnation/power |
| `interrupt` | target | **Yes** | Human pri=3 wake |
| `plan` / `actor` / `verify` / `fission` | worker | **Yes** | Pipeline proof |
| `reflect` / `mutate` | worker | **Yes** | AgentBreeder denial loop |
| `moe.yield` | s1 | **Yes** | MoE paused during human task |
| `plugin.web_sentinel` | all | **No** | Session noise only; skipped on bus |

Bus observation also mirrors `kind=evolve` and reactor `breed.*` status events.

---

## Pressure + MoE (implementation map)

| Concern | File | Symbol |
|---------|------|--------|
| Stagnation math | `engine.py` | `_update_pressure()` |
| MoE cycle | `engine.py` | `_moe_route()` |
| Human yield | `engine.py` + `comms.py` | `human_task_active()` |
| Telemetry | `plugins/comms_beacon.py` | → `post_telemetry()` |
| Softmax gate | `comms.py` | `softmax_route(powers)` — `exp(power*3)` |
| Reassign | `reactor.py` | `drain_control()` → `reassign()` |
| GUI mode | `python_code.py`, `tui.py` | `gui_mode` file; `--gui` or `g` key |
| Breeding | `reactor.py`, `agents.py` | elites, evict, mutation trials |
| Thresholds | `config.py` | `STAG_ESCALATE=0.7`, `VEL_STUCK=0.01`, `STUCK_TICKS_ESCALATE=5` |

**Stuck:** `stag >= 0.7` AND `|velocity| <= 0.01` for 5 consecutive MoE cycles → escalate + swap slot persona.

**Critical fix (do not regress):** `reactor.is_alive()` uses `OpenProcess(0x1000)` — wrong mask `0x00100000` caused false 5s respawn loop.

---

## Research pillars → code (honest scores, codex-dev)

| Pillar | Score | Status |
|--------|-------|--------|
| Blackboard (CAS 2025) | ~90% | v1 envelope live; human + evolve on bus |
| Orchestrator pattern | ~82% | idle workers, 1 LLM gate, human yield |
| Pressure fields (Rodriguez 2026) | ~70% | core math; escalation wired |
| MoE (Bause 2026) | ~78% | closed loop + yield on human |
| AgentBreeder (Oxford 2026) | ~55% | evolve, reflector, mutator, elites, trials — **`breed.improve` live 2026-06-14** |

---

## Hard rules

1. **Never create new `.py` files** — edit existing modules only
2. **No env vars for runtime colony config** — CLI args and `config.py` only (`.env` for LMS hosts is OK)
3. **Personas coordinate via bus only** — no shared mutable state between processes
4. **Do not add markdown files to the repo** — only `README.md`, `KNOWLEDGE.md`, `AGENTS.md`
5. **Test on `codex-dev` or `grok-dev`** before claiming stability fixes
6. Every Python change must pass `python -m py_compile <file>`
7. **GUI default OFF** — use `python tui.py --gui` or press `g` to allow desktop automation; default still declines GUI goals

---

## Live test results

### 2026-06-13 (grok-dev, session `20260613_164412`)

Infrastructure PASS; GUI notepad FAIL → fixed in `afe87ac`.

### 2026-06-14 LLM A/B (`python llm.py bench`)

| Profile | JSON ok | Avg s | System FPS |
|---------|---------|-------|------------|
| nemotron_legacy | 2/4 | 28.2 | 4 |
| nemotron (optimized) | 3/4 | 20.3 | 1 |

Optimized wins JSON reliability and KV-stable planner system prompt. Legacy persona-in-system caused 4 distinct system fingerprints. **LM Studio:** set Max Concurrent Predictions=1 manually — colony now enforces single-flight via `runtime/.lmstudio.lock`.

### 2026-06-14 (codex-dev, Grok validation)

**60s smoke PASS**
- 5/5 slots alive; 3 `moe.route`; 9 `pressure`; 33 bus events

**360s behavior PASS**
- 18 `moe.route` (~20s cadence); 0 false respawn
- Full pipeline on s2/s3: `plan`→`actor`→`verify`→`reflect`→`mutate`
- Bus evidence: `evolve` evict/patch_plugin, `breed.elite`, `breed.evict`
- **Gap (fixed):** first 6min had no `breed.improve`; trial evaluator + safe telemetry fallback now produce it
- **Noise:** `plugin.error` spam on s1/s4/s5 (web_sentinel connectivity)

### Human retest (codex-dev `502947b`)

- `@devops open notepad` → decline, zero Notepad (default safe mode)
- `@implementor create hello.txt with hello world` → deterministic verify path → confirmed fission

---

## What works (verified codex-dev)

- 5 slots without false respawn
- MoE closed loop + human yield
- Human file task deterministic path
- Reflector after verifier denial
- Mutator safe `patch_plugin` with write-prefix guard
- Fission → `evolve` retain/evict; reactor `breed.elite` / `breed.evict`
- Elite archive + respawn selection
- Mutation trial evaluator (60s window)
- `python comms.py breeder` audit command
- GUI mode opt-in (`--gui`, `g` toggle, header shows `GUI`/`safe`)

## Not built yet (do not claim done)

- Consistent multi-cycle `breed.improve` across runs (one event proven; GOAL needs repetition)
- LLM fission_judge (deterministic +1 only)
- Desktop observer agent (win32 UIA — port from `main` when needed)
- Long-run MAP-Elites fitness convergence

---

## Test procedure (run after changes)

**Before start**

- [ ] `git checkout codex-dev && git pull` (or `grok-dev` after merge)
- [ ] LM Studio + nemotron, or `--backend acp`
- [ ] No stale tui/reactor/notepad processes
- [ ] `runtime/comms/` empty or fresh (TUI wipes on start)

**Launch**

```bash
python tui.py --model-profile nemotron
```

- [ ] TUI 45 lines; header `5/5 slots`
- [ ] Slots alive > 30s
- [ ] s1: `moe.route` ~every 20s; `pressure` ~every 20s
- [ ] `python comms.py state` — telemetry per persona
- [ ] Human GUI test (safe mode): decline, no Notepad
- [ ] Human file test: `@implementor` → confirmed fission
- [ ] `python comms.py breeder` — evolve/breed evidence after 6+ min run

**Smoke:** `python run_test.py 120`

---

## Suggested next work (priority order)

1. **Repeat `breed.improve`** across multiple live cycles (MAP-Elites convergence)
2. Reduce mutator harm to `comms_beacon` (protected) and tune LLM patch quality
3. Fix `plugin.error` / web_sentinel noise on idle slots
4. Port desktop observer from `main` when GUI mode needs screen context
5. MAP-Elites fitness from fission + stagnation history
6. Merge stable branch → `unify-rewrite` when human decides

---

## File traceability

| Component | Files |
|-----------|-------|
| MoE gate | `engine.py`, `comms.py` |
| Pressure | `engine.py`, `plugins/comms_beacon.py` |
| Human cap / GUI | `agents.py`, `python_code.py`, `actions.py`, `tui.py` |
| Breeding | `reactor.py`, `agents.py`, `comms.py` |
| Reactor | `reactor.py` |
| Orchestrator scheduler | `agents.py` |
| TUI | `tui.py` |
| Config | `config.py` |
| Prompts | `prompts/planner.txt`, `prompts/mutator.txt`, `prompts/reflector.txt`, `prompts/personalities/*.txt` |
| Schemas | `schemas/bus_v1.json`, `route.json`, `telemetry.json`, `planner.json` |

---

## Session history

### grok-dev (through `afe87ac`)

| Commit | Summary |
|--------|---------|
| `afe87ac` | GUI guard, human cap, MoE yield, token diet |
| `894e72c` | MoE closed loop + docs |
| `6906eac` | Blackboard protocol v1 |

### codex-dev (13 commits ahead)

| Commit | Summary |
|--------|---------|
| `5933ad3` | Plugins mutator update |
| `23b94e0` | `comms.py breeder` audit command |
| `54870ea` | Mirror breeder evidence to observation bus |
| `3d9a024` | Mutation trial scoring from telemetry |
| `b45b631` | Elite respawn selection |
| `502947b` | Deterministic human file tasks |

---

## Grok Build knowledgebase (session memory)

**Branch model:** Work on `codex-dev` until merged to `grok-dev`. Do not commit to both without coordination.

**Codex transcript:** `Codex-log.md` — full chat from bootstrap through AgentBreeder wiring. Read GOAL section at end.

**Vision trailer:** `ENDGAME_VISION.html` — inception layers, paper map, milestone scores (update grok-dev % to ~82% when editing).

**Validation 2026-06-14:** 60s + 360s TUI runs on `codex-dev` both PASS. Merge codex→grok recommended.

**GUI mode:** User requested "hui/GUI mode" for self-evolving organism — opt-in via `--gui` or `g` key; removes planner/actor safeguards. Default safe mode unchanged.

**Python path (this machine):** `C:\Users\px-wjt\AppData\Local\Python\bin\python.exe` if `python` not on PATH.

---

## Multi-agent branching

```
unify-rewrite          ← integration trunk
├── grok-dev           ← Grok (behind codex-dev by 13 commits)
├── codex-dev          ← Codex + Grok continuation (ACTIVE)
└── main               ← parallel species (organism M4)
```

**Merge recommendation (2026-06-14):** Fast-forward `grok-dev` to `codex-dev` after human approval. All infra tests pass; codex adds breeding loop without regressing MoE/pressure.

**Do not** have two agents commit to the same branch without coordination.