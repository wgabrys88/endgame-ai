# RULES.md — Repository contract

**Branch:** `bare-metal` (forward dev). **`main`** = same organism, **one** instance (no bus/reactor).

---

## SYSTEM CORE — copy this entire section into any AI session

```text
DETERMINISTIC BRIEFING: endgame-ai (bare-metal branch)

SAME ARCHITECTURE — NOT TWO ORGANISMS:
  One endgame-ai instance = main.py → engine.run(board) → agent pipeline.
  main branch:     ONE instance, ONE process (no comms bus, no reactor, no breeding).
  bare-metal:      FIVE identical instances (slots 1–5) + comms blackboard + reactor parent.
  Colony is N× the same code path, not a rewrite. main could run YouTube/Notepad via GUI actor;
  colony currently regressed to run_python-only (see Capability regression).

PAPERS → CODE (read these, then grep the module):
  1. Blackboard / stigmergy (bus protocol v1)
     Repo: comms.py (post, inbox_match, events_bus.jsonl), engine._apply_bus_interrupt
     No single canonical paper — pattern is classical blackboard MAS.

  2. Mixture-of-Experts routing — Bause 2026
     Paper: https://arxiv.org/abs/2605.25929
     Read: softmax gating over agent capabilities; route work to specialist.
     Repo: comms.softmax_route, engine._moe_route (slot 1 comms_operator only).
     Grep: "Bause 2026", softmax_route, _moe_route

  3. Pressure field / temporal decay — Rodriguez 2026
     Paper: https://arxiv.org/abs/2601.08129
     Read: stagnation pressure, time-since-event escalation.
     Repo: engine._update_pressure, config.STAG_ESCALATE, board["_pressure"].
     Grep: "Rodriguez 2026", stagnation, power

  4. Quality-diversity elites — MAP-Elites
     Paper: https://arxiv.org/abs/1504.04909
     Read: archive niches, mutate, retain elites across behavioral dimensions.
     Repo: reactor.Breeder, breed_archive.json, comms.post_evolve.
     Grep: Breeder, MAP-Elites, breed_archive

  5. Planner–actor–verifier loop — ReAct (conceptual)
     Paper: https://arxiv.org/abs/2210.03629
     Read: reason → act → observe; we add verifier + fission_judge + mutator.
     Repo: agents.py pipeline classes, prompts/planner.txt, schemas/*.json.
     Grep: PlannerAgent, ActorAgent, VerifierAgent, FissionJudgeAgent

WHAT WE BUILT (papers → modules):
  1. Blackboard bus — shared JSON + event log; all inter-slot coordination.
  2. MoE router (Bause) — comms_operator softmax_route(power) → route@worker. Deterministic.
  3. Pressure field (Rodriguez) — per-slot stagnation/power → MoE + TUI.
  4. Per-slot pipeline — scheduler→planner→actor→verifier→fission_judge→reflector→mutator.
     LLM is a subroutine (llm.py), not the organism.
  5. Breeder / MAP-Elites — reactor parent evolves candidates, archives elites, respawns slots.
  6. Personality = ONE main.py process + ONE prompt file. NOT Python subclasses.
     config.Personality(name, slot, mission) + prompts/personalities/{name}.txt

WHAT IS NOT THE ORGANISM:
  - LLM backend (nemotron via LM Studio) — llm.py, swappable
  - Desktop stack (observer.py, win32.py, actions.py) — ~950 lines, present but UNWIRED in colony actor
  - TUI (tui.py) — human display + keyboard inject only
  - prompts/*.txt, schemas/*.json — data, not logic

CAPABILITY REGRESSION (main vs bare-metal — SAME desktop code, different actor path):
  | Capability              | main (1 instance)              | bare-metal colony (now)        |
  |-------------------------|--------------------------------|--------------------------------|
  | Actor execution         | execute_step + execute_verb    | run_python(code) only          |
  | GUI verbs               | click, write, press, hotkey…   | none — skipped if not python   |
  | Screen context          | ObserverAgent → screen_*     | not in pipeline                |
  | Planner steps           | text + python (is_python_step) | code field only, AST validated |
  | GUI goals               | runs when gui_mode on        | _gui_decline_plan unless --unconstrained |
  | Multi-app (Notepad etc) | worked in sessions           | desktop files exist, actor can't call them |
  FIX (next code pass): restore main-style ActorAgent path inside colony — one code path, not duplicate 7k mess.

HONEST SIZE COMPARISON:
  main branch:     24 files, ~3,656 lines — 1× instance, GUI actor, no bus/breed
  bare-metal now:  42 files, ~7,162 lines — 5× instance + reactor + bus + breed + bloat
  → ~2× lines for real multi-process wiring PLUS ~2,500 lines accidental duplication (ledger below).

CODE MINIMALISM (laws — apply when deleting):
  L1. One instance = main.py + engine.run. Colony adds only comms + reactor wrapper.
  L2. No new .py files — merge inward into existing modules.
  L3. Delete before adding — net line count must shrink each slimming pass.
  L4. One JsonRoleAgent pattern for all LLM roles; no AST zoo for planner/actor guards.
  L5. Smokes and CLI mirrors are dev-only; not shipped in organism path.
  L6. Desktop is optional module (~950 lines); organism core must run without it.
  L7. Personality = dataclass + .txt prompt, never subclasses.

TRUE MINIMAL WIRING (target, not current):
  comms bus core ............... ~400 lines
  engine loop .................. ~260 lines
  main.py entry ................ ~70 lines
  reactor spawn+control+breed .. ~500 lines
  agents pipeline (7 steps) .... ~600 lines (unified actor: python OR gui verbs)
  llm + config + log ........... ~500 lines
  SUBTOTAL ORGANISM ............ ~2,300 lines (no desktop)
  desktop (optional) ........... ~950 lines
  DELETE NEXT .................. ~2,500 lines (bloat ledger)

RUNTIME TOPOLOGY (5 child processes + 1 parent):
  tui.py → subprocess reactor.py
    reactor: slot1=comms_operator (fixed), slots2-5=workers (breedable)
    each slot: subprocess main.py → engine.run(board) — IDENTICAL binary/code
    board + runtime/comms/messages.json = blackboard
    NO direct calls between slots — only comms.py

ONE CYCLE (any slot — same engine.run):
  1. comms.apply_interrupt(board)     # human pri=3 overrides goal
  2. plugins/*.py hot-swap
  3. pressure math → post_telemetry
  4. [comms_operator only] MoE route or escalate stuck worker
  5. scheduler → planner|actor|verifier|fission|reflect|mutate chain
  6. actor: CURRENTLY run_python only — TARGET: python OR execute_verb like main

ONE CYCLE (reactor parent):
  1. respawn dead slots
  2. process_evolve_candidates() from bus
  3. evaluate_mutation_trials()
  4. save breed_archive.json

PERSONALITY TRUTH:
  config.Personality(name, slot, mission) — dataclass only
  prompts/personalities/{name}.txt — mission (only per-persona difference in code path)
  prompts/planner.txt etc. — role prompts (shared across slots)
  engine.AgentContext — binds personality to board per process

HARD INVARIANTS (do not break when slimming):
  - Bus-only between slots
  - Verifier + fission_judge fail-closed
  - py_compile on changed .py
  - No new .py files (merge inward)
  - Never commit runtime/ or sessions/

BLOAT LEDGER (delete next, ~half the repo):
  agents.py smokes ...................... ~200 lines
  agents.py plugin mutation AST ........... ~335 lines
  agents.py planner AST validators ........ ~200 lines (keep minimal guards only)
  reactor.py smokes ....................... ~250 lines
  comms.py CLI + mirror formatters ........ ~200 lines
  tui.py display ........................ ~300 lines (keep ~45-line core)
  acp_client.py (if lmstudio-only) ........ ~223 lines

READ ORDER: RULES.md (this block) → OBSERVATIONS.md session log → README.md
CODE PATH: comms.py, engine.py, agents.py, reactor.py, main.py, tui.py
RESEARCH: open arxiv links above before changing pressure/MoE/breed/actor behavior
```

