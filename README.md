# endgame-ai

endgame-ai is a local Windows desktop organism driven by a JSON signal graph.
Python owns mechanics. `prompts/wiring.json` owns behavior.

The project goal is a reliable, collaborative desktop agent that can handle
complex contingent workflows through the same interface a human uses in the
browser dashboard and an AI uses over HTTP. The immediate target is:

```text
open Chrome
start a conversation with grok.com about endgame-ai
continue from Grok's real responses for 3 turns
save a summary of the conversation in Notepad
play Shakira Waka Waka on YouTube
```

This is intentionally hard. It requires real desktop observation, browser state,
conversation memory, app switching, summary writing, and media playback without
copying stale trace literals or typing into the wrong window.

## Architecture

The runtime is a signal graph. Nodes are defined in `prompts/wiring.json`,
executed by `server.py`, and inspected or edited through `wiring-editor.html`.

Current graph shape:

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

Roles:

- `goal_inbox` normalizes the requested goal.
- `moe_route` decides local execution or colony delegation.
- `planner` creates ordered human-level subtasks.
- `scheduler` selects the current subtask.
- `bus_check` handles colony interrupts.
- `observe` captures the focused desktop window plus window awareness.
- `act` is the only circuit that sees `SCREEN`; it emits deterministic verbs.
- `verify` judges completion from action evidence and memory.
- `reflect` diagnoses failed steps.
- `self_modify` proposes conservative wiring changes.
- `bus_post` publishes final/delegation state.
- `satisfied` terminates the graph.

## ROD Contract

ROD means Reason, Observe, Decide as a runtime contract:

1. Build the node's wired input blocks from current state and wiring.
2. Call the local model once for reasoning.
3. Store reasoning under the circuit for inspection.
4. Call the model again with that reasoning and the same role contract.
5. Require one JSON object in content for the circuit.
6. Parse and validate the circuit record type.
7. Apply only generic state patches and route along wiring edges.

The model first deduces what it sees or knows from its wired inputs. It then
emits the constrained decision JSON. Reasoning is inspectable but must not leak
into circuits that should not see it.

## Invariants

- `prompts/wiring.json` is the behavior source of truth.
- Python handles mechanical truth: HTTP, graph routing, desktop focus,
  cached element maps, action execution, state files, wiring validation, and
  hot-reload.
- Python must not hardcode task strategy for Grok, Notepad, YouTube, or any
  future workflow.
- `act` is the only circuit that receives `SCREEN`.
- Focused-window `[ID]` targets are actionable only for the observation that
  produced them.
- `WINDOWS:` entries are awareness only; they are not element targets.
- Chained actions use the cached observation map shown to `act`.
- Normal verification uses action evidence and `MEMORY`, not a hidden post-act
  screen scan.
- If visible information must survive app switching, `act` stores it through
  `remember`.
- Dashboard actions and HTTP API calls must have parity.
- The HTML editor must stay schema-driven where `prompts/wiring-schema.json`
  describes the data, with generic object editors for future fields.

## Current Implementation State

Implemented:

- two-pass ROD for LLM-backed nodes
- queued `/run` and `/resume` runner
- saved resume state at the next node
- serialized observe/action calls
- deterministic action chains
- cached observation reuse across chained verbs
- focused `[ID]` targets and non-actionable `WINDOWS:` list
- Python HWND focus for targeted actions
- rejection of targeted writes to non-writable elements
- verifier preflights for focus, app launch, and browser navigation evidence
- trace examples for planner as structure only
- isolated planner/act reasoning to prevent stale JSON poisoning
- `state.memory` plus `remember`
- `/step`, `/inspect`, `/node/:type`, `/state`, `/wiring`, pause/resume, and SSE
- schema-driven `wiring-editor.html` with graph editing, state panels, wired
  inputs, reasoning, screen/window split, and hot-reload
- self-modify with current wiring summary and conservative patch examples
- observation detail controlled by `wiring.json` instead of hardcoded tiny
  previews
- hot-reloaded wiring updates action verbs and observation settings in the live
  server
- browser navigation normalization now preserves focus-before-`ctrl+l` order
- focused-window observation now falls back from shell/Desktop foreground to the
  top real application window, avoiding mixed shell/browser target maps
- browser conversation policy now permits deterministic scroll/end/wait
  recovery before returning `CANNOT`
- model output budget raised from 2048 to 8192 tokens for longer reasoning and
  structured decisions

Previously validated:

- simple desktop `open notepad` streaks completed repeatedly at about 11 cycles
- dashboard loaded and basic step/debug controls worked
- `/health` and `/smoke` passed in prior validation runs

Real compound run state on 2026-06-21:

- A real compound run exposed a generic navigation bug: inserting `ctrl+l`
  before a model-emitted browser focus selected the wrong window. The fix is now
  generic chain normalization, not Grok-specific logic.
- A resumed real run then proved the navigation fix: Chrome was focused,
  `ctrl+l` selected the address bar, `grok.com` was typed, and Grok loaded.
- The run reached `state.step == 7` and stopped at the scheduler for:
  `write summary of conversation to Notepad`.
- `state.json` is ignored by git but intentionally left local as resumable run
  data. Current resume node: `scheduler`.
- Memory contains three real Grok capture keys:
  `grok_turn_1_response`, `grok_turn_2_response`, and
  `grok_turn_3_response`.
- Completed real workflow evidence: Chrome/Grok navigation, initial Grok
  message submission, first response memory, follow-up submission, second
  response memory, third message submission, and third response memory.
- Remaining workflow work: open/focus Notepad, write a memory-derived summary,
  verify the Notepad content, then navigate/search YouTube and verify Waka Waka
  playback.
