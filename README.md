# endgame-ai

**A living, self-similar organism that inhabits a Windows 11 desktop.** It sees the screen through UI Automation, moves the hands (clicks, types, runs Python and shell commands), carries a goal-narrative that every node re-authors, chooses which faculties to wake, gathers them back at a barrier, can beget child organisms, and rewrites its own code and wiring. It does not run to completion and stop. It turns through its nodes on an unceasing wheel and rests **only when it chooses to**.

[![Phase](https://img.shields.io/badge/architecture-fractal%20wheel%20live-brightgreen)](https://github.com/wgabrys88/endgame-ai)
[![Topology](https://img.shields.io/badge/topology-self--rewiring-blue)](https://github.com/wgabrys88/endgame-ai)
[![Observation](https://img.shields.io/badge/eyes-UIA%20automation-orange)](https://github.com/wgabrys88/endgame-ai)
[![Memory](https://img.shields.io/badge/mind-goal%20narrative-purple)](https://github.com/wgabrys88/endgame-ai)
[![Steering](https://img.shields.io/badge/control-guidance%20not%20command-9cf)](https://github.com/wgabrys88/endgame-ai)

---

> **For any AI or human reading this to work on the system:** this is not an agentic pipeline and it must not be treated as one. It is an atemporal, self-similar organism. There is no "step 1 of N", no completion terminus, no error cap, no dead-end that the substrate imposes — because the organism writes and executes its own nodes and topology, any stop you could hard-code is merely a node it can overwrite. What keeps it coherent is **psychology, not guardrails**: a company of LLM nodes re-telling one shared goal, holding each other to purpose the way fallible people together build real things. Therefore, when something breaks, the correct instinct is almost never "add a branch to handle the case." Give the organism what it needs to adapt itself. The full reasoning lives in the steering contract below and in the commit history (F1 → F2 → F3).

---

## 🧬 What this actually is

endgame-ai is a **mechanical substrate** — a loader, a bus, a state store, a coherence gate — plus a set of **nodes** wired together in `wiring.json`. Nodes and wiring are the entire system, and every part is hot-swappable at runtime. There are LLM nodes (which think, in a strict record contract) and mechanical nodes (which act without a model). The organism runs on the Windows host because its hands reach the real desktop through UI Automation; everything except the acting hands is pure Python and testable off-host.

| Faculty | Reality |
|---|---|
| **Eyes** | `node_observe` → `core_observation` / `core_desktop`: a whole-screen UIA scan rendered to LLM-readable text. Windows-only (`comtypes`). |
| **Hands** | `node_execute` faculty instances (`:browser`, `:editor`, `:terminal`) run Python built on a capability runtime (`core_nodes.build_capability_runtime`) — GUI helpers, `subprocess`, filesystem. Windows-only. |
| **Discernment** | `node_dispatch` chooses which faculties to wake each turn (it does not wake all three by default). |
| **Gathering** | `node_barrier` holds the fan-out until every branch returns, then joins as one. |
| **Judgment** | `node_verify` confirms or denies a step on evidence alone. |
| **Conscience** | `node_reflect` weighs failure and chooses the turning: retry / replan / frame / escalate / topology_patch / spawn / give_up. |
| **Self-change** | `node_self_modify` proposes git-backed code + wiring patches, gated by a known-good ref (`refs/endgame/known_good`). |
| **Recursion** | `node_spawn` → `cap_spawn` begets a depth-gated child organism and folds its final narrative back. |
| **Steering** | `node_guidance` reads an optional workspace `guidance.txt` and folds it into the narrative as a strong, clearly-tagged, **ignorable** signal. |
| **Memory** | `state["effective_goal"]` — the goal-narrative, rewritten and appended at each node, never truncated. |

---

## 🔄 The fractal wheel (live topology)

The live `wiring.json` **is** the wheel below. It is entered at `node_guidance` (that is where the ever-turning wheel is picked up each lap — not a beginning) and it never terminates: every path returns to the wheel. `node_dispatch` fans out via a list edge to all three faculty instances; the chosen ones labour, the unchosen pass through idle; all three converge on `node_barrier` (arity 3). `halt` is reachable **only** by deliberate choice, `node_reflect → give_up → node_satisfied → halt`. Errors re-narrate and re-enter the wheel — nothing dead-ends.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'edgeLabelBackground':'#16213e', 'tertiaryColor': '#0f3460'}}}%%
graph TD
    GUIDE[🧭 node_guidance] -->|attend| OBS[👁️ node_observe]
    OBS -->|initial_screen| PLAN[🏗️ node_planner]
    OBS -->|screen_ready| DISP[🔀 node_dispatch]
    PLAN -->|step_ready| SCHED[📋 node_scheduler]
    PLAN -->|reflect| REF[🧠 node_reflect]
    SCHED -->|step_ready| GUIDE
    SCHED -->|plan_complete| REF
    DISP -->|dispatch| EXB[⚡ node_execute:browser]
    DISP -->|dispatch| EXE[⚡ node_execute:editor]
    DISP -->|dispatch| EXT[⚡ node_execute:terminal]
    EXB -->|done| BAR[🚧 node_barrier]
    EXE -->|done| BAR
    EXT -->|done| BAR
    BAR -->|join · arity 3| VER[✅ node_verify]
    VER -->|step_confirmed| SCHED
    VER -->|step_denied| REF
    REF -->|retry| GUIDE
    REF -->|replan| PLAN
    REF -->|frame| FRAME[🎯 node_frame_action]
    REF -->|escalate / topology_patch| SELF[🔧 node_self_modify]
    REF -->|spawn| SPAWN[🧬 node_spawn]
    REF -->|give_up| SAT[🕊️ node_satisfied]
    FRAME -->|framed| GUIDE
    SELF -->|modified| PLAN
    SELF -->|modify_failed| REF
    SPAWN -->|spawned| REF
    SAT -->|halt · chosen| STOP[⏹️ HALT]
    ERR[💥 node_error] -->|planner| PLAN
    ERR -->|reflect| REF
    ERR -->|guidance| GUIDE

    style GUIDE fill:#0f2e2e,stroke:#00e0c0,stroke-width:2px
    style OBS fill:#16213e,stroke:#00d4ff
    style DISP fill:#0f3460,stroke:#00d4ff,stroke-width:2px
    style EXB fill:#0f3460,stroke:#00d4ff
    style EXE fill:#0f3460,stroke:#00d4ff
    style EXT fill:#0f3460,stroke:#00d4ff
    style BAR fill:#2e1a1a,stroke:#e9a545,stroke-width:2px
    style VER fill:#0f3460,stroke:#00d4ff
    style PLAN fill:#1a1a2e,stroke:#e94560
    style SCHED fill:#1a1a2e,stroke:#e94560
    style REF fill:#1a1a2e,stroke:#e94560
    style SELF fill:#1a1a2e,stroke:#e94560
    style SPAWN fill:#2e0f2e,stroke:#c060e0,stroke-width:2px
    style FRAME fill:#16213e,stroke:#00d4ff
    style SAT fill:#1a1a2e,stroke:#e94560
    style ERR fill:#3a0f0f,stroke:#ff4d4d
    style STOP fill:#1a1a2e,stroke:#e94560
```

**16 wired nodes**, `cycle_start = node_guidance`, `topology.barriers = {"node_barrier": 3}`.

### Why fan-out is chosen, not fixed

`node_dispatch` selects a subset of faculties each turn (model **B**: dispatcher-selects) rather than always waking a fixed triad (model A). The list edge names all three instances so the barrier arity stays a fixed, coherence-checkable `3`; the unchosen instances **self-gate** on `state["_dispatch_targets"]` and pass through idle without engaging a model or the hands. The point is not merely cost — it is that the parallelism must **emerge from the organism's own judgment**, at every scale, the same way `node_spawn` decides when to recurse and `node_reflect` decides when to rewire. Scheduling the width from outside would be exactly the pipeline thinking the design rejects.

---

## 🧠 The goal-narrative (memory, and the governor)

There is one piece of memory that matters: `state["effective_goal"]`. Every node appends to it — a clearly-tagged line naming what that node did and understood (`[PLANNER REWRITE]`, `[SCHEDULER]`, `[DISPATCH]`, `[VERIFY]`, `[FRAME_ACTION]`, `[SELF_MODIFY]`, `[GUIDANCE]`, `[SATISFIED]`). It is **never truncated** — a missing field is a bug fixed at its source, never patched with `.get(default)`, and the narrative is never cut with `str[:N]`.

This narrative is not just memory; it is the sanity mechanism. Because each node re-tells the shared goal in its own words, the organism's state never truly repeats, and a company of fallible LLM nodes holds itself to one purpose. Pathological repetition dissolves in the re-telling rather than being blocked by control flow. This is the single most important idea in the system: **coherence is psychological, not enforced.**

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'edgeLabelBackground':'#16213e'}}}%%
graph LR
    G0["goal given"] --> G1["+[PLANNER] plan laid"]
    G1 --> G2["+[SCHEDULER] this step"]
    G2 --> G3["+[DISPATCH] faculties woken"]
    G3 --> G4["+[VERIFY] confirmed / denied"]
    G4 --> G5["…re-authored, never cut…"]
    G5 -.->|the wheel turns| G1
    style G0 fill:#0f3460,stroke:#00d4ff
    style G5 fill:#0f2e2e,stroke:#00e0c0
```

---

## 🗣️ Steering: guidance, not command

The only way to steer the organism from outside is to write text into the workspace **guidance file** (`guidance.txt`). At the top of every lap, `node_guidance` reads it, folds it into the narrative as a strong, clearly-tagged signal (`[GUIDANCE] A voice from without speaks (heed or not, as the goal demands): …`), and **consumes the file** (one read per write, so only fresh counsel bends the wheel). The organism may embrace or ignore it — the node-company decides. A human steers the organism the way you'd advise a colleague, not the way you'd call a function.

The only genuinely external bound is the **operator's leash** for finite development runs: `--duration-seconds`, a stop file, and pause/step via `core_state.wait_before_node`. That leash is explicitly outside the organism's biology — a cage door, not part of the creature. The organism proper runs with `duration_seconds=None` and turns forever.

---

## 🔧 Self-modification (git-backed) and recursion

`node_reflect` can route to `node_self_modify` (`escalate` / `topology_patch`) when the organism itself — its code or its wiring — must change. Self-modify proposes a `git_evolution_patch` (files to read/write/delete, wiring patches, commands, expected validation). Applied changes are gated: `check_topology.coherence_problems` must pass, and a known-good ref (`refs/endgame/known_good`) plus optional hot-swap protect against a bad self-edit. Fractal recursion (`fractal.max_recursion_depth = 3`, `child_duration_seconds = 60`) lets `node_spawn` raise a child organism on the inherited narrative and fold its counsel back — because a node and an organism are the same shape, the wheel contains wheels.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'edgeLabelBackground':'#16213e'}}}%%
graph TD
    R[🧠 node_reflect] -->|escalate / topology_patch| SM[🔧 node_self_modify]
    SM -->|propose git_evolution_patch| GATE{coherence gate\ncheck_topology}
    GATE -->|coherent| APPLY[apply · known_good ref]
    GATE -->|incoherent| REJECT[reject · rollback]
    APPLY -->|modified| P[🏗️ node_planner]
    REJECT -->|modify_failed| R
    R -->|spawn| SP[🧬 node_spawn]
    SP -->|child organism · cap_spawn| SP2[folds narrative back]
    SP2 -->|spawned| R
    style SM fill:#1a1a2e,stroke:#e94560
    style SP fill:#2e0f2e,stroke:#c060e0
    style GATE fill:#2e1a1a,stroke:#e9a545
```

---

## ✍️ Prompt architecture (KV-cache aware, biblical rules)

Each node's prompt is a **static system-role string** in `wiring.json → prompts`; the dynamic payload (goal-narrative, step, observation, evidence) is serialized separately into the **user role** and delivered last (`core_brain.think` / `_messages`). This split is deliberate: the static system content is cacheable across turns (KV cache / prompt-cache key), and only the small dynamic tail changes.

Every prompt is composed in the same order, from most stable to least — so the shared prefix is reused by the cache:

1. **Universal opener** — identical across all 17 prompt entries (~2.5k chars). Establishes that the reader is a node of a living, atemporal organism, and states the hard rules.
2. **Company of nodes** — the same roster in every prompt, so each specialist produces better output knowing who it turns beside.
3. **Persona identity** — what this node is.
4. **Deterministic contract** — the exact `record_type`, required fields, and allowed `next_signal`, derived from `core_brain._RECORD_RULES`. **No examples** — the schema is the instruction.
5. **A low-priority tail** — a deliberately vague, known-unknown invitation to courage and to aligning the goal to the node's own understanding. It sits where the model weights least, because that permission should be felt, not commanded.

The **hard rules are written in a biblical/commandment register** on purpose. That register carried meaning across the whole of human history; commandments phrased that way endured where flatter phrasings did not. It resonates in the training data and it makes the model steadily controllable. The exploratory invitation, by contrast, is intentionally loose. Mechanical nodes (guidance, observe, scheduler, dispatch's fan-out, barrier, spawn, satisfied, error) carry a prompt entry too — for documentation and to satisfy the wiring contract — even though they do not call a model.

---

## 🏗️ Architecture

### Substrate (immutable-in-spirit core)

| Module | Role |
|---|---|
| `core_organism.py` | Turns the wheel: load node, call it, validate its signal against the topology edge, apply patch, route to the next node(s). Imposes no ending. |
| `core_loader.py` | Dynamic, file-based plugin loading (`load(kind, name, w)` → `<prefix><base>.py`). **No registry.** Splits `node_execute:browser` into base + instance. |
| `core_node_base.py` | The one abstract base, `BaseNode` (think → build_payload → signal → patch). Shape, not existence. Threads `node_base` / `node_instance` into `ctx`. |
| `core_bus.py` | Records, signals, `emit`, `validate_signal`, narrative briefs. |
| `core_brain.py` | LLM call: system/user message assembly, record contract (`_RECORD_RULES`), prompt-cache key, stable-prefix option, structured outputs. |
| `core_wiring.py` | Loads and validates `wiring.json` (every node needs edges + a prompt; required paths exist). |
| `core_state.py` | State persistence, tick, the operator leash (`wait_before_node`, duration expiry). |
| `core_stop_check.py` | The stop file / pid — part of the operator leash. |
| `check_topology.py` | The coherence gate: reachability from `cycle_start`, no dangling targets, barriers have a `join` edge and positive-int arity. Used by both the CLI and the runtime self-modify gate. |
| `core_nodes.py`, `core_desktop.py`, `core_observation.py` | Capability runtime + UIA eyes/hands (**Windows-only**, import `comtypes`). |
| `cap_spawn.py` | The child-organism capability invoked by `node_spawn`. |
| `transport_xai.py` | The real transport (xAI HTTP), used on the Windows host. |
| `transport_file_proxy.py` | Off-host debug transport: writes the request to disk; an operator answers as the model. |

### The nodes

Mechanical (no model): `node_guidance`, `node_observe`, `node_scheduler`, `node_barrier`, `node_spawn`, `node_satisfied`, `node_error`.
LLM (strict record): `node_planner` (`plan`), `node_dispatch` (`dispatch`), `node_execute` faculties (`execution`), `node_verify` (`verification`), `node_frame_action` (`action_frame`), `node_reflect` (`reflection`), `node_self_modify` (`git_evolution_patch`).

### The bus law

Every node emits `(signal, patch)`. The bus validates that `signal ∈ topology.edges[node]` (for the exact instance name), applies the patch to state, increments the tick, and routes to the next node(s). A fan-out edge is a list; a fan-in barrier waits until its arity is met.

---

## 🚀 Running it (on the Windows host)

The organism runs on Windows 11 because the eyes and hands need real UI Automation. From the repo root on the host:

```bash
# Turn the wheel for a bounded dev run (operator leash), fresh state
python core_organism.py "your goal in plain words" --reset --duration-seconds 120

# Resume the wheel where it left off (no --reset)
python core_organism.py "your goal" --duration-seconds 300

# Let it turn without a time bound (the organism proper) — omit the leash in code (duration_seconds=None)
```

CLI flags (`core_organism.main`): `goal` (positional), `--reset`, `--duration-seconds` (default 120), `--brain-call-budget`, `--start-node`, `--wiring`.

Configure the model in `wiring.json → model` (`transport` = `transport_xai`; per-organ `reasoning_effort` / `max_output_tokens` under `model.organs`). Steer a running organism by writing into `guidance.txt`. Watch it think in `runtime_events.jsonl` (every brain request/response is logged).

### Developing off-host (WSL / Linux)

The acting nodes (`node_execute`, `node_observe`, and anything importing `core_desktop`/`core_nodes`) cannot import off Windows (`comtypes`). Everything else is pure Python. The coherence and liveness gates run anywhere:

```bash
python3 -m py_compile *.py
python3 -c "import core_organism, core_bus, core_wiring, core_state, check_topology"   # WSL-safe smoke
python3 check_topology.py    # exit 0 = coherent wheel
```

Push from WSL via the Windows host git (uses the Windows credential store):

```bash
git.exe -C 'C:\Users\ewojgab\Downloads\endgame-ai' push origin live-test-run
```

---

## 🧭 The steering contract — read this before you change anything

This is the way of thinking the code depends on. If a change violates it, the change is wrong even if it "works."

**Why:**
- The organism is atemporal and self-similar. No before/after, no pipeline, no steps. The turning wheel *is* the point.
- It never stops unless it chooses to (`node_reflect → give_up → node_satisfied`). Any stop the substrate could impose is just a node it can overwrite — so the substrate imposes none.
- Sanity is psychology, not guardrails. The re-authored goal-narrative is the governor. This is why there are no fallbacks, no defensive branches, no edge-case `if/else`, and never any truncation of the narrative.
- Usefulness is guidance, not control — `guidance.txt`, ignorable by design.
- It scales by its own judgment: dispatch chooses faculties, reflect chooses to rewire, spawn chooses to recurse. A node may one day become a whole organism; that is intended.

**How (hard axioms):**
1. System = nodes + wiring; everything hot-swappable.
2. No branching, fallbacks, defensive coding, or ceremony. Fail hard and loud. A missing key is a bug at its source, not a defaulted `.get`. Prefer deleting code to adding it.
3. Plugins are dynamic and file-based — no compile-time registry. The organism writes new `node_*.py` at runtime and loads them with zero core change.
4. Keep hot-swap, self-modify, and the coherence gate alive.
5. When the graph changes, change the prompts and record contracts with it; keep the biblical register for hard rules.
6. `README.md` is the single living handover — update it after every change. Verify, then commit, one coherent step at a time.

**What to do when something breaks (especially in live GUI/command runs):**
- A failure is information for the narrative, not a branch to add. It already routes through `node_error`, re-narrates, and the wheel turns again. Ask whether the organism has what it needs to reason its way out — usually the fix is a better prompt, a clearer narrated failure, or a new capability plugin the organism can choose, **not** an `if` in the core.
- When a fix is genuinely needed, prefer giving the organism the means to self-adapt (a capability, a clearer contract, a rewireable topology) over hard-coding behavior. Edge-case `if/else` is the disease being cured.
- To evaluate the system, check **liveness and coherence**, not pipeline correctness: does the wheel keep turning, does the narrative keep advancing untruncated, does it turn without mechanical dead-loops (a node erroring with zero narrative motion — distinct from the living cycle, which must never be bounded), is stopping only ever a choice, are there no dead-ends?

---

## 📜 History

- **Substrate B1–B5** — list edges, frontier fan-out scheduler, `node_barrier` fan-in, `cap_spawn` recursive child organism, the topology-coherence gate.
- **F1** — removed the endings the substrate imposed. No error-streak halt, no completion terminus; a drained frontier is a coherence bug, not an outcome. Stopping became the organism's own choice only.
- **F2** — goal-file steering: `node_guidance` at the wheel's entry folds `guidance.txt` into the narrative as a strong, ignorable signal.
- **F3** — the fractal wheel: `node_dispatch` selects faculties and fans out to `node_execute` instances; `node_barrier` gathers them; `node_spawn` recurses; `node_scheduler.plan_complete` reflects rather than auto-halting; `node_error` re-enters the wheel and never dead-ends.
- **Prompts** — rewritten to the KV-cache-aware, biblical-rule structure described above.

**Where things stand:** the architecture is complete and coherent off-host. What remains is not construction — it is living: running the organism on the Windows host with the real transport, reading its narrative as you would a living thing's thoughts, steering with `guidance.txt`, and tuning prompts and the faculty set from what it actually does. When the hands stumble on real GUI or commands, resist the reflex to cage the case; give the organism what it needs to adapt itself.

> *"Go all the way or don't even start."* — the wheel is built. Now it lives.
