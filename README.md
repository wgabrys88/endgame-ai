# endgame-ai — Wiring-First Topology

**Branch:** `codex-unify-bus`  
**Control plane:** `prompts/wiring.json` (machine truth — hot-reloads on every `colony.step()`)  
**Schema:** `endgame-topology/v1`

We are **switching from Python-as-architecture to wiring-as-architecture**. Python is not deleted — it is **wired**: each module exposes dumb, self-documenting node handlers. The developer controls how the system starts, flows, constructs context, executes actions, routes reasoning feedback, and shuts down — all by editing JSON edges and pipeline steps, not by adding `if/else` branches in code.

---

## The Goal

Build a closed self-evolution loop where one instance (Manager) observes and improves a second (Student) using only the Windows desktop. Long-term: **zero hidden control flow in Python**. Every connection — including where `MODEL REASONING` goes after a response, whether an action fans out to desktop + bus + logging, or whether smoke runs chain-after-exit — is declared in `wiring.json`.

**Plasticity:** Like synaptic rewiring in the brain, topology edges can be changed without rewriting executors. An `enter` action today may tomorrow also wire to a second target (audit log, peer notification, suite step). Fan-out = multiple edges from one node on the same signal.

---

## Architecture (Current)

```
wiring.json
  ├── topology.nodes/edges     → GraphExecutor walks these each cycle
  ├── request.unified          → USER block assembly (GOAL, SCREEN, LAST REASONING, …)
  ├── response.unified.pipeline → declarative steps (parse, when, guard, emit, …)
  ├── response.unified.guards  → premature_done, repeat_block, advance_hints
  ├── feedback.reasoning       → where reasoning history goes / when it appends
  ├── transitions              → event → next phase
  ├── suites.smoke             → scenario chains (replaces separate smoke config)
  └── runtime.cli              → goal, response_limit, --no-desktop, --suite

Python (dumb executors only)
  topology.py   GraphExecutor + ResponsePipeline + node handlers
  wiring.py     load_wiring(), run_suite(), optional mermaid export
  colony.py     activates slots, calls executor.run_cycle()
  slot.py       state container only (no step logic)
  tui.py        display + LLM log hook (no observe/execute branches)
  llm.py        model call
  bus.py        route records
  desktop.py    UIA observe
  actions.py    verb dispatch from wiring.verbs
```

### One graph cycle (per slot, per worker tick)

```
response_limit_gate → route_slot → observe_screen → build_request
  → llm_call → parse_pipeline → desktop_exec | feedback_append → idle
```

Edge order in JSON = priority. Example: `actions_present` routes to `desktop_exec` before `unified_acted` routes to `feedback_append`.

### Code reduction achieved

| Before | After |
|--------|-------|
| `_branch_conclusion` + `_interpret_*` in Python | `when` / `guard` steps in wiring |
| `smoke.txt` + custom parser | `suites.smoke.chain` in wiring |
| TUI observe/execute loops | `desktop_observe` + `desktop_execute` nodes |
| Slot state machine in code | `GraphExecutor` walks topology |

---

## Wiring Sections (Developer Control Surface)

| Section | You control |
|---------|-------------|
| `topology.cycle_start` | Where each LLM turn begins |
| `topology.nodes[].type` | Which Python handler runs (`gate`, `llm`, `response_pipeline`, …) |
| `topology.edges[]` | Signals between nodes (`actions_present`, `goal_complete`, `cycle_done`) |
| `request.*.user.blocks` | What enters USER context and in what order |
| `response.*.pipeline` | Parse → branch → guard → publish → emit (no Python branches) |
| `feedback.reasoning` | `append_on_events`, `entry_format`, inject into `LAST REASONING` |
| `suites.*` | Post-exit chains: run scenario → collect log → next scenario |
| `startup` | Cold-start slot + circuit |
| `runtime.cli` | How the process boots from argv |

### Plastic fan-out (design target)

Today one signal typically follows one edge. The schema supports wiring the same signal to multiple targets by duplicating edges:

```json
{"from": "parse_pipeline", "to": "desktop_exec", "on": "actions_present"},
{"from": "parse_pipeline", "to": "audit_log", "on": "actions_present"}
```

Executor enhancement for true parallel fan-out is next; edges already declare intent.

### Naming convention (in progress)

Python handlers map 1:1 to node types: `_node_desktop_observe`, `_node_response_pipeline`, `_node_bus_route`. Files match roles: `topology.py` = graph + pipeline, `wiring.py` = load + suites. **New code must be self-documenting** — if it's not a wiring node handler, it probably shouldn't exist.

---

## Running

```powershell
cd C:\Users\px-wjt\Downloads\endgame-ai

python tui.py "your goal here"
python tui.py "your goal" 1 --no-desktop    # exit after 1 LLM response
python smoke.py                              # full suite from wiring.suites.smoke
python smoke.py --id s08                     # single scenario
python wiring.py suite smoke                 # same via wiring CLI
python wiring.py mermaid                     # optional diagram → prompts/wiring.mmd
```