---

## Architecture diagram

```mermaid
flowchart TB
    subgraph human["Human layer (not organism)"]
        TUI[tui.py display + keyboard]
        LM[LM Studio nemotron]
    end

    subgraph parent["Parent process — deterministic"]
        R[reactor.py]
        BR[Breeder MAP-Elites archive]
        R --> BR
    end

    subgraph bus["Blackboard — comms.py"]
        MSG[messages.json chat]
        EVT[events_bus.jsonl]
        INJ[inject.jsonl pri=3]
        CTL[control.jsonl reassign]
    end

    subgraph slot1["Slot 1 — comms_operator"]
        M1[main.py + Personality]
        E1[engine.run]
        MOE[MoE softmax_route]
        M1 --> E1 --> MOE
    end

    subgraph slotN["Slots 2-5 — workers same code"]
        M2[main.py + Personality]
        E2[engine.run]
        PIPE[scheduler→planner→actor→verifier→fission→reflect→mutate]
        M2 --> E2 --> PIPE
    end

    TUI -->|subprocess| R
    R -->|spawn ×5| M1
    R -->|spawn ×5| M2
    E1 & E2 & R <-->|read/write| bus
    PIPE -->|call_llm| LM
    MOE -->|route@worker| bus
    PIPE -->|post evolve| bus
    BR -->|read evolve| bus
```

ASCII equivalent:

```text
                    ┌─────────┐
                    │  tui.py │
                    └────┬────┘
                         │ spawn
                    ┌────▼────────────────────────────┐
                    │ reactor.py + Breeder (parent)   │
                    └──┬───┬───┬───┬───┬───────────────┘
           spawn     │   │   │   │   │
        ┌────────────┘   │   │   │   └────────────┐
        ▼                ▼   ▼   ▼                ▼
   ┌─────────┐      ┌─────────┐ ×4 workers (IDENTICAL main.py code)
   │ s1 MoE  │      │ s2-s5   │
   │operator │      │pipeline │
   └────┬────┘      └────┬────┘
        │                │
        └────────┬───────┘
                 ▼
        ┌────────────────────┐
        │ comms.py blackboard│
        │ messages + events  │
        └────────────────────┘
```

