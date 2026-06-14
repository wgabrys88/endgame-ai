# RULES.md — Repository contract

**Branch:** `bare-metal` (forward dev). **Legacy:** `main` (single-process demo, not a subset).

---

## SYSTEM CORE — copy this entire section into any AI session

```text
DETERMINISTIC BRIEFING: endgame-ai colony (bare-metal branch)

WHAT WE BUILT (from papers → code):
  1. Blackboard bus (protocol v1) — shared JSON state + event log. All coordination here.
  2. Mixture-of-Experts router (Bause 2026) — comms_operator reads telemetry, softmax_route(power), posts route@worker. Deterministic, no LLM.
  3. Pressure field (Rodriguez 2026) — stagnation/power per slot from failures + time-since-fission. Feeds MoE + TUI.
  4. Per-slot pipeline (same code every slot) — scheduler→planner→actor→verifier→fission_judge→reflector→mutator. LLM is a subroutine.
  5. AgentBreeder / MAP-Elites (reactor parent) — evolve candidates on bus; archive elites; respawn personas. Parent process only.
  6. Personality = ONE main.py process + ONE prompt file. NOT separate Python classes. architect/implementor/reviewer are labels + .txt missions.

WHAT IS NOT THE ORGANISM:
  - The LLM (nemotron) — replaceable backend in llm.py
  - Desktop stack (observer.py, win32.py, actions.py) — copied from legacy main; ~950 lines; enables Notepad/Chrome when GUI on. Same capability main had in 3.6k total lines.
  - TUI (tui.py) — human display only
  - prompts/*.txt, schemas/*.json — data, not logic

HONEST SIZE COMPARISON:
  main branch:     24 files, ~3,656 lines — 1 process, desktop+YouTube, NO bus, NO breeding, NO 5-slot colony
  bare-metal now:  42 files, ~7,028 lines — 5 slots + reactor, full bus+breed, SAME desktop stack bolted on
  → We doubled line count for multi-process wiring. We also duplicated validators, mutation AST, smokes, TUI formatting.

TRUE MINIMAL WIRING (target, not current):
  comms bus core ............... ~400 lines (post, route, inbox, telemetry, interrupt)
  engine loop .................. ~260 lines (plugins, pressure, MoE gate, pipeline walk)
  main.py entry ................ ~70 lines (Personality.from_env → engine.run)
  reactor spawn+control+breed .. ~500 lines (5 Popen, archive, trial scoring)
  agents pipeline (7 steps) .... ~600 lines (one JsonRoleAgent pattern, no AST zoo)
  llm + config + log ........... ~500 lines
  SUBTOTAL ORGANISM ............ ~2,300 lines (deterministic + LLM calls, no desktop)
  desktop (optional) ........... ~950 lines (observer+win32+actions — keep or fork)
  CURRENT BLOAT TO DELETE ...... ~2,500 lines (see Bloat ledger below)

RUNTIME TOPOLOGY (5 processes + 1 parent):
  tui.py → subprocess reactor.py
    reactor: slot1=comms_operator (fixed), slots2-5=workers (breedable)
    each slot: subprocess main.py → engine.run(board) in a loop
    board + runtime/comms/messages.json = blackboard
    NO direct calls between slots — only comms.py

ONE CYCLE (worker process):
  1. comms.apply_interrupt(board)     # human pri=3 overrides goal
  2. plugins/*.py hot-swap
  3. pressure math → post_telemetry
  4. [comms_operator only] MoE route or escalate stuck worker
  5. scheduler → planner|actor|verifier|fission|reflect|mutate chain
  6. actor runs Python subprocess (actions.run_python) with comms bus_* injected

ONE CYCLE (reactor parent):
  1. respawn dead slots
  2. process_evolve_candidates() from bus
  3. evaluate_mutation_trials()
  4. save breed_archive.json

PERSONALITY TRUTH:
  config.Personality(name, slot, mission) — dataclass only
  prompts/personalities/{name}.txt — mission text (the ONLY per-persona difference in code path)
  prompts/planner.txt etc. — role prompts (same for all slots)
  engine.AgentContext — binds personality to board per process

HARD INVARIANTS (do not break when slimming):
  - Bus-only between slots
  - Verifier + fission_judge fail-closed
  - py_compile on changed .py
  - No new .py files (merge inward)
  - Never commit runtime/ or sessions/

BLOAT LEDGER (delete next, ~half the repo):
  agents.py smokes ...................... ~200 lines (move to dev-only or delete)
  agents.py plugin mutation AST ........... ~335 lines
  agents.py planner AST validators ........ ~200 lines (keep minimal guards only)
  reactor.py smokes ....................... ~250 lines
  comms.py CLI + mirror formatters ........ ~200 lines
  tui.py display ........................ ~300 lines (keep 45-line core)
  acp_client.py (if lmstudio-only) ........ ~223 lines

READ ORDER: RULES.md (this) → OBSERVATIONS.md session log → README.md run command
CODE PATH: comms.py, engine.py, agents.py (pipeline only), reactor.py, main.py, tui.py
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

| Idea | Paper ref in code | Module | Deterministic? |
|------|-------------------|--------|----------------|
| Blackboard / stigmergy | bus v1 protocol | `comms.py` | Yes |
| MoE gate / softmax routing | Bause 2026 | `engine._moe_route`, `comms.softmax_route` | Yes |
| Pressure / stagnation escalation | Rodriguez 2026 | `engine._update_pressure`, `config.STAG_ESCALATE` | Yes |
| Quality-diversity elites | MAP-Elites pattern | `reactor.Breeder` | Yes |
| LLM planner-actor-verifier | classical agent loop | `agents.py` pipeline classes | No (LLM) |
| Fission credit / evolution | project-specific | `FissionJudgeAgent`, `comms.post_evolve` | LLM judge, deterministic post |

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
| **Total** | **~7028** | | **Target after halving: ~3500** (or ~2500 lmstudio-only, no desktop) |

**main branch** (`git checkout main`): 24 files, ~3656 lines — single `engine.run` + math agents (stagnation/lorenz/pid) + desktop. Could play YouTube. **No colony, no bus, no breeding.** Not a smaller version of bare-metal.

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