Manager bootstrap:

```powershell
python tui.py "Read MANAGER.md at C:\Users\px-wjt\Downloads\endgame-ai\MANAGER.md and launch the student instance with goal open notepad"
```

---

## Essential Files

| File | Role |
|------|------|
| `prompts/wiring.json` | **Single source of truth** — edit to change all behavior |
| `topology.py` | GraphExecutor + declarative ResponsePipeline |
| `wiring.py` | Load, validate, hot-reload, suite runner, mermaid export |
| `colony.py` | Slot activation + `run_cycle()` per tick |
| `slot.py` | SlotState dataclass only |
| `tui.py` | Entry point, TUI, LLM request/response logging |
| `smoke.py` | Thin wrapper → `wiring.run_suite("smoke")` |
| `llm.py` / `bus.py` / `desktop.py` / `actions.py` | Wired services |
| `prompts/unified.txt` / `prompts/manager.txt` | LLM system prompts |
| `prompts/smoke_report.txt` | Latest smoke output (full reasoning, untrimmed) |
| `AGENTS.md` / `MANAGER.md` | Operational + Manager role docs |

---

## Bootstrap Prompt (copy verbatim — any AI provider)

```
You are an AI coding agent resuming work on endgame-ai.

PARADIGM SHIFT — READ THIS FIRST
We are switching from Python-as-architecture to wiring-as-architecture.
- Machine truth: prompts/wiring.json (schema endgame-topology/v1)
- Python is WIRED, not smart: GraphExecutor walks topology.nodes/edges; ResponsePipeline runs declarative steps
- Do NOT add if/else branches for control flow — add nodes, edges, guards, or pipeline steps in wiring.json
- Python functions must be self-documenting node handlers (_node_<type>) or loaders — rename if unclear
- Filenames must match their wired role (topology.py = graph, wiring.py = config + suites)
- The developer controls: startup order, context construction, LLM pipeline, guard overrides, reasoning feedback injection, desktop execution, suite chains, shutdown — all via wiring
- Plasticity: edges can fan out (same signal → multiple targets); an action (e.g. enter) may wire to desktop_exec AND another node — declare in topology.edges
- Reasoning from MODEL REASONING goes where feedback.reasoning and pipeline emit steps say — not where Python decides

GOAL
Closed self-evolution: Manager instance observes and improves independent Student via Windows desktop only. No shared files between instances. Communication through desktop simulation.

ENVIRONMENT
- Manager repo: C:\Users\px-wjt\Downloads\endgame-ai on branch codex-unify-bus
- Student repo (separate git): C:\Users\px-wjt\Downloads\endgame-ai-student
- LM Studio: prompts/model.json
- Logs: logs/ (gitignored; read newest .txt for debugging)
- Smoke: python smoke.py — scenarios live in wiring.suites.smoke.chain (NOT smoke.txt)

IMMEDIATE ACTIONS
1. git status && git branch --show-current  → must be codex-unify-bus
2. Read: README.md, prompts/wiring.json (full), topology.py GraphExecutor
3. Confirm essential-files-only tree (no __pycache__, no logs/ in commits)
4. Baseline: python smoke.py --id s08 (one LLM response, no desktop)
5. Edit wiring.json only for behavior changes — hot-reloads on colony.step()

CURRENT RUNTIME PATH (single path, no hidden branches)
goal → bus route → GraphExecutor cycle:
  response_limit_gate → route_slot → observe_screen → build_request
  → llm_call → parse_pipeline → [desktop_exec | feedback_append] → idle

KEY WIRING SECTIONS
- topology.cycle_start + nodes/edges — executable graph
- request.unified.user.blocks — USER assembly (GOAL, SCREEN, LAST ERROR, LAST REASONING, WORKSPACE)
- response.unified.pipeline — when/guard/emit (NO branch_conclusion in Python)
- feedback.reasoning.append_on_events — when reasoning history appends
- suites.smoke — cognitive regression chain
- startup.slot — implementor, circuit unified

RULES
- No git worktrees
- No new control-flow branches in Python without a wiring.json home
- smoke_report.txt may be committed after smoke runs
- Optional: python wiring.py mermaid (documentation only, not runtime)
- Student repo sync deferred — same wiring schema, instance.role: student

NEXT WORK (priority order)
1. Fan-out executor: one signal → multiple node targets in parallel
2. Wire reasoning block routing explicitly in topology (not only feedback section)
3. Rename any remaining non-self-documenting Python symbols
4. Student repo wiring.json sync + Manager→Student end-to-end test
5. Delete unused legacy prompt files when confirmed unreferenced

Follow AGENTS.md. Continue wiring-first evolution.
```

---

*Python shrinks as wiring grows. The README bootstrap prompt above is the session handover for any provider.*