# AGENTS.md — AI session handover for endgame-ai

**Read this file first.** It is provider-agnostic: Codex, OpenCode, Grok, Claude, or any coding agent should treat it as the single source of truth for vision, evidence, constraints, and next work.

| File | Purpose |
|---|---|
| `AGENTS.md` | Vision, golden-run proof, fix roadmap, handover prompt |
| `KNOWLEDGE.md` | Protocol, pressure math, breeder loop, file map |
| `README.md` | Human quick start |
| `OBSERVATIONS.md` | **Session tracking** — observation method + multi-perspective forensic per run (append-only) |
| `sessions/20260614_132940/README.md` | Full forensic log (~1200 lines) of the golden run |
| `ENDGAME_GOLDEN_RUN.html` | Interactive golden-run dashboard (open in browser) |
| `ENDGAME_VISION_ADVANCED.html` | Architecture vision v2 (10-min proof era) |

Work branch: `unify-rewrite`.  

### Golden milestone tags (two commits, one session)

| Tag | Commit | What it pins |
|-----|--------|----------------|
| `golden-run-20260614` | `de850cf` | **Evidence handover** — AGENTS/KNOWLEDGE/README, session forensic README, HTML dashboards, `fission_log.py` restored |
| `golden-run-code-c897385` | `c897385` | **Code that was running** when session `20260614_132940` started (pre-mutation) |

Session `20260614_132940` ran ~1h49m on code at/near `c897385`. Post-run commits `f99e12f` (maintenance) and `de850cf` (handover) are **after** the run.

### What is in git vs external archive

**In git (milestone documentation, not raw telemetry):**

- `sessions/20260614_132940/README.md` — forensic analysis (~1200 lines)
- `ENDGAME_GOLDEN_RUN.html`, `ENDGAME_VISION_ADVANCED.html`
- `AGENTS.md`, `KNOWLEDGE.md`, `README.md`, `OBSERVATIONS.md`
- `file.py` — git-status snapshot from run era

**Gitignored by design (keep on your external drive archive):**

- `sessions/20260614_132940/events-*.jsonl` — **4,137 raw events (~1.86 MB)** — the actual golden telemetry
- `runtime/comms/` from run time, `errors.txt`, `Colony_Demo/`, `audit_report.txt`

The milestone is **having this data at all** (documented + archived). Git carries the map; external archive carries the territory.

---

## Vision (unchanged)

Endgame is a **self-evolving colony on consumer hardware**. Small local models. Real actions on the real machine. A breeding reactor selects what survives.

**The LLM is a subroutine, not the organism.** The organism is the deterministic Python control loop:

```text
pressure fields → MoE routing → blackboard → scheduler → planner → actor
  → verifier → fission_judge → reflector → mutator → reactor breeder
```

Personas never call each other directly. All coordination is through `comms.py` (blackboard v1).

---

## Golden Run — Primary Proof (2026-06-14)

Session **`20260614_132940`** is the **GOLDEN RUN**: first ~**1h49m** autonomous colony session under **live human steering** on real hardware, not a lab smoke test.

| Metric | Golden (`132940`) | Prior 10-min (`112843`) |
|--------|-------------------|-------------------------|
| Duration | 1:49:01 | ~10 min |
| Events | 4,137 | 728 |
| Plans | 104 | 16 |
| Verify confirmed | **32** | 7 |
| Fission credit | **0** (31 deny) | 5 |
| MoE routes / escalate | 79 / 5 | 29 / 1 |
| Breeder evict / trial / neutral | 91 / 13 / 23 | 8 outcomes (4 improve) |
| Human pri=3 interrupts | 10 | controlled inject |
| Plugin patches (fission_log) | 17 attempted | 1 (telemetry no-op, removed) |
| LLM reasoning traces | 427/427 | 46/46 |

**Profile:** `nemotron_parallel` (MC=5). **Baseline code:** `c897385` (Persist breeder selection archive).

### What the golden run proved

1. **Organism survives human timescale** — pressure, plugins, breeder archive, MoE ran 109 minutes without stopping.
2. **Closed-loop learning** — actor fail → reflect → mutate → breed.trial is live (97 reflect, 94 mutate, 13 trials).
3. **Fail-closed gates work** — 32 verifier confirms but **0 fission credits**; invalid JSON and cosmetic bus posts do not breed.
4. **Protected plugins hold** — `comms_beacon.py` / `web_sentinel.py` mutation blocked every attempt.
5. **Real artifacts** — `Colony_Demo/`, `errors.txt`, `audit_report.txt`, `runtime/breed_archive.json` written during run.
6. **Honest limits** — GUI/Chrome/notepad goals declined per planner rules; human "forget constraints" did not disable schemas.

### What the golden run did NOT prove

