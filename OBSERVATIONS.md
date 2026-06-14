# OBSERVATIONS.md

**AI-facing doc (git-tracked).** § COLD-START HANDOVER is the only briefing for tools with zero context. Update it on every behavior-changing commit (see `RULES.md`).

Humans: read `README.md`.

---

## COLD-START HANDOVER PROMPT

**Last updated:** 2026-06-14 · **Branch:** `bare-metal` (**42 files**, ~6971 lines) · **Backup:** `unify-rewrite` (49) · **MILESTONE:** `dev-milestone-20260614` → `5ca4ee8` · **HEAD:** `ca4afcf`

Copy the fenced block into any new AI session.

```text
PROJECT: endgame-ai — self-evolving multi-agent colony on consumer hardware.
Branch: bare-metal (42 files, ~6971 lines). Backup: unify-rewrite. Legacy: main (24 files, different arch).
Model: nvidia-nemotron-3-nano-4b, profile nemotron_parallel (LM Studio MC=5).

READ ORDER:
1. RULES.md — 42-file inventory + traceback methodology
2. OBSERVATIONS.md — this prompt + § Traceback audit below
3. README.md — human run command
4. Code: comms.py, engine.py, agents.py, reactor.py, tui.py, config.py

MINIMAL CORE (42 files):
  Entry(3): tui.py, reactor.py, main.py
  Pipeline(3): engine.py, agents.py, comms.py (+ actor sandbox bus_* API)
  Infra(4): config.py, log.py, llm.py (runtime only), python_code.py
  Desktop(3): actions.py (+ desktop helpers), observer.py, win32.py
  Backend(1): acp_client.py
  Plugins(4) · Prompts(10) · Schemas(5) · Meta(8)

IDENTITY (OoO): config.Personality + engine.AgentContext(board).
  main.py sets board.personality/slot; engine.ensure_context() binds object.
  agents._personality(board) reads board first; reactor.Breeder holds archive state.

STRIPPED: lessons.py, run_test.py, 3 schemas; colony_env→comms; desktop→actions; llm benchmark ~970 lines.

ORGANISM (deterministic, not the LLM):
  pressure → MoE (s1) → blackboard → scheduler → planner → actor → verifier
  → fission_judge → reflector → mutator → breeder (reactor.py)

RUN:
  python tui.py "long-term goal sentence"
  python tui.py --safe "goal"   # guarded mode
  LM Studio localhost:1234, nemotron-3-nano-4B loaded.
  Fresh disk: python -c "import log; log.cleanup_runtime(deep=True)"

GOALS (Codex /goal):
  CLI trailing words → LONG_TERM_GOAL (runtime/colony_goal.txt, gitignored).
  MoE assigns work toward it. TUI Enter = pri=3 ACTIVE_TASK override until verified.
  No goal → maintenance audits → idle.

ARCHITECTURE: 5 slots — comms_operator + 4 workers. Bus-only via comms.py.

HARD RULES (RULES.md):
  - No new .py files
  - Never commit runtime/, sessions/, golden artifacts
  - py_compile changed Python; do not weaken verifier/fission gates

KEY FILES:
  Bus: comms.py (inbox_match, apply_interrupt, set_colony_goal)
  Loop: engine.py, agents.py, prompts/*.txt, schemas/*.json
  Ops: tui.py, reactor.py, config.py
  Breeder: reactor.py, plugins/fission_log.py (protected)

SMOKE (no LLM):
  python agents.py --fission-smoke
  python agents.py --git-verify-smoke
  python reactor.py --archive-smoke
  python reactor.py --breed-improve-smoke

MILESTONE: git checkout dev-milestone-20260614  # pins 5ca4ee8 DEV_BASELINE_20260614
BRANCHES: bare-metal = forward dev (minimal). unify-rewrite = backup (pre-cleanup).
STATE: bare-metal cleanup branch created. Session 20260614_201915 forensics in § Session log.
CURRENT PRIORITY:
  1. Shrink agents.py in-place (validators block, JsonRoleAgent) — no new .py files
  2. Prove breed.improve elite survives restart
  3. Fix s2/s4 need_plan idle spin
  DONE: AgentContext, Breeder class, _verify_outcome, format_phase_brief, Personality on board

NOT IN GIT: runtime/, sessions/*.jsonl — keep locally only.
```

---

## Traceback audit: main vs bare-metal (2026-06-14)

### Why bare-metal feels "enormous" vs main

