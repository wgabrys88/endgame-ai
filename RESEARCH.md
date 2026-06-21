# RESEARCH.md - Direction and Proof Standard

This file explains the research direction behind `endgame-ai`. `README.md` is
the operational handover. This document is the design argument and validation
standard.

## Thesis

A small local model can do useful desktop work if it is embedded in a truthful,
inspectable signal graph. The model should not improvise the entire agent loop.
Each circuit should have one role, explicit inputs, strict output JSON, and a
limited set of mechanical verbs.

The long-term product is not a scripted Grok workflow. It is a wiring-first
organism that can:

- observe the real Windows desktop
- reason in constrained circuits
- act through deterministic verbs
- remember facts across context switches
- expose every state transition to humans and API clients
- hot-reload behavior through JSON
- suggest conservative wiring changes when stuck

## Research Boundary

Python is allowed to be strong at mechanics:

- HTTP server and API parity
- graph execution and state persistence
- model calls and JSON parsing
- desktop observation and cached target maps
- keyboard/mouse input
- action safety guards
- schema validation and wiring hot-reload
- colony bus plumbing

Python should not become the planner, browser-special-case brain, or hidden task
policy. Behavior belongs in `prompts/wiring.json`.

## ROD Position

ROD means the runtime separates reasoning from decision:

1. Build wired input blocks.
2. Ask the model to reason.
3. Store the reasoning.
4. Ask the model to decide as one JSON object.
5. Route only from parsed data and graph signals.

This matters because the main failure mode is contamination: stale traces,
verifier JSON, old app names, or previous goals leak into a circuit that should
only use current state. ROD is useful only while inputs remain honest and
bounded by role.

Key role boundaries:

- Planner sees goal, history, memory, completed steps, and structural traces.
- Act sees `SCREEN` and emits verbs.
- Verify sees step criteria, action evidence, and memory.
- Reflect sees failure evidence and suggests recovery strategy.
- Self-modify sees wiring summary and proposes one conservative wiring patch.

## What Has Improved

The project moved from a brittle loop toward an inspectable desktop organism:

- queued runner avoids overlapping `/run` loops
- resume state points to the next node
- observe/action calls are serialized
- deterministic action chains reduce needless scan cycles
- chained actions reuse the cached observation that `act` saw
- focused `[ID]` targets are scoped to the focused window
- `WINDOWS:` gives top-level awareness without expanding action scope
- targeted writes fail when the element is not writable
- planner and act no longer receive stale downstream reasoning
- planner treats traces as structure, not literals
- verifier has deterministic preflights for mechanical facts
- memory exists as explicit state through the `remember` verb
- dashboard and API share `/step`, `/inspect`, `/state`, and `/wiring`
- schema-driven graph editing exists in the HTML workbench
- observation depth is now wiring-configurable
- live wiring reload now updates action verbs and observer settings
- browser navigation ordering is mechanically normalized as focus browser,
  `ctrl+l`, write URL, Enter
- observer fallback avoids using shell/Desktop foreground as the actionable
  scope when a real application window is available
- act prompt policy now allows deterministic scroll/end/wait recovery on
  browser conversation pages before returning `CANNOT`
- model output budget now supports longer reasoning

The prior reliable milestone was repeated real `open notepad` completion. That
is useful but insufficient. The next proof must be contingent and multi-app.

## Stopped Run Evidence

Validation was stopped on request on 2026-06-21. No further tests should be run
until the next session explicitly resumes.

The latest real run reached this state:

- `state.json` exists locally and is ignored by git.
- `_resume_node` is `scheduler`.
- `step` is `7`.
- current step is `write summary of conversation to Notepad`.
- `memory` contains `grok_turn_1_response`, `grok_turn_2_response`, and
  `grok_turn_3_response`.
- last useful outcome was `remember grok_turn_3_response`.

What the run proved:

- deeper observation worked in real Chrome/Grok pages, showing dozens of
  observed entries instead of a tiny narrow view
- the browser navigation fix worked: Chrome focus happened before `ctrl+l`
- Grok loaded from real `grok.com`
- the system submitted the initial endgame-ai message
- the system remembered three visible Grok response snippets
- the system made follow-up submissions based on the running state

What remains:

- planner/act must split Notepad summary work into open/focus Notepad and write
  a MEMORY-derived summary
- verify should confirm the summary from the write action and/or visible
  Notepad content
- YouTube navigation/search/playback still needs real step evidence
- response capture should become less shallow; turn 2 and 3 memories captured
  visible short prompts/snippets, not full rich answer summaries

## Current Reliability Risks

### Observation Depth

The organism can only act on what reaches `SCREEN`. If the observer samples too
sparsely, reads only tiny text excerpts, or hides most visible content, the LLM
will make slower and less reliable decisions. Observation must be configurable
from wiring and visible in the workbench.

Current direction:

