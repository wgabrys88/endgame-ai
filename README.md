# endgame-ai

endgame-ai is a local Windows desktop organism whose behavior lives in a JSON
signal graph and whose mechanics live in Python.

The project is not a prompt demo. It is a wiring-first agent runtime that can
look at the real desktop, choose a bounded action, verify from evidence, reflect
when a step fails, and conservatively change its own wiring when the failure is
generic. The same runtime must be usable by a human in the workbench and by an
AI over HTTP.

## Vision

The long-term target is a desktop agent that can complete complex contingent
workflows through the same applications a human uses, without task-specific
Python code and without stale trace replay.

The current north-star workflow is:

```text
open Chrome
start a conversation with grok.com about endgame-ai
continue from Grok's real responses for 3 turns
save a summary of the conversation in Notepad
play Shakira Waka Waka on YouTube
```

That target is intentionally hard. It requires real desktop observation,
conversation memory, browser state, app switching, summary writing, media
selection, and playback verification. The product direction is not to hardcode
Grok, Notepad, YouTube, or a particular page layout. The product direction is
to improve observation, wiring, reasoning contracts, and verification until the
system can handle this class of workflow generically.

## Architecture

Runtime behavior is a directed signal graph in `prompts/wiring.json`.
`server.py` executes the graph. `desktop.py` observes and manipulates Windows.
`actions.py` dispatches data-driven action verbs. `wiring-editor.html` is the
human workbench and schema-driven wiring editor.

Current graph:

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

Node roles:

- `goal_inbox` normalizes a requested goal into state.
- `moe_route` decides local execution or colony delegation.
- `planner` turns the goal, history, and memory into human-level subtasks.
- `scheduler` selects the current subtask.
- `bus_check` handles colony interrupts.
- `observe` captures the real desktop and builds the `SCREEN` block.
- `act` is the only circuit that sees `SCREEN`; it emits deterministic verbs.
- `verify` judges step completion from action evidence and memory.
- `reflect` diagnoses failed steps without seeing `SCREEN`.
- `self_modify` proposes conservative wiring changes.
- `bus_post` publishes terminal or delegation telemetry.
- `satisfied` terminates the graph.

## ROD Contract

ROD means Reason, Observe, Decide. Each LLM-backed circuit follows the same
shape:

1. Build the node's wired input blocks from current state and wiring.
2. Call the local model once for reasoning.
3. Store reasoning under that circuit for inspection.
4. Call the model again with the same role contract and the reasoning context.
5. Require one JSON object in content.
6. Parse and validate the circuit's record type.
7. Apply only generic state patches and route along wiring edges.

Reasoning is inspectable, but circuit boundaries matter. Planner never sees
screen elements. Verify and reflect never see screen elements. Act is the only
circuit that receives desktop observation.

## Core Invariants

- `prompts/wiring.json` is the behavior source of truth.
- Python owns mechanics: HTTP, graph routing, desktop focus, cached element
  maps, action execution, state files, validation, and hot reload.
- Python must not hardcode task strategy for Grok, Notepad, YouTube, or any
  future workflow.
- `act` is the only circuit that receives `SCREEN`.
- Focused-window `[ID]` targets are actionable only for the observation that
  produced them.
- `WINDOWS:` entries are awareness only; they are not element targets.
- `DESKTOP_TREE:` is read-only context.
- `aid=` and `class=` are stable UIA identity hints, not action targets.
- `screen_meta` must report tree and probe coverage truthfully.
- Chained actions use the cached observation map shown to `act`.
- Normal verification uses action evidence and `MEMORY`, not hidden post-act
  screen scans.
- If visible information must survive app switching, `act` stores it with
  `remember`.
- Dashboard actions and HTTP API calls must have parity.
- The workbench must remain schema-driven where `prompts/wiring-schema.json`
  describes the data, with generic editors for future fields.

## Observation Model

Observation is the next center of gravity for the project. A weak or partial
`SCREEN` block causes the model to make plausible but wrong inferences.

The observer now produces:

- ACTION SCOPE: actionable focused-window and top-overlay `[ID]` targets.
- OVERLAYS: z-ordered window overlays that may obstruct the focused app.
- DESKTOP_TREE: a bounded full-desktop UIA hierarchy for read-only context.
- WINDOWS: z-ordered visible top-level windows for awareness.
- PROBE telemetry: primary, overlay, full-screen hover, dense, and scroll
  enrichment stats.
- TREE coverage: focused capture, overlay capture, truncation, scope counts,
  captured owner HWNDs, and missing overlay HWNDs.