- Open reliability gap from the stopped run: `act` returned `CANNOT` when asked
  to write the summary to Notepad while Grok was still focused. Planner/act
  wiring should split this into open/focus Notepad, write summary from MEMORY,
  then continue to YouTube.

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

## Methodology

Work brick by brick:

1. Inspect the exact state or failure.
2. Decide whether the defect is behavior wiring or mechanical plumbing.
3. Prefer `prompts/wiring.json` for behavior, role contracts, guards, limits,
   and routing.
4. Use Python only for generic mechanics the model cannot reliably infer.
5. Keep runtime artifacts out of tracked files.
6. Validate with real `/step` runs when the session authorizes runtime work.
7. Move lessons from the target workflow back into task-agnostic wiring or
   generic plumbing.

Do not solve the compound target by hardcoding the target. The correct product
is a wiring-first organism that can self-debug and evolve behavior through JSON.

## Files

```text
server.py                  HTTP server, graph runner, LLM calls, node handlers
desktop.py                 Windows desktop observation/input via ctypes
actions.py                 Data-driven verb dispatcher
colony.py                  Multi-slot local runner
wiring-editor.html         Human/API step-debug workbench
prompts/wiring.json        Behavior graph, prompts, guards, limits, verbs
prompts/wiring-schema.json Schema for validation and editor generation
prompts/model.json         Local model endpoint and generation budget
README.md                  Operational handover
RESEARCH.md                Direction, risks, and proof plan
```

Ignored runtime files include `state.json`, `bus.json`,
`prompts/traces.jsonl`, `prompts/wiring.backup.json`, caches, and logs.
The allowlist `.gitignore` is intentional: source/docs/prompts are committed,
while local run state and traces remain on disk for resume/debug unless a human
explicitly cleans them.

## Immediate Validation Loop

For this target, use real step-by-step server runs, not simulated tests. If the
local `state.json` from 2026-06-21 is still present, resume from it first; it is
at the Notepad-summary stage with three Grok memory entries.

1. Start the server.
2. Use `/health` only to confirm the server is alive and not in simulation.
3. Inspect `/state`; if `_resume_node` is `scheduler` and `step` is `7`,
   continue from the saved run.
4. Inspect `state`, `screen`, `last_actions_raw`, `last_outcome`, `memory`,
   and `reasoning_chain`.
5. Drive the goal through `/step` in small chunks.
6. Patch wiring first when the model policy is wrong.
7. Patch Python only for generic contradictions such as wrong chain ordering,
   too-narrow observation, stale hot-reload, or unsafe action mechanics.
8. Restart from clean runtime artifacts only after the useful run state has
   been summarized or intentionally discarded.
9. Final proof requires visible evidence of Grok conversation memory, Notepad
   summary content, and YouTube playback.

## Handover Prompts

Use these prompts when handing the project to another AI coding provider.

### Implementation Continuation Prompt

```text
You are working in the local clone of endgame-ai. Continue implementation until
the system is a wiring-first Windows desktop organism: behavior in
prompts/wiring.json, schema-driven editing in wiring-editor.html, Python only
for generic mechanics, and no task-specific Grok/Notepad/YouTube hardcoding.

Read README.md, RESEARCH.md, server.py, actions.py, desktop.py,
prompts/wiring.json, prompts/wiring-schema.json, and wiring-editor.html before
editing. Preserve GUI/API parity for /step, /inspect, /state, /wiring, and
/node/:type. Prefer wiring changes for prompts, guards, limits, and routing.
Use Python only for mechanical contradictions.

Known focus areas:
- deepen observation without arbitrary tiny truncation
- keep live hot-reload synchronized with action and observation runtime
- ensure browser navigation focuses the browser before ctrl+l
- make planner produce contingent submit/remember/follow-up steps
- make act use remember before app switches
- make planner split summary-to-Notepad into open/focus Notepad and write
  MEMORY-derived summary
- keep self_modify conservative and wiring-aware

Current stopped state:
- all servers/tests were stopped on request
- ignored state.json resumes at scheduler, step 7
- current step is write summary of conversation to Notepad
- memory has grok_turn_1_response, grok_turn_2_response, grok_turn_3_response
- remaining proof is Notepad summary, then YouTube Waka Waka playback
```

### Real Validation Prompt

```text
Run only real step-by-step validation through the local server. Do not rely on
simulated tests for the compound proof. First inspect state.json. If it matches
the 2026-06-21 stopped state, resume it instead of starting over:

resume node: scheduler
step: 7
current step: write summary of conversation to Notepad
memory keys: grok_turn_1_response, grok_turn_2_response, grok_turn_3_response

If state.json is absent or intentionally discarded, start from clean
state.json/bus.json, confirm /health reports simulation=false, then step the
target goal in small chunks:

open Chrome; go to grok.com; ask about endgame-ai; remember Grok response 1;
send a follow-up based on memory; remember response 2; send a follow-up based
on memory; remember response 3; save a summary to Notepad; play Shakira Waka
Waka on YouTube.

After each chunk inspect state.current_step, screen, last_actions_raw,
last_outcome, memory, last_error, and reasoning_chain. If a failure is generic,
patch wiring or Python, restart the server, preserve or summarize useful
runtime state, and rerun from the smallest useful real slice.
```

### Debug Patch Prompt

```text
When a real run fails, classify the failure before editing:

1. Behavior prompt/guard/limit/routing problem: patch prompts/wiring.json.
2. Schema/editor parity problem: patch wiring-schema.json and
   wiring-editor.html.
3. Generic runtime contradiction: patch server.py, actions.py, or desktop.py.
4. Task-specific workaround: reject it and find the reusable rule.

Every patch must preserve the invariant that Python is mechanics and wiring is
behavior. The final answer must report real step evidence, remaining risk, and
whether helper processes were stopped and runtime artifacts cleaned.
```
