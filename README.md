# endgame-ai

**A living Windows desktop organism — not an agent framework.**

It runs indefinitely on your machine, controls mouse and keyboard, reads the screen (including hover-probe discovery like a human glancing around), edits its own code, and evolves under pressure. Local LLMs via [LM Studio](https://lmstudio.ai/) — typically a small Nemotron-class model (~4B), slow but free, optionally parallel.

This document is the **project bootstrap**. Future human and AI sessions should start here. It states what exists in code today, what we are building toward, and how we will prove the design works.

---

## For AI coding agents — read this first

| Item | Value |
|------|-------|
| **Active branch** | `merge-prep` (development line toward `main`) |
| **Sanitized baseline tag** | `sanitize-ready-20260615` → commit `9102d0a` |
| **Archived experiment tag** | `experiment-pure-python-20260615` → pure-Python rewrite (4 commits ahead of baseline; do not assume it is the active direction) |
| **`main` branch** | Older single-process organism (~2,900 LOC, Lorenz/PID math thread, no colony). `merge-prep` is ~245 commits ahead with a different architecture. |
| **Deep research report** | `deep-research-report.md` — literature mapping for Role-Based Blackboard + Hierarchical Mutators |
| **Do not assume** | The 5-slot colony is superior to a single rod. The colony must **earn its keep through ablation**. |
| **Do not code blindly** | Gaps listed in [Known gaps](#known-gaps-code-today-vs-target) are intentional next work, not bugs to “fix” without context. |

**Mission (owner-confirmed):** Replace a human for **any task on this computer** — desktop GUI and repo/code work equally. The organism has **no permanent goal**; it rests when satisfied but never exits. Long-horizon “eternal” operation is a design requirement, not a demo feature.

**Execution modes (both required):** Like a CPU that can be single-core time-sliced *or* multi-core parallel — the system must run as **one rod (unicore)** or **colony (multicore)**. Parallel is a feature; unicore must always work. One slightly larger model may outperform several tiny ones on some tasks — keep both paths.

---

## What it is

Traditional agents: `task → done → exit → dead`.

endgame-ai: `task → plan → act → verify → fission → pressure → mutate → what next? → never stop`.

| Metaphor | Meaning in code |
|----------|-----------------|
| **Rod** | One `main.py` process with a personality — runs the full pipeline loop |
| **Colony** | `reactor.py` supervises 5 rods + MAP-Elites breeder |
| **Blackboard** | `comms.py` — shared bus (`messages.json` + `events_bus.jsonl`) |
| **Pressure** | Stagnation rises when stuck → triggers reflector → mutator |
| **Fission** | Verified novel work earns credit; repeats denied by fission judge |
| **DNA** | Prompt files under `prompts/` — evolved by mutator + breeder |
| **Satisfied** | Goal verified + inbox quiet → reduced metabolism (`DELAY_SATISFIED`), not shutdown |

This is closer to a **living organism** than “agentic AI”: metabolism (cycle timing), reproduction (fission), immune response (reflector/mutator), endocrine state (satisfied), and a nervous system (bus).

---

## What it is not

- Not LangChain / AutoGen / CrewAI wrapped around tools
- Not a chat UI that pretends to have hands
- Not a framework where the model is the product — **the runtime loop is the product**
- Not proven multi-agent superiority — that is a **hypothesis under test**

---

## Theoretical foundation

The target architecture name (from `deep-research-report.md`):

> **Role-Based Blackboard Multi-Agent System with Hierarchical Prompt Evolution**

No single paper defines this exact stack. The components are well grounded:

| Concept | Relevance to endgame-ai | Key reference |
|---------|-------------------------|---------------|
| Blackboard coordination | Shared bus; specialists respond to posted work instead of rigid master–slave control | Salemi et al., *LLM-Based Multi-Agent Blackboard System for Information Discovery in Data Science*, [arXiv:2510.01285](https://arxiv.org/abs/2510.01285) (2025–2026) |
| Role / SOP specialization | Personas are planner-level role priors (architect, implementor, …) | Hong et al., *MetaGPT*; Li et al., *CAMEL* |
| Mixture-of-Agents (task level) | `comms_operator` routes whole rods, not token-level MoE | Wang et al., *Mixture-of-Agents Enhances LLM Capabilities* |
| Routing as optimization | When to collaborate vs stay single is task-dependent | *MasRouter: Learning to Route LLMs for Multi-Agent Systems*, [arXiv:2502.11133](https://arxiv.org/abs/2502.11133) (2025) |
| Fast local adaptation | Reflector → mutator loop on actor/verifier behavior | Shinn et al., *Reflexion*; Madaan et al., *Self-Refine* |
| Slow planner evolution | Dedicated persona mutates planner prompts with scored evaluation | Fernando et al., *Promptbreeder*; Yang et al., *OPRO* |
| Desktop evaluation (external) | Sanity check against real OS tasks | Xie et al., *OSWorld*, [arXiv:2404.07972](https://arxiv.org/abs/2404.07972) |

**Core design conclusion (deduced):** Parallel rods help only when roles, routing, permissions, and verification are genuinely differentiated — not when five copies of the same loop broadcast chatter. The colony claim must be validated by ablation against the strongest single-rod baseline.

---

## Architecture today (`merge-prep`)

```
┌──────────────────────────────────────────────────────────────┐
│  TUI (tui.py) — terminal dashboard, spawns reactor           │
│    └── Reactor (reactor.py) — 5 slots, MAP-Elites breeder    │
│          ├── Slot 1: comms_operator  (thalamus / MoE router) │
│          ├── Slot 2: architect       (design / navigation) │
│          ├── Slot 3: implementor     (execution / files)     │
│          ├── Slot 4: reviewer        (verification)          │
│          └── Slot 5: devops          (git / infra health)    │
└──────────────────────────────────────────────────────────────┘
         │                              │
    ┌────▼─────┐                   ┌────▼────┐
    │ Blackboard│                  │ LM Studio│
    │ (comms.py)│                  │ (local)  │
    └──────────┘                   └──────────┘
```

### Per-rod pipeline (`engine.py`)

Each `main.py` process runs the same stage graph:

```
scheduler → planner → actor → verifier → fission_judge
                ↑         ↓ denied
                └── reflector → mutator ──┘
```

Interrupts: bus messages can preempt the current goal (`comms.apply_interrupt`). Plugins in `plugins/*.py` hot-load every cycle.

### Biological mapping

| Component | Biology | Implementation |
|-----------|---------|----------------|
| Thalamus | All external stimuli enter here | `comms_operator` — sole human-goal receiver, decomposes + routes |
| Frontal cortex | Planning, strategy | Planner + persona SOP |
| Motor cortex | Execution | `ActorAgent` — Python `exec` or GUI verbs |
| Visual cortex | Screen perception | `desktop.py` — hover probe + UIA tree merge |
| Autonomic | Pressure fields | `_update_pressure` in `engine.py` |
| Immune | Diagnose failures | `ReflectorAgent` |
| Adaptive immunity | Patch behavior | `MutatorAgent` |
| Reproductive | Select fit DNA | `FissionJudgeAgent` + `reactor.Breeder` (MAP-Elites) |
| Endocrine | Low metabolism when done | `_is_satisfied` |

### Blackboard protocol (`comms.py`)

Two stores, one envelope schema (v1):

- `runtime/comms/messages.json` — intent (route, request, ping, evolve, …)
- `runtime/comms/events_bus.jsonl` — observation (telemetry, pipeline phases)

MoE routing: `comms_operator` reads colony telemetry (`stagnation`, `power`, `velocity`), softmax-gates maintenance work, escalates stuck rods to alternates (often `quality_critic`).

### Desktop observation (`desktop.py`)

**Works today:** Hover-probe regions sweep the screen; discoveries merge with UIA accessibility tree. Browsers that lie to static trees are partially compensated by probe-first discovery (`_merge`: probe primary, tree adds depth).

Actor uses element IDs from the merged book; verifier checks `print()` evidence and screen state.

### Personas (`config.py` + `prompts/personalities/`)

| Persona | Slot | Contract (prompt-level) |
|---------|------|-------------------------|
| `comms_operator` | 1 | Receive human goals; decompose; `bus_route()` only; no file edits |
| `architect` | 2 | Design, navigation, structure |
| `implementor` | 3 | Execute, patch files, GUI actions |
| `reviewer` | 4 | Verify outcomes; report problems |
| `devops` | 5 | Git, build, packaging health |
| `quality_critic` | pool | Escalation target when rods stuck; not a default slot |

**Prompt layers today:**

- `prompts/planner.txt`, `actor.txt`, `verifier.txt`, … — shared **circuit** instructions
- `prompts/personalities/{name}.txt` — **role identity** (used as LLM system prompt for *all* circuits in that rod)

### Model profiles (`config.py`)

| Profile | Behavior |
|---------|----------|
| `nemotron` | 1 concurrent LLM call, global lock — **unicore mode** |
| `nemotron_parallel` | 5 concurrent calls, no lock — **multicore mode** |

Target hardware: local LM Studio with Nemotron-class ~4B model. Slow is acceptable; cost is zero marginal dollars.

### CPU analogy (owner requirement)

| CPU concept | endgame-ai equivalent |
|-------------|----------------------|
| Single physical core, time-sliced apps | `nemotron` profile, or colony with one active rod |
| Multiple cores | `nemotron_parallel`, 5 slots each in LLM wait simultaneously |
| Process scheduler | `reactor.py` + `comms_operator` MoE routing |
| Core parking / turbo | Satisfied state (slow cycles) vs human interrupt (full priority) |

**Both modes stay in the codebase.** Future evolution may evict personas, respawn with different models, or collapse to one rod — unconstrained by design.

---

## Target architecture (what we are building toward)

Derived from `deep-research-report.md` + owner answers + code audit.

### 1. Hierarchical mutators

```
FAST (per rod, frequent):
  reflector → local mutator → patch actor.txt / verifier.txt / plugins ONLY

SLOW (colony-level, benchmarked):
  planner-mutator persona → propose diffs to planner SOPs
                         → shadow-eval on held-out tasks
                         → promote only if success↑ and regression↓
```

**Why:** Reflexion-style loops fix execution; Promptbreeder-style loops fix role strategy. Mixing both inside every rod’s `patch_prompt` destabilizes the role priors that make the colony useful.

### 2. Planner-only blackboard

Only planners publish task claims, partial results, and verdict summaries. Actors and verifiers stay local; their outputs reach siblings through planner summaries.

### 3. Independent reviewer (runtime-enforced)

Reviewer must confirm or deny with evidence — not fix while reviewing. Requires prompt contract **and** permission enforcement (future RBAC on bus + action signals).

### 4. Ablation ladder (prove or simplify)

| Stage | Configuration | What it tests |
|-------|---------------|---------------|
| **A** | Single rod, best tuned, unicore | Strongest baseline |
| **B** | Single rod + local actor/verifier mutator only | Value of fast adaptation without colony |
| **C** | 5 personas, planner-only bus policy | Value of role differentiation |
| **D** | C + hierarchical mutators | Value of split adaptation |
| **E** | D + dedicated planner-mutator + shadow eval | Full self-improving organism |

**Primary metrics:** task success, first-pass success, reviewer false-positive rate, tokens per solved task, bus overhead ratio, mutation uplift, regression rate.

**Task families (internal first):** desktop GUI (notepad, browser, focus), repo hygiene (py_compile, git, small patches), routing/decomposition (`bench.py` comms scenarios).

External sanity: [OSWorld](https://os-world.github.io/) when harness exists.

### 5. Eternal operation / goal model

There is no single permanent mission string that defines the organism.

| Layer | Source | Persistence |
|-------|--------|-------------|
| Human task | Bus inject / TUI | Until verified or superseded by higher priority |
| Colony drift | `runtime/colony_goal.txt` | Long-horizon direction; comms_operator reads it |
| Idle metabolism | Per-persona self-directed maintenance | When no human pri=3 task |

“Eternal” means the process loop and reactor supervision never treat completion as exit — only satisfied slowdown. Re-planning after success is mandatory, not optional.

---

## Known gaps (code today vs target)

Honest audit of `merge-prep` at `9102d0a`:

| Gap | Current behavior | Target |
|-----|------------------|--------|
| **Unified mutator** | `MutatorAgent` can `patch_prompt` → rewrites entire `personalities/{name}.txt` (affects planner + actor + verifier) | Local mutator: actor/verifier/plugins only |
| **No planner-mutator** | No persona dedicated to planner SOP evolution | New persona or time-shared slot with shadow eval |
| **Bus visibility** | All phases can post; exec steps call `bus_route` from any rod | Planner-only publish contract + enforcement |
| **Reviewer independence** | Reviewer runs full planner→actor→verifier chain | Verify-only lane at runtime |
| **No ablation modes** | `reactor.py` always spawns 5 slots | Config flags: unicore / colony / planner-only-bus |
| **bench.py scope** | 30 isolated LLM circuit scenarios | Extend to end-to-end colony runs with external verifier |
| **Per-model persona evolution** | One profile per reactor launch | Future: per-slot model assignment, evict/respawn with different LLM |

Archived experiment (`experiment-pure-python-20260615`) explored pure-Python signal output instead of JSON circuits. It is preserved for reference; **active line does not follow it** until ablation justifies the migration.

---

## Implementation roadmap

Ordered to minimize wasted parallelism.

### Phase 0 — Measurement (current priority)

- [ ] Add reactor config: `unicore` (1 rod) vs `colony` (5 rods)
- [ ] Document baseline prompts for single-rod generalist
- [ ] Run ablation A vs C on 10 internal desktop + 10 repo tasks
- [ ] Record: success, latency, tokens, bus overhead

### Phase 1 — Split mutators

- [ ] Restrict local mutator to `actor.txt`, `verifier.txt`, `plugins/`
- [ ] Remove `patch_prompt` → personality from per-rod mutator
- [ ] Separate prompt registry: circuit vs persona SOP

### Phase 2 — Planner-only bus

- [ ] Message schema: `{claim, done_when, verdict, confidence}`
- [ ] Prompt contract: only planners call `bus_route` / `bus_post` for coordination
- [ ] Runtime RBAC (block bus writes from actor/verifier phases)

### Phase 3 — Planner-mutator persona

- [ ] Add persona (slot 6 or idle-time on slot 1)
- [ ] `propose_prompt_patch(target, diff, rationale)` flow
- [ ] Shadow eval via `bench.py` + `replay.py` before promotion

### Phase 4 — Reviewer hardening

- [ ] Reviewer slot: verifier + bus publish only; no file patch verbs
- [ ] Track false-positive completion rate

### Phase 5 — Merge to `main`

- [ ] Colony beats unicore baseline on success-adjusted cost **or** documented decision to ship unicore-first
- [ ] PR from `merge-prep` → `main`

---

## Quick start

**Requirements:** Windows 11, Python 3.11+, LM Studio running locally (default `http://localhost:1234`).

```powershell
git clone https://github.com/wgabrys88/endgame-ai.git
cd endgame-ai
git checkout merge-prep

# Optional: .env
# ENDGAME_LMS_HOSTS=http://localhost:1234

# Colony (5 slots, parallel profile)
python tui.py "Open notepad and write hello" --model-profile nemotron_parallel

# Unicore (single rod, locked LLM)
python main.py "Open notepad and write hello" --model-profile nemotron
```

### Tools

```powershell
# 30 LLM circuit scenarios
python bench.py --list
python bench.py --scenarios plan_open_notepad,actor_click_edit --output results.txt

# Replay session LLM calls
python replay.py
python replay.py sessions\<timestamp>
```

### Plugins

Drop `plugins/my_plugin.py` with `def run(board): ...` — hot-loaded every engine cycle.

---

## File map

| File | Role |
|------|------|
| `main.py` | Single rod entry point |
| `engine.py` | Organism loop, pressure, MoE gate, plugins |
| `agents.py` | Pipeline agents (planner, actor, verifier, reflector, mutator, fission_judge) |
| `reactor.py` | Multi-process supervisor, MAP-Elites breeder, respawn |
| `comms.py` | Blackboard bus, routing, interrupts, telemetry |
| `desktop.py` | Win32/UIA observation, hover probe |
| `actions.py` | GUI verbs + Python exec runner |
| `llm.py` | LM Studio HTTP client (+ ACP backend) |
| `config.py` | Personas, profiles, paths, thresholds |
| `tui.py` | Terminal dashboard |
| `bench.py` | LLM benchmark harness (30 scenarios) |
| `replay.py` | Session replay / model comparison |
| `prompts/` | Circuit + personality DNA |
| `runtime/comms/` | Live bus state |
| `runtime/breed_archive.json` | MAP-Elites elite prompts |
| `deep-research-report.md` | Full literature + technique porting guide |

---

## Git state (session bootstrap)

| Ref | Purpose |
|-----|---------|
| `merge-prep` | Active development branch |
| `main` | Production line (older architecture) |
| `sanitize-ready-20260615` | Frozen snapshot of merge-prep start point |
| `experiment-pure-python-20260615` | Archived 4-commit experiment |
| `unify-rewrite` | Branch pointer at experiment (deletable; tag preserves history) |

---

## References

1. Salemi et al. — LLM-Based Multi-Agent Blackboard System — [arXiv:2510.01285](https://arxiv.org/abs/2510.01285)
2. MasRouter — Learning to Route LLMs for Multi-Agent Systems — [arXiv:2502.11133](https://arxiv.org/abs/2502.11133)
3. Fernando et al. — Promptbreeder — [arXiv:2309.16797](https://arxiv.org/abs/2309.16797)
4. Shinn et al. — Reflexion — [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
5. Hong et al. — MetaGPT — [arXiv:2308.00352](https://arxiv.org/abs/2308.00352)
6. Xie et al. — OSWorld — [arXiv:2404.07972](https://arxiv.org/abs/2404.07972)
7. Project literature synthesis — `deep-research-report.md`

---

## License

MIT