The full-screen hover pass intentionally moves the mouse across the screen at
the configured point spacing, collects UIA elements under those hover points,
deduplicates them against focused/overlay probes, and restores the cursor.
This is generic mechanical observation. It is controlled by `observe` keys in
`prompts/wiring.json` and validated by `server.py` plus
`prompts/wiring-schema.json`.

Current rich observation defaults are intentionally large because the local LM
Studio context budget can accept more screen evidence:

```text
probe_step_px=40
hover_scan_enabled=true
hover_scan_step_px=40
desktop_tree_max_depth=8
desktop_tree_max_nodes=900
desktop_tree_child_limit=180
read_text_max=16000
node_value_max_chars=12000
render_value_max_chars=4000
tree_value_max_chars=4000
render_tree_value_max_chars=800
```

If observation becomes too slow, reduce the wiring values rather than removing
the generic capability.

## Workbench

`wiring-editor.html` is the operator surface. It must make the wiring graph and
runtime state understandable without requiring raw JSON reading.

The workbench currently includes:

- a topology-aware SVG signal graph
- auto layout from `topology.cycle_start`
- draggable nodes with persisted local positions
- pan, wheel zoom, fit, and explicit zoom controls
- styled forward, back, loop, success, and failure edges
- edge creation and reconnection through ports/handles
- schema-driven inspectors for nodes, edges, and top-level wiring sections
- hot-reload through `POST /wiring`
- `Step`, `Continue`, `Pause`, `Observe`, `Load State`, and `Save State`
- state, plan, history, wired inputs, reasoning, raw JSON, schema, and log tabs
- Action Scope IDs, Desktop Tree, and Telemetry observation panels

The graph is an editor and a debugger. It should keep improving toward a view
where the operator can see which node ran, why a transition was selected, where
failure loops occur, and which JSON fields control each behavior.

## HTTP Surface

```text
GET  /                         Workbench
GET  /health                   Runtime status and capabilities
GET  /state                    Last persisted state
GET  /bus                      Colony bus
GET  /wiring                   Live wiring
GET  /wiring-schema            Editor schema
GET  /events                   SSE events

POST /run        {"goal": "..."}             Queue autonomous run
POST /resume                                Resume saved state
POST /pause                                 Pause between nodes
POST /step       {"goal","state","node"}      Execute one node transition
POST /inspect    {"goal","state","node"}      Inspect wired inputs
POST /state      {"state": {...}}             Save state
POST /node/:type {"state": {...}}             Execute one node handler
POST /wiring     {full wiring.json}          Validate and hot-reload wiring
POST /interrupt  {"goal": "..."}             Bus interrupt
POST /push       {"type":"...","text":"..."} Dashboard event push
POST /bus/post   {message}                   Append bus message
```

Parity rule: anything the GUI can do must be possible through HTTP, and HTTP
state changes must be visible in the GUI.

## Current Implementation State

Implemented:

- two-pass ROD for LLM-backed nodes
- queued `/run` and `/resume` runner
- saved resume state at the next node
- serialized observe/action calls
- deterministic action chains
- cached observation reuse across chained verbs
- focused `[ID]` targets plus non-actionable window/tree awareness
- Python HWND focus for targeted actions
- rejection of targeted writes to non-writable elements
- verifier preflights for focus, app launch, browser navigation, summary
  writing, and media playback false positives
- isolated planner/act reasoning to reduce stale JSON poisoning
- `state.memory` plus `remember`
- `/step`, `/inspect`, `/node/:type`, `/state`, `/wiring`, pause/resume, and SSE
- schema-driven workbench with graph editing, hot reload, state panels, wired
  inputs, reasoning, observation panels, and telemetry
- self-modify with current wiring summary and conservative patch examples
- observation settings controlled by `wiring.json`
- validated `set_observe` and `/wiring` observe updates
- UIA `automation_id` and `class_name` identity hints
- z-ordered desktop tree and rectangle-based window ownership fallback
- full-screen mouse-hover observation enrichment
- richer token-oriented observation and debug limits

Known compound-run evidence from prior real runs:

- Chrome/Grok navigation succeeded.
- A Grok initial message was submitted.
- Three Grok response memory keys existed in the real run:
  `grok_turn_1_response`, `grok_turn_2_response`, and
  `grok_turn_3_response`.
- A memory-derived summary write action into Notepad succeeded.
- YouTube search/navigation for `Shakira Waka Waka` succeeded.
- Playback was not proven; verifier correctly refused precursor evidence.