---

## Scientific mapping (papers → modules)

| Idea | Paper | Module | Deterministic? |
|------|-------|--------|----------------|
| Blackboard / stigmergy | (classical MAS) | `comms.py` | Yes |
| MoE gate / softmax routing | [Bause 2026](https://arxiv.org/abs/2605.25929) | `engine._moe_route`, `comms.softmax_route` | Yes |
| Pressure / stagnation escalation | [Rodriguez 2026](https://arxiv.org/abs/2601.08129) | `engine._update_pressure`, `config.STAG_ESCALATE` | Yes |
| Quality-diversity elites | [MAP-Elites](https://arxiv.org/abs/1504.04909) | `reactor.Breeder` | Yes |
| Planner–actor–verifier loop | [ReAct](https://arxiv.org/abs/2210.03629) (conceptual) | `agents.py` pipeline classes | No (LLM) |
| Fission credit / evolution | project-specific | `FissionJudgeAgent`, `comms.post_evolve` | LLM judge, deterministic post |

## Capability regression (main vs colony)

| Capability | `main` (1 instance) | `bare-metal` colony (now) |
|------------|---------------------|---------------------------|
| **Architecture** | `main.py` → `engine.run` | Same — 5× `main.py` + `comms` + `reactor` |
| **Actor** | `execute_step` + `execute_verb` (GUI verbs) | `run_python(code)` only |
| **Observer** | `ObserverAgent` in pipeline | Not wired |
| **Planner steps** | `text` field + `is_python_step` | `code` field only; `_validate_planner_contract` |
| **GUI goals** | Runs with `gui_mode` | `_gui_decline_plan` unless `--unconstrained` |
| **Desktop files** | Used by actor | Present (`actions.py`, `observer.py`, `win32.py`) but actor ignores them |

**Fix target:** one unified `ActorAgent` — python subprocess OR GUI verbs — shared by single-instance and colony modes.

## Code minimalism

1. **Same instance code** — colony is a wrapper, not a fork. `engine.run` and `agents.py` must not diverge per mode.
2. **Delete before add** — each slimming pass must reduce net lines (see bloat ledger in § SYSTEM CORE).
3. **No new `.py` files** — merge into `agents.py`, `comms.py`, `reactor.py`, etc.
4. **Organism without desktop** — core ~2.3k lines must run with `actions.py` GUI path optional.
5. **Personality = instance** — `config.Personality` + prompt `.txt`; never role subclasses.
6. **Research before changing** — read linked papers when touching pressure, MoE, breeding, or actor routing.

---

## Line budget (measured bare-metal HEAD)

| Module | Lines | Essential? | Notes |
|--------|------:|-------------|-------|
| `agents.py` | ~1511 | **partial** | ~380 pipeline + ~200 fission/evolve; **~730 bloat** (AST, smokes, mutation) |
| `reactor.py` | ~1070 | **partial** | ~500 spawn/breed/control; **~250 smokes** |
| `comms.py` | ~1041 | **partial** | ~400 bus protocol; rest mirror/TUI/actor-sandbox/CLI |
| `tui.py` | ~651 | display | Not organism |
| `observer+win32+actions` | ~951 | desktop | **Same as main had** — Notepad, Chrome, UIA |
| `engine.py` | ~263 | **yes** | Core loop |
| `llm.py` | ~358 | **yes** | LM Studio path only |
| `main.py` | ~70 | **yes** | One Personality instance |
| prompts+schemas+plugins | ~200 | data | Not code paths |
| **Total** | **~7162** | | **Target after halving: ~3500** (or ~2500 lmstudio-only, no desktop) |

**`main` branch** (`git checkout main`): 24 files, ~3656 lines — **one** `main.py` + `engine.run` instance with GUI actor + `ObserverAgent`. No bus, no reactor, no breeding. **Same architecture, scale=1** — not a different organism.

---

## What git tracks (only)

| Category | Paths |
|----------|--------|
| **Run** | `*.py`, `prompts/**`, `schemas/**`, `plugins/**`, `.env` |
| **Humans** | `README.md` |
| **AI** | `OBSERVATIONS.md` |
| **Project** | `LICENSE`, `CONTRIBUTING.md`, `RULES.md`, `.gitignore`, `.gitattributes` |

**Never commit:** `runtime/`, `sessions/`, golden artifacts.

---

## Required updates on every commit

| If you changed… | Update |
|-----------------|--------|
| Behavior, wiring, CLI | `OBSERVATIONS.md` § COLD-START |
| Human run command | `README.md` |
| System contract / bloat ledger | `RULES.md` (this file) |
| Session evidence | `OBSERVATIONS.md` § Session log |

## Code rules

1. **No new `.py` files** — merge inward.
2. **Bus-only** between slots.
3. **`python -m py_compile`** before push.
4. **Do not weaken** verifier / fission gates.
5. **Personality = instance** — `config.Personality` + prompt `.txt`; not subclasses.

## Fresh start

```bash
python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py "your long-term goal"
```