| | `main` | `bare-metal` (now) |
|--|--------|-------------------|
| **Files** | 24 | **42** |
| **Lines** | ~3,656 | **~6,971** |
| **Processes** | 1 (+ math thread) | 5 slots + reactor |
| **Bus** | snapshot.json | comms blackboard |
| **Breeding** | none | reactor MAP-Elites |
| **Agents** | stagnation/lorenz/pid math | fission_judge + mutator + MoE |
| **llm.py** | 118 lines | 358 lines (was 1280 before benchmark strip) |

**main is not a subset** — it is a legacy single-agent loop. Bare-metal is ~2× lines because the **working wiring** (multi-process, bus, breed, fission) is real code.

### Traceback from `python tui.py` (critical path)

```text
tui.py ──subprocess──► reactor.py ──spawn×5──► main.py
                                              └── Personality.from_env()
                                              └── engine.run(board)
                                                    └── agents.* (1524 lines — bloat #1)
                                                    └── comms bus
                                                    └── plugins/*
llm.py ◄── agents (358 lines after strip — was 68% benchmark dead weight)
```

### Dead weight removed this pass

| Item | Savings |
|------|---------|
| `llm.py` benchmark block | ~970 lines |
| `colony_env.py` → `comms.py` | 1 file |
| `desktop.py` → `actions.py` | 1 file |
| Dead functions (`kill_children`, `gui_default_enabled`, …) | small |

### Remaining bloat (in-file, next passes)

| Module | Lines | Issue |
|--------|------:|-------|
| `agents.py` | 1524 | Monolith: validators + mutation + smokes + 7 agent classes |
| `reactor.py` | 950 | Breeding + spawn + smokes in one module |
| `comms.py` | 888 | Bus + mirror + actor sandbox + CLI |
| `tui.py` + `comms.py` | — | Duplicate `_brief()` formatting |

### OOP target (no new .py files per RULES)

```text
config.Personality     — done (dataclass slots=True)
engine.AgentContext    — personality + board, passed to pipeline steps
reactor.Breeder        — class inside reactor.py (archive, trials, evolve)
agents.Pipeline        — optional: collapse JsonRoleAgent pattern for 4 roles
```

Personalities stay **prompt files + Personality instance** — not six subclasses. Slot = process boundary; Personality = identity object inside process.

---

## Methodology

### Evidence (local, gitignored)

1. `sessions/<id>/events-reactor.jsonl` — breeder
2. `sessions/<id>/events-child-s1..s5.jsonl` — workers
3. `runtime/comms/messages.json` — blackboard
4. `runtime/breed_archive.json` — survivors

### Poll protocol

| Situation | Wait |
|-----------|------|
| Simple file task | 30–45s |
| Multi-step / git | 90–120s |
| Planner LLM active | ≥45s |
| Stuck loop | 3–5 min or new task |

### Session close (append to log below)

One table row + 5–15 lines: what worked, what failed, files to change together.

### Human / bus rules

- TUI posts `from=human`, pri=3 — no `@human` in body.
- pri=3 delivers without `@colony` (`comms.inbox_match`).
- Declines use pri=0 + `human_ack` (not pri=3).

### Wiring reference (current)

| Component | Role |
|-----------|------|
| `comms.apply_interrupt` | Single interrupt path |
| `comms.set_colony_goal` | Codex-style persistent goal |
| `engine._moe_route` | Routes `maintenance_goal_text()` |
| `_restore_after_human_task` | After human verify → idle → MoE |

---

## Session log

Append only. No golden archives in git — summaries live here.

| Session | Duration | Events | Headline | Notes |
|---------|----------|--------|----------|-------|
| `dev-milestone-20260614` | — | — | **DEV BASELINE** | Slim repo, Codex goal startup, RULES.md, OBSERVATIONS handover |
| *(flush 2026-06-14)* | — | — | Repo slimmed `3a30c9a` | Golden artifacts removed from git |
| `20260614_201915` | ~23m | ~2250 | **Partial win, elite wipe** | Killed 20:43. See forensics below. |
| `bare-metal` v1 | — | 44→42 | **File strip** | lessons, run_test, 3 schemas |
| `bare-metal` v2 | — | 42 / ~7k lines | **Code strip** | llm benchmark, colony_env+desktop merge, Personality OoO |
| `bare-metal` v3 | — | 42 files | **OoO refactor** | AgentContext, Breeder, verifier dedup, shared _brief |

### Session `20260614_201915` forensics (2026-06-14, killed by operator)

**Run:** `python tui.py` with colony goal (breed.improve + notepad progress). Profile `nemotron_parallel`, open/unconstrained, GUI. Span 18:19–18:43 UTC.

**Evidence files (local, gitignored):**