Do not treat that as final completion. The remaining proof is to expose and
click a matching playable media result, verify playback, and optionally refocus
Notepad to visually audit the summary.

## Latest Validation Evidence

Validated on 2026-06-22 from the current worktree:

- `python -m compileall -q .` passed.
- `python -m pyright` passed with 0 errors, 0 warnings, 0 informations.
- `git diff --check` passed, with only Git CRLF normalization warnings.
- Workbench inline JavaScript parsed successfully with bundled Node.
- Fresh server started on `http://127.0.0.1:9078`.
- `GET /health` returned `ok=true`, `desktop_exec=true`, and
  `wiring_hot_reload=true`.
- `GET /wiring` showed `hover_scan_enabled=true`,
  `hover_scan_step_px=40`, `desktop_tree_max_nodes=900`, and
  `debug_value_max_chars=12000`.
- `POST /node/observe` returned `screen_ready`, focused
  `YouTube - Google Chrome`, 65 action-scope elements, 28,594 screen
  characters, `hover_scan_used=true`, 1,296 hover points, 51 hover-added
  nodes, 374 desktop tree nodes, `treeTruncated=false`,
  `focusedCaptured=true`, and `overlayCaptured=true`.
- `POST /step` on the `observe` node returned `screen_ready`, routed next to
  `act`, produced 70 action-scope elements, 33,283 screen characters,
  `hover_scan_used=true`, 1,296 hover points, 60 hover-added nodes, 374 tree
  nodes, and `transitionTerminal=false`.
- Raw `POST /wiring` hot reload accepted the updated `wiring.json`.
- Browser verification of the workbench showed 12 graph nodes, 21 graph edges,
  7 back edges, 1 loop edge, 9 failure-styled edges, working zoom/fit/auto
  layout controls, no desktop or mobile horizontal overflow, and no browser
  console errors.
- The synthetic `/step` validation state was cleared afterward; `GET /state`
  should return `{}` unless a later run writes new state.

## Methodology

Work brick by brick:

1. Inspect the exact state or failure.
2. Decide whether the defect is behavior wiring or mechanical plumbing.
3. Prefer `prompts/wiring.json` for prompts, guards, limits, roles, routing,
   and behavior contracts.
4. Use Python only for generic mechanics the model cannot reliably infer.
5. Keep runtime artifacts out of tracked files.
6. Validate with real `/step` runs when runtime work is authorized.
7. Move lessons from target workflows back into task-agnostic wiring or
   generic plumbing.

Failure classification:

- Behavior prompt, guard, limit, or routing problem: patch `prompts/wiring.json`.
- Schema/editor parity problem: patch `prompts/wiring-schema.json` and
  `wiring-editor.html`.
- Generic runtime contradiction: patch `server.py`, `actions.py`, or
  `desktop.py`.
- Task-specific workaround: reject it and find the reusable rule.

## Files

```text
server.py                  HTTP server, graph runner, LLM calls, node handlers
desktop.py                 Windows desktop observation and input via ctypes/UIA
actions.py                 Data-driven verb dispatcher
colony.py                  Multi-slot local runner
wiring-editor.html         Human/API step-debug workbench
prompts/wiring.json        Behavior graph, prompts, guards, limits, verbs
prompts/wiring-schema.json Schema for validation and editor generation
prompts/model.json         Local LM Studio endpoint and generation budget
README.md                  Operational handover and project vision
RESEARCH.md                Direction, risks, and proof plan
```

Ignored runtime files include `state.json`, `bus.json`, `state.*.json`,
`prompts/traces.jsonl`, `prompts/wiring.backup.json`, local transcripts,
caches, and logs. The allowlist `.gitignore` is intentional: source, docs, and
prompts are committed; local run state and traces remain on disk for
resume/debug unless a human explicitly cleans them.

## Real Validation Loop

Use real step-by-step server runs for compound proof. Do not rely on simulated
tests for the final target.

Recommended loop:

1. Start the server bound to localhost unless there is a specific reason to
   expose it.
2. Confirm `GET /health`.
3. Inspect `GET /state`.
4. Inspect `state.current_step`, `screen`, `screen_meta`, `last_actions_raw`,
   `last_outcome`, `memory`, `last_error`, and `reasoning_chain`.
5. Use `POST /node/observe` when the question is observation quality.
6. Use `POST /step` for one graph transition at a time.
7. If a step fails, classify the failure before editing.
8. Patch wiring first when the behavior contract is wrong.
9. Patch Python only when observation or action mechanics contradict the real
   UI.
10. Preserve useful runtime state before resetting or repairing it.

