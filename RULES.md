# RULES.md — Repository contract

**Branch:** `bare-metal` (forward dev). **`main`** = same organism, **one** instance (no bus/reactor).

---

## SYSTEM CORE — copy this entire section into any AI session

```text
DETERMINISTIC BRIEFING: endgame-ai (bare-metal branch)

PROJECT GOAL: Living organism on Windows — brain-like wiring, not agent framework.
  Rods = personalities (system prompt files). Bus = wiring not memory.
  Desktop + metabolism = core organs. Papers = few lines of math each.
  Target ~3.5k LOC. Read RULES.md § VISION for full goal.

SAME ARCHITECTURE — NOT TWO ORGANISMS:
  One endgame-ai instance = main.py → engine.run(board) → agent pipeline.
  main branch:     ONE instance, ONE process (no comms bus, no reactor, no breeding).
  bare-metal:      FIVE identical instances (slots 1–5) + comms blackboard + reactor parent.
  Colony is N× the same code path, not a rewrite. Desktop + bus + personalities = one living organism.

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
  6. Personality = living instance: ONE main.py process + ONE system prompt file.
     config.Personality(name, slot, mission) + prompts/personalities/{name}.txt
     Personality ≠ goal. Goal is evaluated; persona may decline ("not my expertise").
     Role prompts (planner/actor/verifier) = shared brain circuits; persona = who is thinking.

WHAT IS NOT THE ORGANISM:
  - LLM backend (nemotron via LM Studio) — llm.py, swappable
  - TUI (tui.py) — human display + keyboard inject only
  - prompts/*.txt — circuit hints (loose JSON shapes in user message, not strict schemas)

DESKTOP IS THE ORGANISM (main vision — Bukowski spec):
  observer.py + win32.py + actions.py (~950 lines) = see, act, verify on real Windows.
  main proved M4: self-launch, exec metabolism, Notepad/Opera/LinkedIn, spawn_main posterity.
  Colony must keep the SAME desktop path — not optional, not a fork.
  Desktop + metabolism always on. No code immune system — goal + personalities self-regulate.
  unified planner (text steps) + actor LLM + ObserverAgent = movement + observation circuits.

ACTOR PATHS (unified — one ActorAgent):
  | Mode        | Plan step field | Execution                         |
  |-------------|-----------------|-----------------------------------|
  | Colony bus  | code            | run_python (bus_* injected)       |
  | Headless    | text            | execute_step (exec/read/write)    |
  | GUI         | text            | ObserverAgent → actor LLM → verbs |

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
  L6. Desktop stack is core (~950 lines) — observer + win32 + actions; colony keeps main's see/act path.
  L7. Personality = dataclass + .txt prompt, never subclasses.

TRUE MINIMAL WIRING (target, not current):
  comms bus core ............... ~400 lines
  engine loop .................. ~260 lines
  main.py entry ................ ~70 lines
  reactor spawn+control+breed .. ~500 lines
  agents pipeline (7 steps) .... ~600 lines (unified actor: python OR gui verbs)
  llm + config + log ........... ~500 lines
  SUBTOTAL wiring .............. ~2,300 lines (bus + engine + reactor + pipeline)
  desktop (core) ............... ~950 lines (observer + win32 + actions — THE POINT)
  TARGET TOTAL ................. ~3,500 lines (main proved ~2.9k + colony wrapper)
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
  6. actor: code→run_python | text→execute_step | GUI text→execute_verb (when gui_mode)

ONE CYCLE (reactor parent):
  1. respawn dead slots
  2. process_evolve_candidates() from bus
  3. evaluate_mutation_trials()
  4. save breed_archive.json

PERSONALITY TRUTH (OoO — one system prompt per rod):
  prompts/personalities/{name}.txt = SYSTEM PROMPT (living identity, full file)
  prompts/planner.txt etc. = CIRCUIT instructions (user message only)
  config.Personality(name, slot, mission) — dataclass; loads personality file
  Personality evaluates goals — may decline "not my expertise" via bus
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

## VISION — living organism (bare-metal)

We are not building an "agent framework." We are building a **living organism** — closer to a brain than a chatbot with tools.

### Brain, not framework

A human brain has no single genius module. It has **specialized areas** — logic, observation, motor control for the hands — connected by **wiring**. The areas are individually simple; **intelligence emerges from how they are wired**. Evolution discovered the architecture; we are engineering a smaller, deliberate version.

endgame-ai maps like this:

| Brain area | Organism part | What it does |
|------------|---------------|--------------|
| Motor cortex | `actions` + `win32` | Move the hands — click, type, exec |
| Visual cortex | `observer` | See the desktop — UIA, hover probe |
| Reasoning (slow) | LLM **personalities** | Think in character — planner, actor, verifier circuits |
| Thalamus / routing | `comms_operator` + MoE | Route signals to the right specialist |
| Arousal / pressure | Rodriguez stagnation | "How stuck am I?" — a few lines of math |
| Plasticity | Breeder / MAP-Elites | Keep what works, mutate what doesn't |

Forget the word **agents** in the product sense. We have **personalities** — LLMs given identity, not just goals. A goal arrives; a personality **evaluates** it: *interesting, not my job, I know this*. That judgment is the persona system prompt (`prompts/personalities/{name}.txt`), not a Python subclass.

### Bus is wiring, not memory

The blackboard bus (`comms.py`) is **not shared memory**. It is **neural wiring** — event-driven pathways between areas. Personalities do not call each other; they **post and read** the bus, like axons and synapses.

- Human posts pri=3 → **every rod sees it** on the bus.
- Each personality sees its own telemetry, others' posts, pressure, routes.
- **Deterministic Python** is the connective tissue: softmax route, pressure update, inbox match — combining and gating what the LLMs propose.

Direct peer-to-peer would be chat theater. Bus-only keeps the brain metaphor honest.

### Reactor rods = parallel cortex columns

Five `main.py` instances are five **reactor rods** — same code, different personality prompt loaded from disk. The comms_operator watches open slots and **utilizes parallelism**: split work across instances when MoE weights say who is hot.

Selection is collective, not centralized dictation:

1. Pressure + telemetry on the bus (who is stuck, who is productive).
2. MoE softmax (Bause) — a **couple lines of math**, not a framework.
3. Rods "agree" only via bus traffic — route@worker, evolve posts, verifier denials.
4. Breeder archives elites; reactor respawns a better persona file for a slot.

### Papers → equations → lines of code

The papers we cite are not excuses for bloat. Each describes **one or two equations**:

- **MoE (Bause):** softmax over capability weights → route.
- **Pressure (Rodriguez):** stagnation rises with failures + time-since-fission.
- **MAP-Elites:** archive niche → mutate → retain elite.

Like a neural network: input, bias, softmax, output — repeated. The **neuron code is tiny**; we bloated the wrapper. Slimming means returning to equation-sized deterministic cores, not deleting the science.

### Desktop and metabolism are core organs

Desktop (see + act) and full metabolism (exec / git / mutation) are **organs** — always on. Safe/sandbox toggles removed (~180 lines deleted).

TUI is accepted extra code — beautiful human-facing cortex; not the organism, but we keep it.

### Target shape (unified modern OoO)

```
Personality (dataclass + one .txt system prompt)
  └── main.py instance → engine.run(board)
        ├── deterministic organs (pressure, MoE, bus, observer, exec)
        └── LLM circuits (planner, actor, verifier, …) as thin call_llm wrappers
