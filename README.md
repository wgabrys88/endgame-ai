# endgame-ai

endgame-ai is a local Windows desktop organism driven by a signal graph.

The repository is intentionally small. Python owns mechanics: HTTP transport,
state files, graph routing, desktop observation, deterministic input, and wiring
validation. Behavior belongs in `prompts/wiring.json`: topology, role prompts,
guards, limits, prompt inputs, and self-modification policy.

The current work is about making that organism reliable enough for complex,
contingent desktop workflows, with a shared step/debug surface that a human can
operate in the browser and an AI can operate through the same HTTP API.

## Current State

The previous session made the core loop materially more truthful and more
repeatable.

Implemented and proven:

- ROD is implemented as a two-pass LLM contract for every LLM-backed circuit.
- `/run` and `/resume` enqueue work on one background runner instead of
  creating overlapping graph loops.
- Saved resume state points to the next node rather than the node that already
  ran.
- Desktop observation and desktop action calls are serialized.
- `act` can emit short deterministic chains such as `win+r`, write app name,
  and `enter`.
- Chained verbs reuse the observation map that produced the `SCREEN` shown to
  `act`; they do not rescan before every verb.
- A configured settle delay between chained verbs replaces the accidental delay
  that repeated hover scans previously provided.
- Focused-window actionable elements receive `[ID]` targets.
- Observations include a non-actionable `WINDOWS:` list of visible top-level
  window titles.
- Targeted click/write/scroll actions mechanically focus the cached element's
  HWND in Python.
- A targeted write fails if its `[ID]` is not in the cached map.
- Verifier preflights cover deterministic truths such as successful focus
  evidence and Run-dialog app-launch chains.
- `act` no longer receives verifier/reflector reasoning that can poison its
  schema.
- `planner` no longer receives broad downstream reasoning that can cause it to
  copy verdict JSON into future plans.
- Planner receives traces as structural examples, not as literal tasks to copy.
- `self_modify` receives a compact current-wiring summary and conservative
  patch examples.
- Colony support has been validated with a two-slot delegation proof.
- A basic dashboard and `/step` endpoint exist for manual stepping.

Previous-session evidence:

- Syntax and wiring JSON parsed cleanly.
- `/smoke` passed 6/6.
- Direct observation confirmed `WINDOWS:` is present while `[ID]` scope remains
  focused-window-only.
- Ten consecutive real desktop `open notepad` goals completed at roughly 11
  graph cycles each under a 15-cycle cap.

Implementation additions in this session, pending runtime validation:

- `/step` now returns the executed node, signals, target edges, state patch,
  full state, next node, and before/after debug context.
- `/inspect` exposes the current node's wired prompt inputs without executing a
  graph node.
- `POST /state` can save an API-provided state object for GUI/API parity.
- `POST /pause` lets autonomous runs stop between nodes and persist a resume
  point.
- `/node/:type` returns the same patch-plus-full-state shape used by the
  dashboard.
- The dashboard was rebuilt as a schema-driven wiring workbench with node drag,
  edge creation/reconnection, generic object editors, state panels, wired input
  panels, reasoning panels, and debounced hot-reload through `POST /wiring`.
- `state.memory` and the `remember` verb were added so `act` can store compact
  response facts or summaries before switching apps or navigating away.
- Wiring prompts now describe a precise, conservative, safety-first desktop
  organism that handles contingent browser work through observe, remember,
  continue, summarize, and write steps.

## ROD Contract

ROD means Reason, Observe, Decide in the actual runtime, not only in prompts.
Each LLM node follows this contract:

1. Build the node's wired input blocks from current state and wiring.
2. Call the model once for reasoning content.
3. Store the reasoning content under the circuit/node for inspection.
4. Call the model a second time with that reasoning content and the same role
   contract.
5. Require the second call to emit exactly one JSON object for that circuit.
6. Parse and validate the object in Python.
7. Apply only generic state patches and route along wiring edges.

The model should first deduce what it sees or knows from its wired inputs, then
produce the circuit's structured output. Non-`act` circuits do not see the
desktop unless the wiring explicitly gives them a desktop-derived block.

## ROD Invariants

These invariants are part of the runtime contract:

- `prompts/wiring.json` is the behavior source of truth.
- Python may enforce mechanical facts, but it must not invent task strategy.
- Only focused-window actionable elements get `[ID]` targets.
- `WINDOWS:` entries are context, not targets.
- `act` is the only circuit that receives `SCREEN`.
- Planner never receives raw desktop UI labels, `[ID]` targets, or `SCREEN`.
- `act` should not receive verifier or reflector reasoning.
- Action execution uses the cached observation map that produced the screen
  shown to `act`.