Final proof for the north-star workflow requires:

- visible evidence or memory evidence for three real Grok responses
- Notepad summary content written from memory
- YouTube playback evidence, not only search or navigation evidence

## Handover Prompts

Use these prompts when handing the project to another AI coding provider.

### Implementation Continuation Prompt

```text
You are working in the local clone of endgame-ai. Continue implementation until
the system is a wiring-first Windows desktop organism: behavior in
prompts/wiring.json, schema-driven editing in wiring-editor.html, Python only
for generic mechanics, and no task-specific Grok/Notepad/YouTube hardcoding.

Read README.md, RESEARCH.md, server.py, actions.py, desktop.py,
prompts/wiring.json, prompts/wiring-schema.json, prompts/model.json, and
wiring-editor.html before editing. Preserve GUI/API parity for /step, /inspect,
/state, /wiring, and /node/:type. Prefer wiring changes for prompts, guards,
limits, roles, and routing. Use Python only for mechanical contradictions.

Known focus areas:
- keep observation as the center of gravity: rich UIA tree, full-screen hover
  probing, spatial/order cues, overlay separation, and scrollability
- ensure ACTION SCOPE IDs remain the only actionable element targets
- keep DESKTOP_TREE read-only and useful for cognition
- make the workbench graph show real signal flow, feedback, and failure loops
- keep live hot reload synchronized with action and observation runtime
- make planner produce contingent submit/remember/follow-up steps
- make act use remember before app switches
- keep self_modify conservative and wiring-aware
- avoid narrow prompt rules for one page/site until the generic observation
  problem is understood

Before claiming completion, prove it with current files, static checks, live
/health, live /wiring validation, live /node/observe telemetry, and real /step
evidence.
```

### Real Step Validation Prompt

```text
Run only real step-by-step validation through the local server after runtime is
explicitly authorized. Do not rely on simulated tests for the compound proof.

First inspect /health and /state. If state.json exists, preserve or summarize
useful evidence before repairing it. If the current goal is the north-star
workflow, expected prior evidence may include memory keys:
grok_turn_1_response, grok_turn_2_response, grok_turn_3_response.

Before stepping act-heavy work, inspect observation quality:
- compare the visible browser/app page to SCREEN
- confirm PROBE telemetry includes the full-screen hover pass
- confirm DESKTOP_TREE coverage and truncation are truthful
- confirm playable or writable controls appear in ACTION SCOPE before targeting
  them

Use POST /step in small chunks. After each transition inspect:
state.current_step, screen, screen_meta, last_actions_raw, last_outcome,
memory, last_error, and reasoning_chain.

If a failure is generic, patch wiring or Python, restart/hot-reload as needed,
preserve useful runtime state, and rerun from the smallest useful slice.
```

### Observation Debug Prompt

```text
Diagnose observation before prompt-tuning. The model can only reason over the
SCREEN text it receives.

For any failed page/app interaction:
1. Observe the real screen through /node/observe.
2. Inspect ACTION SCOPE, DESKTOP_TREE, WINDOWS, and screen_meta.probe.
3. Check whether full-screen hover_scan_used is true and whether hover_added
   exposed additional controls.
4. Check whether the tree is truncated before the relevant content.
5. Check whether overlays or browser chrome are being confused with page
   content.
6. Patch observe limits or desktop.py mechanics only if the representation is
   missing generic truth.
7. Patch prompts/wiring.json only if the representation is truthful but the
   role contract makes the circuit reason incorrectly.
```

### Workbench UI Prompt

```text
Improve wiring-editor.html as an operator/debugger surface, not as a marketing
page. The graph should communicate topology, current node, edge signals,
feedback loops, failed paths, and editable JSON fields. Keep the editor
schema-driven, preserve /wiring hot reload, keep HTTP/API parity, and verify in
the browser at desktop and mobile sizes.

Avoid hiding raw JSON; make it one tab among better structured views. Any graph
positioning should be interactive, persistent locally, and recoverable with an
auto-layout button.
```

### Completion Audit Prompt

```text
Before marking the goal complete, derive every concrete requirement from the
current user objective and verify each against current evidence:
- README fully rewritten with vision and handover prompts
- /step API authorized and used for behavior evidence when safe
- observation scan includes full-screen mouse-hover enrichment
- richer observation/token limits are wired, validated, and hot-reloadable
- workbench graph represents nodes and connections usefully and interactively
- static checks pass
- live /health, /wiring, /node/observe, and relevant /step calls prove runtime
  behavior

If any item has weak or missing evidence, keep working.
```