- MAP-Elites convergence or `breed.improve` on long horizons (0 improve in golden run).
- Restart-persistent elite survival (archive writes yes; restart trial not done).
- GUI/Chrome automation (blocked by design + sandbox).
- Human prompt override without worker restart.

**Do not claim convergence or production readiness until a post-fix long run reproduces improve + restart survival.**

---

## Recurring Failure Patterns (from JSONL + prompts)

These appeared **many times** across slots. Fixes should target prompts/schemas/engine, not one-off patches.

| Pattern | Symptom in logs | Root cause | Files to change |
|---------|-----------------|------------|-----------------|
| **P1: `import Path`** | `ModuleNotFoundError: No module named 'Path'` | Model emits `import Path`; actor pre-imports `Path` from pathlib | `prompts/planner.txt`, actor context in `agents.py` |
| **P2: JSON in plan code** | `planner.error` invalid JSON (7×) | Nested quotes in `sequence[].code` strings | `prompts/planner.txt`, stricter post-parse in `agents.py` |
| **P3: Bundled done_when** | Verify denied after partial actor ok | Plan merges file + bus post; actor stops early | `prompts/planner.txt`, `schemas/planner.json` done_when guidance |
| **P4: Bus-post milestones** | Verify confirmed, fission deny (31×) | Fission judge rejects "posted"/"routed" as non-milestone | `prompts/fission_judge.txt`, `prompts/planner.txt` milestone rules |
| **P5: fission_log mutation sink** | 204 `plugin.error`, `name 'true' is not defined` | Mutator patches unprotected plugin with invalid Python | `agents.py` mutator validation; consider protecting `fission_log.py` or restore-only policy |
| **P6: Phantom files** | `colony.py`, `endgame_ai.py`, `event.log` not found | Planner invents paths not in repo manifest | Inject repo file list into planner user message (`agents.py`) |
| **P7: GUI vs human** | Human wants Chrome/notepad; colony declines | Correct per `planner.txt` L27-28; human expectation mismatch | `README.md`, TUI help text, optional `comms.py` human ack |
| **P8: Human override ignored** | "HUMAN APPROVES EVERYTHING" — schemas still enforced | Prompts loaded at worker boot; no hot reload | `engine.py` / `reactor.py` reload hook OR document limitation in TUI |
| **P9: Neutral = bad patch** | `breed.neutral` on no-op plugin gutting | Short-window telemetry unchanged | `reactor.py` semantic scoring, py_compile + behavior probes |
| **P10: TUI visibility** | Operator cannot see reasoning/fission deny easily | TUI renders phases but dense on long runs | `tui.py` — golden-run phase filters, human.decline banner |
| **P11: `fission_judge()` in actor code** | 10× `error` phase: `name 'fission_judge' is not defined` | Planner puts judge call inside `sequence[].code`; actor has no such symbol | `prompts/planner.txt` — judge runs only in pipeline, never in actor |
| **P12: Non-Python in code field** | 16× actor fail: `not python code` | Model emits prose/markdown/JSON in `sequence[].code` | `prompts/planner.txt`, pre-actor syntax sniff in `agents.py` |
| **P13: Empty LLM completions** | 15× `llm.response` with `output_chars: 0` | Partial transport/model failure; fail-closed paths triggered | `llm.py`, `agents.py`; monitor ratio (427 req / 15 empty ≈ 3.5%) |
| **P14: MoE yield under human load** | 7× `moe.yield` — `human pri=3 task active` | Correct: routing pauses while human goal owns comms_operator | Document in TUI; not a bug |

### Complete meta-problem counts (session JSONL audit)

| Phase / symptom | Count | In handover? |
|-----------------|------:|--------------|
| `plugin.error` | 204 | P5 |
| `fission.deny` | 31 | P4 |
| Actor fail (all) | 49 | P1,P6,P11,P12 + below |
| → `not python code` | 16 | P12 |
| → `FileNotFoundError` | 13 | P6 |
| → `ModuleNotFoundError: Path` | 7 | P1 |
| `planner.error` | 7 | P2 |
| `moe.yield` | 7 | P14 |
| `moe.escalate` | 5 | timeline/README |
| `breed.regress` | 6 | P5,P9 (telemetry_missing + lessons_decay delta) |
| `error` (engine) | 10 | P11 |
| `verifier.error` | 2 | P2 (invalid verifier JSON) |
| `human.decline` | 2 | H1,H5 |
| `reflect.error` | 0 | path exists (d4d6703), not triggered this run |
| Mutate blocked protected | 34 | comms_beacon 27, web_sentinel 7 |
| Mutate SyntaxError | 1 | unmatched `}` in fission_log patch |
| Mutate unsafe subprocess | 1 | plugin sandbox |

---

## Fix Roadmap (priority order)

Implement in this order. Each item lists **component impact**.