- Normal verification relies on action evidence and structured state, not an
  automatic post-action hover scan.
- A successful mechanical focus/open action can be confirmed by Python before
  model verification.
- `MEMORY` is explicit task state; the model chooses when to store it through
  the `remember` action, and later circuits consume it only through wired input
  blocks.
- Self-modification validates a complete wiring document before hot-reload.
- The same step/debug operations must be available through GUI controls and
  HTTP calls.

## Current Graph

The working loop is a signal graph:

```text
goal_inbox -> moe_route -> planner -> scheduler -> bus_check -> observe -> act -> verify
                 |                         |                                  |
                 | delegated               | plan_complete                    | step_denied
                 v                         v                                  v
              bus_post -> satisfied     bus_post -> satisfied              reflect
                                                                            | | |
                                                                            | | +-> self_modify
                                                                            | +---> planner
                                                                            +----> scheduler
```

The graph is not a chatbot wrapper. Each node has one constrained job:

- `goal_inbox` normalizes a user goal.
- `moe_route` decides whether local execution or delegation is appropriate.
- `planner` creates task-agnostic, current-goal-preserving steps.
- `scheduler` selects the next step.
- `bus_check` checks shared colony messages.
- `observe` captures a bounded desktop view.
- `act` maps the current step plus `SCREEN` to deterministic verbs.
- `verify` judges whether the current step is complete.
- `reflect` diagnoses failure and selects a recovery path.
- `self_modify` proposes conservative wiring changes.
- `bus_post` publishes delegation or completion messages.
- `satisfied` ends the graph.

## Methodology

The operating method is brick by brick:

1. Read the current wiring and plumbing before changing behavior.
2. Prefer `prompts/wiring.json` for behavior, role, guard, and routing changes.
3. Use Python only for plumbing contradictions, missing generic endpoints, or
   deterministic mechanics.
4. Keep runtime artifacts out of the repository.
5. Edit only tracked source, documentation, and prompt files.
6. After edit blocks, run only lightweight static checks when runtime validation
   is out of scope: JSON parsing, schema parsing, Python AST parsing, and
   `git diff --check`.
7. Leave real server runs, `/smoke`, colony runs, and desktop goals for
   validation sessions.

The engineering rule is simple: the model handles semantic choice; Python
handles mechanical truth.

## Immediate Target

The next target proof is the compound desktop workflow:

```text
open Chrome
start a conversation with grok.com about endgame-ai
keep the conversation based on Grok's real responses for 3 turns
save a summary of the conversation in Notepad
play Shakira Waka Waka on YouTube
```

This is intentionally contingent. The organism must read what actually happens
on the desktop, preserve useful state across turns, avoid stale trace literals,
write the summary into the correct focused application, and continue into a
separate browser media task.

This workflow should be developed through the same collaborative step/debug
surface used by humans and API clients.

## Step/Debug Workbench Target

The dashboard is now implemented as the operational workbench source. It is
schema-driven from `prompts/wiring-schema.json` where schema detail exists, and
falls back to generic JSON/object editors for unknown future fields. Runtime
validation is still pending by design for this implementation-only session.

Required properties:

- Load and render the live `prompts/wiring.json` graph.
- Represent nodes as editable boxes and edges as editable connections.
- Support adding, removing, editing, and reconnecting nodes and edges.
- Hot-reload valid wiring through `POST /wiring`.
- Show current node, next node, state patch, signals, and full state after
  every step.
- Show wired inputs such as `SCREEN`, `HISTORY`, `COMPLETED_STEPS`,
  `CURRENT_WIRING`, action evidence, and reasoning content.
- Separate focused `[ID]` targets from the non-target `WINDOWS:` list.
- Support pause, resume, inspect, and one-step execution.
- Provide parity between GUI controls and HTTP calls.
- Avoid hardcoded future wiring fields where the schema can drive editors.

The long-term plan is a fully operational schema-driven interactive
step/debug workbench where a human and an AI can collaborate on the same graph
state without hidden side channels.

## HTTP Surface

Current and target-compatible endpoints:

```text
GET  /                         Dashboard
GET  /health                   Node registry, slot, run status, capabilities
GET  /smoke                    Six-point self-test
GET  /state                    Last persisted state
GET  /bus                      Shared bus contents
GET  /wiring                   Current wiring
GET  /wiring-schema            Wiring schema for dashboard/editor
GET  /events                   SSE stream

POST /run        {"goal": "..."}           Queue autonomous run
POST /resume                              Queue saved-state resume
POST /pause                               Request pause between run nodes
POST /step       {"goal","state","node"}    Execute one graph transition with debug context
POST /inspect    {"goal","state","node"}    Inspect wired inputs without executing
POST /state      {"state": {...}}           Save API-provided state
POST /node/:type {"state": {...}}          Call one node type and return patch/full state
POST /wiring     {full wiring.json}        Validate and hot-reload wiring
POST /interrupt  {"goal": "..."}           Post slot interrupt
POST /push       {"type":"..","text":".."} Dashboard event push
POST /bus/post   {message}                 Append bus message
```