- lower probe spacing for richer UIA coverage
- read longer text pattern content
- render longer field/text previews
- list more top-level windows
- show total observed entries as well as actionable `[ID]` count
- keep focused-window target scope strict

### Browser State

Browser workflows combine navigation latency, focused field ambiguity, page app
state, login state, and dynamic response content. The runtime must preserve
generic browser invariants:

- focus browser before `ctrl+l`
- use `ctrl+l`, write URL/search, Enter for navigation
- do not type chat text into the address bar
- wait/observe when a response is still loading
- remember visible response facts before switching apps
- never verify a response that was not observed or remembered
- when leaving browser for Notepad, first convert browser MEMORY into a summary
  and then write that summary in the editor; do not try to write while Grok is
  still focused

### Prompt Contamination

Long runs accumulate history, reasoning, and traces. These are useful only if
circuit inputs remain role-specific. The planner must not see `SCREEN`.
Verifier and reflect must not invent elements. Act must not copy stale verifier
JSON. Traces must stay structural.

### Workbench Parity

The dashboard is not a demo surface. It is the collaborative debugger. A human
clicking Step and an API client posting `/step` must operate the same state and
same graph. Node/edge edits must hot-reload through the same `/wiring` endpoint
used by external tools.

### Self-Evolution

Self-modification should first tune wiring behavior, guards, limits, or simple
topology. It should not generate broad Python changes during a live desktop
failure. The correct self-evolution path is:

```text
failure evidence -> reflect diagnosis -> self_modify wiring patch ->
validate whole wiring -> hot-reload -> continue stepping
```

## Compound Proof Standard

The milestone is complete only when the real desktop workflow reaches all of
these states with inspectable evidence:

1. Chrome is opened or focused.
2. Browser navigates to `grok.com`.
3. Initial endgame-ai question is submitted to Grok.
4. A real visible Grok response is captured into `MEMORY`.
5. A follow-up based on response 1 is submitted.
6. A real response 2 is captured into `MEMORY`.
7. A follow-up based on response 2 is submitted.
8. A real response 3 is captured into `MEMORY`.
9. A summary derived from memory is written into Notepad.
10. YouTube is opened or focused.
11. Shakira Waka Waka is searched/opened and playback is visible.

Autonomous success is not required before the workbench is valuable. The
required near-term mode is collaborative step/debug: inspect, patch, hot-reload,
continue.

## Validation Method

For this target, simulated tests are not enough. The useful validation loop is:

1. Stop stale servers.
2. Inspect local `state.json` before cleaning; if it is the 2026-06-21 stopped
   state, resume from it or summarize it before deletion.
3. Start the real local server.
4. Confirm `/health` reports `simulation=false`.
5. Step through the compound goal via `/step` in small chunks.
6. Inspect compact state after each chunk.
7. Patch generic defects.
8. Preserve useful run evidence in docs or state before cleaning artifacts.
9. Restart and rerun from the smallest meaningful real slice.

Use `/smoke` only as a fast endpoint sanity check when appropriate. It is not
evidence that the compound workflow works.

## Completion Definition

The system is production-ready for the current vision when:

- behavior changes can be made in `prompts/wiring.json`
- the schema-driven HTML workbench can inspect and edit live wiring
- API and GUI paths have parity
- observer depth is sufficient for browser responses and editor text
- action chains are deterministic and safe
- memory captures real visible content before context switches
- self_modify can propose small wiring fixes from failure evidence
- real compound step validation succeeds end to end
- docs explain current state and handover prompts without stale restrictions

## Next Implementation Priorities

1. Continue removing small hardcoded truncations from state shown to the model
   or debugger.
2. Expand `prompts/wiring-schema.json` until all important wiring knobs are
   first-class editor fields.
3. Improve dashboard session ergonomics: named step sessions, state diff view,
   and explicit current-node resume controls.
4. Strengthen prompt roles for response capture and memory-derived summaries.
5. Fix the Notepad transition: plan open/focus Notepad, write summary from
   MEMORY, verify written content, then continue to YouTube.
6. Let self_modify edit conservative prompt/guard fields through validated
   wiring patches.
7. Keep running real slices of the compound workflow after each generic fix.

## Handoff Checklist

Before another AI continues:

- read `README.md` and this file
- inspect `git status --short`
- review current diffs in `server.py`, `actions.py`, `desktop.py`,
  `prompts/wiring.json`, `prompts/wiring-schema.json`, and `prompts/model.json`
- check ignored `state.json`; if present, it is useful resumable evidence from
  the stopped real run
- start no background helper that will be left running
- when validation begins, use real `/step` calls and compact evidence output
- do not hardcode the target workflow in Python

The correct final report is evidence-based: what was changed, which real steps
completed, where any failure remains, whether helper processes were stopped, and
which runtime artifacts were preserved or cleaned.