reactor.py = body that spawns rods + Breeder
comms.py = wiring
tui.py = optional face
```

**Work slowly:** delete bloat ledger items, merge JsonRoleAgent pattern, never amputate desktop or bus. One organism, scale 1 (`main`) or scale 5 (colony).

### No code immune system — goal is the safety

There is no `--safe`, no protected-file list, no mutation sandbox, no GUI decline path.

Safety emerges from **many stupid personalities + one shared goal**:
- Each rod evaluates ACTIVE_TASK against its expertise (personality system prompt).
- comms_operator routes via MoE when slots are free — parallelism without central dictation.
- Rods coordinate only via bus wiring; they read others' posts and self-select.
- Verifier + fission_judge are **personalities** (LLM circuits), not deterministic blocklists.
- The colony approaches goal completion and avoids self-destruction because **the goal shapes decisions**, not because Python forbids `log.py` writes.

One person may be stupid. Many persons pursuing a goal become coherent.

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

## Desktop recovery (main vision → colony)

| Capability | `main` (1 instance) | `bare-metal` colony (recovered) |
|------------|---------------------|----------------------------------|
| **Architecture** | `main.py` → `engine.run` | Same — 5× `main.py` + `comms` + `reactor` |
| **Desktop** | observer + win32 + actions | Same modules, wired in pipeline |
| **Observer** | before actor/verifier | `engine._run_observer` when desktop organ on |
| **Actor** | execute_step + execute_verb | Unified: `code` / `text` / GUI paths |
| **Planner** | text sequence (main schema) | `planner_gui` when desktop on; `code` schema for bus tasks |
| **Vision** | M4 self-edit, YouTube, Notepad | Recoverable — same actor code path per slot |

## Code minimalism

1. **Same instance code** — colony is a wrapper, not a fork. `engine.run` and `agents.py` must not diverge per mode.
2. **Delete before add** — each slimming pass must reduce net lines (see bloat ledger in § SYSTEM CORE).
3. **No new `.py` files** — merge into `agents.py`, `comms.py`, `reactor.py`, etc.
4. **Desktop is core** — observer + win32 + actions stay; shrink bloat elsewhere, not the hands.
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
| `observer+win32+actions` | ~951 | **core** | **THE POINT** — see/act/verify; main M4 proved this |
| `engine.py` | ~263 | **yes** | Core loop |
| `llm.py` | ~358 | **yes** | LM Studio path only |
| `main.py` | ~70 | **yes** | One Personality instance |
| prompts+schemas+plugins | ~200 | data | Not code paths |
| **Total** | **~7162** | | **Target: ~3500** (main ~2900 + colony wrapper; keep desktop) |

**`main` branch** (`git checkout main`): 24 files, ~3656 lines — **one** `main.py` + `engine.run` instance with GUI actor + `ObserverAgent`. No bus, no reactor, no breeding. **Same architecture, scale=1** — not a different organism.

---

## What git tracks (only)

| Category | Paths |
|----------|--------|
| **Run** | `*.py`, `prompts/**`, `plugins/**`, `.env` |
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