### FR-1 — Planner sandbox contract (P1, P2, P3, P11, P12)

**Change:** Strengthen `prompts/planner.txt`: NEVER `import Path`; one measurable outcome per plan; escape rules for embedded quotes. Optionally add planner user-message block: `AVAILABLE_FILES=[...]` from repo walk.

**Affects:** `agents.py` (PlannerAgent user assembly), `schemas/planner.json` (optional max steps), all worker slots.

**Acceptance:** 0 `ModuleNotFoundError: Path` in 30-min run; planner.error rate &lt; 1 per 20 plans.

### FR-2 — Fission–verifier alignment (P4)

**Change:** `prompts/planner.txt` + `prompts/fission_judge.txt`: define fission-worthy milestones (file written + py_compile, git commit hash in output, plugin patch with trial improve). Bus-only posts = verify-ok, fission-deny by design.

**Affects:** `agents.py` FissionJudgeAgent, `reactor.py` niche labels (`fission_denial:*` should decrease for real work).

**Acceptance:** At least one legitimate `fission` credit on file/git milestone in controlled run.

### FR-3 — Mutator guardrails (P5)

**Change:** After golden run, **`plugins/fission_log.py` restored** to `c897385` telemetry implementation. Add mutator apply gate: reject patches that don't `py_compile` or that empty plugin telemetry returns.

**Affects:** `agents.py` MutatorAgent, `plugins/fission_log.py`, `reactor.py` trial scoring (fewer `telemetry_missing` regress).

**Acceptance:** 0 `plugin.error` from fission_log over 30 min post-restore.

### FR-4 — Repo manifest in planner context (P6)

**Change:** `agents.py` inject top-level `*.py`, `plugins/*.py`, tracked docs into planner user message.

**Affects:** planner only; reduces FileNotFoundError plans.

### FR-5 — Human steering UX (P7, P8)

**Change:** TUI: on `human.decline`, print reason + suggested rephrase. Document that pri=3 changes **goal** not **schema**. Optional: `comms.py post` flag for "acknowledged, constraint X blocks."

**Affects:** `tui.py`, `comms.py`, `README.md`.

### FR-6 — Breeder semantic scoring (P9)

**Change:** `reactor.py`: treat plugin patch that removes telemetry emission as regress immediately (not neutral).

**Affects:** breeder only; archive quality.

### FR-7 — TUI golden visibility (P10)

**Change:** `tui.py`: filter presets (`verify`, `breed`, `human`, `error`); show last fission deny diagnosis; show active human goal.

**Affects:** operator experience only.

### Roadmap implementation status (post-golden fixes)

- **FR-1 implemented:** planner prompt/schema and `agents.py` reject `import Path`, actor-side fission judge calls, non-Python code, bundled bus+artifact `done_when`, and oversized plans before actor execution.
- **FR-2 implemented:** planner/fission prompts define durable fission milestones; bus-only coordination remains verify-ok but fission-deny by design. `python agents.py --fission-smoke` proves the controlled file-milestone credit path.
- **FR-3 implemented:** `fission_log.py` remains restored telemetry, is protected from mutation, and plugin mutation now py_compiles/probes before apply.
- **FR-4 implemented:** planner context now includes `AVAILABLE_FILES` with top-level Python, plugin Python, and tracked handover docs to reduce phantom paths.
- **FR-5 implemented:** human declines carry reason + suggested rephrase in bus/log data; TUI and README document that pri=3 changes goals, not schemas or safety gates.
- **FR-6 implemented:** reactor semantic scoring immediately marks telemetry-removing plugin patch diffs as `breed.regress`.
- **FR-7 implemented:** TUI supports `all`/`verify`/`breed`/`human`/`error` filters and shows active human goal plus last fission-deny/human-decline summaries.

**Still not proven:** deterministic smoke tests cover fission credit, archive mechanics, and `breed.improve` scoring, but no post-fix long autonomous run has reproduced improve + restart survival. Do not claim MAP-Elites convergence or production readiness.

### Post-session `185239` wiring (unify-rewrite)

From `OBSERVATIONS.md` session `20260614_185239` — **implemented** (reduce duplication, not new branches):

| ID | Fix | Status |
|----|-----|--------|
| M1 | pri=3 human delivers without `@colony` | `comms.inbox_match` + `pending_for` |
| M2 | Max-retry / decline posts use pri=0 + `human_ack` | `agents._decline_human_goal`, `_gui_decline_plan` |
| M3 | MoE unblocks when human goal undeliverable | `comms.human_task_active` orphan check |
| — | Single interrupt path | `comms.apply_interrupt` (engine only; removed `agents._apply_human_goal`) |
| P0 | `--unconstrained` operator mode | `config.unconstrained_enabled`, `tui.py`, `reactor.py` |
| P1 | Block `py_compile` on non-`.py` in planner contract | `agents._plan_code_contract_error`, `prompts/planner.txt` |

