# endgame-ai

Local Windows desktop organism controlled by a signal graph.

This repository is intentionally small. Python is the transport layer: it reads
`prompts/wiring.json`, exposes HTTP endpoints, observes the desktop, executes
verbs, and routes graph signals. Behavior belongs in wiring: topology, prompts,
guards, limits, and role boundaries.

## Current Reality

ROD now means Reason-Observe-Decide in the literal runtime:

1. Each LLM node gets its system prompt and wired input blocks.
2. The first call produces reasoning content: what the circuit sees or knows.
3. The second call receives that reasoning and must emit one structured JSON
   object for the circuit role.
4. Python parses the JSON, stores reasoning by circuit, applies patches, and
   follows wiring edges.

The system is not a generic chatbot wrapper. It is a desktop control loop:

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

## What Changed In This Session

Reliability work:

- `/run` and `/resume` now enqueue work on one background runner instead of
  starting overlapping graph loops.
- Resume state now points at the next node, not the node that already ran.
- Desktop observe/action calls are serialized with a lock.
- Act can execute short deterministic chains such as `win+r`, `write app`,
  `enter`.
- Chained verbs now have a small configured settle delay so removing repeated
  scans does not race dialogs such as Run.
- Verify has deterministic preflight confirms for:
  - successful focus evidence when a window must be open/focused
  - the Run-dialog launch chain for app-opening goals
- Act no longer receives verifier/reflector reasoning, which was poisoning its
  schema.
- Planner no longer receives the broad reasoning chain, which was causing
  replan attempts to copy verdict/diagnosis JSON.
- Trace examples are labeled structural only, so old literal goal text is not
  supposed to leak into new plans.

Observation work:

- Focused-window elements still get the only `[ID]` targets.
- The last observation now owns the element map used by action execution. Act
  no longer triggers a fresh hover scan before every verb in a chain.
- Post-action screen refresh is now opt-in; normal refresh happens at the next
  observe node because verify/reflect do not consume `SCREEN`.
- Observation now also includes a `WINDOWS:` section with top-level visible
  window titles. Those titles are not element IDs; they exist only for
  focus/window-title reasoning.
- Extra hover/scroll enrichment starts at fewer elements, reducing repeated
  sweep work on sparse windows.
- Targeted click/write/scroll actions mechanically focus the element's HWND in
  Python. A targeted write fails if the element is not in the cached map instead
  of typing into whatever field is currently focused.

Prompt work:

- The shared base prompt begins by forcing every circuit to first deduce what
  it sees or knows from its wired inputs.
- Non-act circuits are told explicitly that they do not see the desktop.
- Planner is told not to add focus preparation steps for normal click/write
  work because Python focuses the target window.
- Act is told to use focus only as a single switch/confirmation step, never as
  preparation for acting on a visible `[ID]`.
- Self-modify receives a compact current-wiring summary and conservative patch
  examples.

Validated evidence:

- Syntax and wiring JSON parse cleanly.
- `/smoke` passes 6/6.
- Two-slot colony delegation was validated: a non-exec slot delegated a browser
  goal to the exec slot through the shared bus.
- Real desktop streak: 10 consecutive `open notepad` goals completed, each at
  11 graph cycles with a 15-cycle cap.
- Direct observation confirmed `WINDOWS:` is present while `[ID]` scope remains
  focused-window-only.

## What Is Still Not Done

The next target is not merely opening Notepad. The requested next proof is a
compound desktop workflow:

```text
open chrome, start conversation with grok.com AI about endgame-ai,
keep the conversation based on what Grok responds for 3 turns,
save the summary of the conversation in Notepad,
then run Shakira Waka Waka on YouTube
```

That workflow must be developed through the same HTTP/dashboard step surface a
human can use. The dashboard must be good enough for a human to see and debug
exactly what the AI sees through API calls.

## Methodology

Work brick by brick:

1. Read the current wiring and code before changing behavior.
2. Prefer `prompts/wiring.json` for behavior changes.
3. Make Python fixes only when the plumbing contradicts wiring's intent.
4. Validate with `/smoke`, direct node calls, and real desktop goals.
5. Clean runtime artifacts before committing.
6. Commit only tracked essential files.