The important parity rule: anything the dashboard can do should be expressible
as one of these HTTP operations, and anything an API client can do should be
visible in the dashboard.

## Files

Tracked essentials:

```text
server.py                  HTTP server, graph runner, LLM calls, node handlers
desktop.py                 Windows desktop observation and input via stdlib ctypes
actions.py                 Verb dispatcher and simulation stub
colony.py                  Multi-slot local rod launcher
wiring-editor.html         Human/debug UI for run, step, state, topology
prompts/wiring.json        Brain: topology, prompts, guards, limits, verbs
prompts/model.json         Local model endpoint configuration
prompts/wiring-schema.json Wiring schema for validation and future UI generation
README.md                  Operational handover
RESEARCH.md                Product/research direction and next proof
.gitignore                 Allowlist: only essentials are commit candidates
.gitattributes             Line-ending normalization
LICENSE
```

Ignored runtime artifacts include `bus.json`, `state.json`,
`prompts/traces.jsonl`, `prompts/wiring.backup.json`, caches, logs, and other
generated files.

## Reliability Notes

The prior reliability gains came from reducing contradiction:

- Focus is mechanical when acting on a visible `[ID]`.
- Planner should not invent focus-preparation subtasks for normal targeted
  click/write work.
- `WINDOWS:` helps identify existing windows without expanding target scope.
- Short deterministic chains are safer than many single-step scan/action loops
  when the UI transition is known.
- Verifier preflights should cover facts Python already knows.
- Traces are useful as structural patterns only.
- Self-modification should patch conservative prompt or wiring defects rather
  than make broad topology changes during a live failure.

These rules matter more for browser workflows than simple app-launch goals,
because stale state and copied literals are more damaging when each turn depends
on a real response.

## Appendix: Meta-Format Handover

```yaml
handover:
  project: endgame-ai
  repository: https://github.com/wgabrys88/endgame-ai
  local_workspace: C:\Users\px-wjt\Downloads\endgame-ai
  date: 2026-06-21
  mission:
    Implement the wiring-first organism so it can handle complex contingent
    Windows desktop workflows through a collaborative human/API step debugger.
  previous_session_state:
    proven:
      - two-pass ROD calls are implemented for LLM nodes
      - autonomous runs use a queued background runner
      - resume continues at the next node
      - observe/action calls are serialized
      - act supports deterministic short chains
      - chained actions use cached observation targets
      - observations include focused [ID] targets plus a WINDOWS list
      - verifier has deterministic preflights for focus and app launch evidence
      - planner and act are isolated from stale downstream reasoning
      - traces are structural examples for planner
      - self_modify sees a compact wiring summary
      - two-slot colony delegation was validated
      - open-notepad completed 10 consecutive times at about 11 cycles
    implemented_this_session_static_only:
      - /step returns transition/debug context for GUI and API users
      - /inspect, POST /state, and POST /pause were added
      - /node/:type now returns state_patch plus full state
      - dashboard is schema-driven with editable nodes, edges, generic fields,
        wired input inspection, reasoning inspection, and hot-reload saves
      - edge creation/reconnection and node dragging are implemented in SVG
      - state.memory plus remember verb support contingent response carryover
      - prompts were refined for browser conversation, summary, Notepad, and
        YouTube-style compound workflows without hardcoding the task
    not_yet_proven:
      - Grok three-turn contingent browser dialogue
      - Notepad summary save after browser work
      - YouTube Waka Waka playback after the summary
      - runtime behavior of the new dashboard and memory support
  immediate_target:
    Validate the schema-driven wiring/step workbench and memory-aware prompts
    against the compound Chrome/Grok/Notepad/YouTube workflow.
  methodology:
    - edit tracked files only
    - rewrite behavior in prompts/wiring.json whenever possible
    - change Python only for generic plumbing or mechanical contradictions
    - do not create runtime artifacts
    - do not run servers, /smoke, colony tests, desktop streaks, or goals in
      implementation-only sessions
    - after edit blocks, run static checks only
  next_ai_session_start:
    - read README.md and RESEARCH.md
    - inspect git diff and tracked status
    - if in validation mode, start the server and use GUI/API /step side by side
    - step through Chrome open, Grok conversation, Notepad summary, and YouTube
    - move task-specific lessons back into wiring prompts or generic plumbing
```