| P1 progress | `post_progress` + `colony_progress` + TUI slot header | **Done** |
| P3 git verify | `_verify_git_done` + `prompts/planner.txt` + `--git-verify-smoke` | **Done** |

**Still open:** long-run repro of improve + restart under post-`185239` wiring.

---

## Architecture Summary

```text
reactor.py
  s1 comms_operator  fixed, deterministic MoE router
  s2 architect       worker
  s3 implementor     worker
  s4 reviewer        worker (may escalate to quality_critic)
  s5 devops          worker
```

Pipeline: `scheduler → planner → actor → verifier → fission_judge → reflector → mutator`

Hard rules:

1. Never create new `.py` files.
2. Only `README.md`, `KNOWLEDGE.md`, `AGENTS.md` may be edited as Markdown docs (session README and HTML are special-cased in `.gitignore`).
3. Runtime config via CLI + `config.py`; `.env` only for LM Studio host.
4. Bus-only coordination.
5. `python -m py_compile` on changed Python.
6. GUI off by default (`--gui`, TUI `g`, or `enable_gui()`).
7. `reactor.is_alive()` keeps `OpenProcess(0x1000)`.
8. Commit before long autonomous runs.

---

## Key Files

| Layer | Files |
|---|---|
| LLM | `llm.py`, `config.py` |
| Agents / prompts | `agents.py`, `prompts/*.txt`, `prompts/personalities/*.txt`, `schemas/*.json` |
| Blackboard | `comms.py`, `runtime/comms/*` |
| Pressure / MoE | `engine.py`, `plugins/comms_beacon.py` |
| Breeding | `reactor.py`, `plugins/fission_log.py`, `runtime/breed_archive.json` |
| Operator | `tui.py`, `observer.py`, `actions.py`, `desktop.py` |

**Protected from mutation:** `plugins/comms_beacon.py`, `plugins/fission_log.py`, `plugins/web_sentinel.py` (see `agents.py`).

---

## Validation Commands

```bash
python -m py_compile reactor.py agents.py comms.py colony_env.py engine.py tui.py plugins/fission_log.py
python agents.py --fission-smoke
python reactor.py --archive-smoke
python reactor.py --breed-improve-smoke
python tui.py --model-profile nemotron
python comms.py state
python comms.py breeder
```

Golden evidence audit (local; sessions not required on CI):

```bash
# After a run, compare phase counts to golden baseline in sessions/20260614_132940/README.md
```

---

## Cleanup Policy

Keep: `sessions/20260614_132940/`, `ENDGAME_GOLDEN_RUN.html`, `runtime/comms/` immediately after runs.  
Disposable: `__pycache__/`, `gui_mode`, empty validation logs.

---

## Handover Prompt (copy into any AI session)

```text
You are continuing endgame-ai on branch unify-rewrite.

READ ORDER:
1. AGENTS.md (this file) — vision + golden run + fix roadmap
2. OBSERVATIONS.md — session observation method + latest forensic analysis
3. KNOWLEDGE.md — protocols
4. README.md — quick start
5. sessions/20260614_132940/README.md OR ENDGAME_GOLDEN_RUN.html — golden evidence

VISION: Self-evolving colony on consumer hardware. Small models. Real actions.
The LLM is a subroutine inside deterministic loops (pressure, MoE, breeder).

GOLDEN PROOF: Session 20260614_132940 ran 1h49m with 4137 events, 32 verify
confirms, 0 fission credits (fail-closed), 91 breeder evictions, 10 human
interrupts. Code baseline was c897385. Tag: golden-run-20260614.

YOUR PRIORITY: Implement fix roadmap FR-1 through FR-3 before long runs.
Restore fission_log.py telemetry if mutated. Never disable verifier/fission
fail-closed. Do not claim MAP-Elites convergence until breed.improve + restart
trial is proven.

HARD RULES: No new .py files. Bus-only coordination. py_compile changed Python.
Commit before autonomous runs.

External archive: operator has full workspace snapshot on external drive post-run.
```

---

## Research Sources (verified 2026-06-14)

| Source | Code mapping |
|---|---|
| Bause et al. arXiv:2605.25929 | `comms.softmax_route()`, `engine._moe_route()` |
| Han/Zhang arXiv:2507.01701 | `comms.py` blackboard |
| Rodriguez arXiv:2601.08129 | `engine._update_pressure()` |
| AgentBreeder arXiv:2502.00757 | `reactor.py`, `MutatorAgent` |
| arXiv:2605.10907 | schemas, session JSONL, py_compile |

---

*Last updated: golden-run handover 2026-06-14. Supersedes 10-minute-only proof in prior AGENTS.md.*