| File | Lines | Role |
|------|-------|------|
| `events-reactor.jsonl` | 141 | 15× `breed.improve`, 40× `breed.evict`, 66× archive saves |
| `events-child-s1.jsonl` | 656 | MoE/comms — 426× `plugin.fission_log` poll (stag=0.67 idle) |
| `events-child-s2.jsonl` | 533 | architect — 122× `schedule→planner (need_plan)` spin |
| `events-child-s3.jsonl` | 491 | implementor — primary worker (plan/actor/verify) |
| `events-child-s4.jsonl` | 439 | reviewer — 167× need_plan spin |
| `events-child-s5.jsonl` | 69 | quality_critic — ended on `Unblock work stalled at @devops` |

**What worked**

- Codex goal persisted in `runtime/colony_goal.txt`.
- **implementor (s3)** got verifier **confirmed** for: OBSERVATIONS.md milestone note, notepad opened, note written (18:37–18:39).
- **breed.improve** fired 15× in reactor (git status, notepad, OBSERVATIONS filenames); implementor elite retained mid-run (fitness 0.96).
- **fission.deny** gate worked (4 denials; e.g. bus-only reactor.py claims blocked).
- **human.decline** correctly fired on vague pri=3 tasks after max retries (8 total across slots).

**What failed (root causes)**

1. **verify_denial dominates** — 37 evicts vs 3 fission_denial. Final `breed_archive.json`: `elite_archive={}`, all 5 personas in `evicted_personas`. implementor evicted 18:42 after 60s timeout verify.
2. **Multi-goal overload** — goal bundled breed.improve + notepad + screen report; planner produced invalid JSON, Chrome/Shakira steps (unconstrained), `plugins/reactor.py` patches (file does not exist).
3. **Human pri=3 meta-interrupt** (~18:31) — "remove constraints / max retries / mutate capabilities" → 42× `planner.error` (syntax, Path re-import, comms.py rewrite attempts). Worse than golden-session log.py loop.
4. **s1/s2/s4 idle spin** — comms_operator + architect + reviewer burned cycles on fission_log poll or need_plan without assigned work; TUI showed stag=0.67, fissions=0.
5. **Verifier edge case** — early NameError evidence sometimes got `confirmed` then `denied` (same evidence string); worth watching, not weakening gates.
6. **Mutator blocked** — repeated `patch_plugin` on protected `comms_beacon.py` and nonexistent `plugins/reactor.py`.

**Golden session `20260614_175152` comparison**

| Aspect | Golden (175152, disk gone) | Current (201915) |
|--------|---------------------------|------------------|
| Reference | `llm.py` SESSION_REPLAY_TASKS + GOLDEN_SESSION_BUDGETS | Full JSONL on disk |
| Fission | Empty JSON / unverifiable claims | `fission.deny` with diagnosis (working) |
| Verifier | routed-vs-posted confusion, log.py syntax | Strict evidence checks; timeout denials |
| Planner | Stuck on log.py audit | JSON syntax + hallucinated side tasks |
| Breed | Unknown (session removed) | 15 improve → 0 elites at kill |
| Human | — | 2 declines + 1 destructive pri=3 override |

Golden budgets are **benchmark replay only** (`GOLDEN_SESSION_BUDGETS` in `llm.py`); runtime uses `config.BUDGET` / `THINKING_BUDGET` for `nemotron_parallel`.

**Operator kill state:** Python processes stopped. Stale `pause` + `runtime/.lmstudio.lock` may remain — run `log.cleanup_runtime(deep=True)` before next session.

**Recommended next run**

```text
python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --safe "Patch plugins/lessons_decay.py: add one-line docstring, py_compile, git commit"
```

Single measurable artifact + git hash. No meta pri=3. Wait ≥2 min after plan before judging stall.

### Lessons (compressed, no forensic dumps)

- Colony survives long runs; MoE + breed loop active, but **elites do not survive verify_denial churn**.
- Post-milestone wiring works: goal file, fission deny, human decline, breed.improve signal.
- **nemotron_parallel** needs narrow goals; unconstrained + compound goals → planner.error avalanche.
- s2/s4 need_plan idle spin is a scheduling gap when only s3 has routed work.
- Unproven: MAP-Elites convergence, restart-persistent elites (mid-run elite existed, archive empty at kill).
- Golden session forensic value now lives in `llm.py` replay tasks only — not in repo tree.
- **bare-metal** = 42 files / ~7k lines; main (24 files) is legacy — not comparable.
- `Personality` dataclass is first OoO step; agents/reactor monoliths are next shrink targets.

---

*Update § COLD-START HANDOVER HEAD on every commit. See RULES.md.*