The design rule remains: Python should not decide task strategy. Python may
enforce deterministic safety and mechanical truth, such as "a successful focus
means a matching window exists" or "a failed verb cannot verify a step."

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
RESEARCH.md                Product/research direction and next plan
.gitignore                 Allowlist: only essentials are commit candidates
.gitattributes             Line-ending normalization
LICENSE
```

Ignored runtime artifacts include `bus.json`, `state.json`,
`prompts/traces.jsonl`, `prompts/wiring.backup.json`, caches, logs, and other
generated files.

## HTTP Surface

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
POST /step       {"goal","state","node"}    Execute one graph transition
POST /node/:type {"state": {...}}          Call one node type
POST /wiring     {full wiring.json}        Validate and hot-reload wiring
POST /interrupt  {"goal": "..."}           Post slot interrupt
POST /push       {"type":"..","text":".."} Dashboard event push
POST /bus/post   {message}                 Append bus message
```

The dashboard now uses `/step` for graph stepping, the same endpoint an AI can
call directly. `/node/:type` remains available for low-level node probes.

## Invariants

1. Only focused-window actionable elements get `[ID]` targets.
2. `WINDOWS:` titles are not element IDs.
3. Act is the only circuit that receives `SCREEN`.
4. Planner never receives `SCREEN`, UIA labels, or `[ID]`.
5. Act should not receive verifier/reflector reasoning.
6. Action execution uses the cached observation map that produced the screen
   shown to act; it should not rescan for every verb in a deterministic chain.
7. Python may enforce deterministic mechanical truths but must not invent task
   strategy.
8. Port is `9077 + slot` when slot offset is enabled.
9. Self-modify validates wiring before hot-reload.
10. Behavior changes should be possible through `wiring.json` whenever the
   Python handler already exists.

## Is The Vision Closer?

Yes. Before this session the loop was proven but brittle: app launch could take
27 cycles, focus subtasks confused the model, colony delegation had not been
proved live, and ROD was described more strongly than it was implemented.

Now the core proof is closer by about one layer:

- The ROD two-pass contract exists in code.
- The server can stay responsive while queued runs execute.
- The model has a more accurate environment model.
- The desktop observation exposes enough window context to reason about
  non-focused windows without breaking `[ID]` scope.
- 10 consecutive real desktop app-open goals passed at 11 cycles.

The remaining gap is the hard workflow layer: browser conversation, response
contingency, summarization into Notepad, and YouTube playback. That requires a
better step/debug workbench and more robust browser/text-field behavior.

## Appendix: Handover Prompt For Next AI Session

```yaml
handover:
  project: endgame-ai
  date: 2026-06-20
  status:
    proven:
      - ROD two-pass LLM calls are implemented.
      - queued /run worker prevents overlapping graph loops.
      - observe/action desktop calls are serialized.
      - act prompt supports deterministic action chains.
      - observations include focused-window IDs plus non-ID WINDOWS list.
      - actions use the cached observation map instead of rescanning per verb.
      - verifier has deterministic confirms for focus/open launch evidence.
      - 10 consecutive real desktop "open notepad" goals passed at 11 cycles.
      - two-slot colony delegation was validated.
    not_yet_proven:
      - compound browser dialogue workflow with grok.com
      - saving a generated summary into Notepad
      - YouTube music playback after prior browser work
      - human-grade schema-driven wiring editor
      - runtime/pause graph rewiring from the dashboard
  immediate_goal:
    Rewrite the dashboard and step interface so both a human using the HTML UI
    and an AI using HTTP POST calls can inspect, step, pause, edit wiring, and
    debug the same live graph. Then use that step surface to develop and prove
    the compound Grok/Notepad/YouTube workflow.
  constraints:
    - Prefer wiring.json for behavior changes.
    - Keep Python as generic plumbing.
    - Keep the repository allowlist tight.
    - Do not commit runtime artifacts.
  recommended_order:
    - Finish schema-driven dashboard.
    - Add first-class server step/session endpoints if needed.
    - Validate manual GUI step equals API step.
    - Run the compound workflow in small stepped slices.
    - Commit only essential tracked files.
```
