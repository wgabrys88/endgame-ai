# RESEARCH.md - Reality, Direction, and Next Proof

This document is the strategic companion to `README.md`. The README is the
operational handover. This file explains why the organism matters, what the
previous session changed, and what must be built next.

## Thesis

endgame-ai is a local-first Windows desktop organism. Its central bet is that a
small local model can perform useful desktop work when it is embedded in a
truthful signal graph instead of asked to improvise a whole agent loop.

The graph constrains each role:

- planner produces current-goal-preserving human subtasks
- scheduler selects one current step
- observe produces a bounded desktop view
- act maps the step and screen to deterministic verbs
- verify judges completion evidence
- reflect diagnoses failure
- self_modify proposes conservative wiring patches
- colony routes work across local rods through a bus

The organism evolves by changing `prompts/wiring.json`: topology, prompt
contracts, guards, routing, limits, and behavior policy. Python should remain
small, generic, and mechanical.

## Previous Session Result

The previous session moved the project from a brittle proof to a repeatable
simple desktop loop.

The biggest technical change was making ROD literal. For each LLM-backed node,
the first call produces reasoning content and the second call emits the single
structured JSON object used by the circuit. Reasoning is stored for inspection
instead of being allowed to leak everywhere.

The second major change was reducing race and contradiction:

- `/run` and `/resume` use a queued runner, so the server does not start
  overlapping graph loops.
- Desktop observe/action calls are serialized.
- Resume state advances to the next node.
- `act` can chain deterministic verbs without repeated scans.
- Action execution uses the cached element map that produced `SCREEN`.
- A small chain settle delay replaces accidental hover-scan delay.
- Post-action desktop refresh is opt-in.
- Focused-window `[ID]` scope stays narrow.
- A `WINDOWS:` list gives non-actionable top-level window awareness.
- Targeted action mechanics focus HWNDs in Python.
- Missing cached targets fail instead of typing into the wrong focused field.

The third change was prompt hygiene:

- Every circuit first deduces what it sees or knows from its wired inputs.
- Non-`act` circuits are reminded that they do not see the desktop.
- Planner is told not to create focus-preparation steps for normal targeted
  click/write work.
- Act uses focus as a switch or confirmation step, not as preparation for a
  visible `[ID]`.
- Planner receives traces as structural examples only.
- Act no longer receives verifier/reflector reasoning.
- Planner no longer receives broad downstream reasoning that previously led it
  to copy stale verdicts or JSON shapes.
- Self-modify sees a concise wiring summary and conservative patch examples.

The measured result was a 10-run real desktop `open notepad` streak at about 11
cycles per run with a 15-cycle cap. That is not the final vision, but it proves
the organism can be made less fragile by aligning observation, prompts, and
mechanical execution.

## Current Implementation Additions

This implementation session did not run servers, `/smoke`, colony tests,
desktop goals, or runtime validation. It changed only tracked source,
documentation, schema, and wiring files.

Added in source:

- richer `/step` results with executed node, transition, state patch, full
  state, next node, and before/after debug context
- `/inspect` for wired input inspection without executing a node
- `POST /state` for GUI/API saved-state parity
- `POST /pause` for pause-between-nodes autonomous run control
- `/node/:type` patch-plus-full-state responses
- a rebuilt schema-driven HTML workbench with editable SVG graph nodes,
  draggable/reconnectable edges, generic schema/object editors, hot-reload
  saves, state panels, wired input panels, screen/window/outcome panels, and
  reasoning panels
- a top-level schema entry for the existing `observe` section
- `state.memory` plus a wiring-declared `remember` verb for carrying compact
  observed facts or summaries across app switches
- task-agnostic prompt refinements for browser navigation, contingent
  conversation turns, memory before context switches, verifier evidence
  discipline, reflector diagnosis, and conservative self-modification

The runtime research question now shifts from "can the UI express the shared
debug surface?" to "does the shared surface let a human and API client steer the
compound workflow to completion?"

## ROD Research Position

ROD works only if the contracts remain strict.

Reasoning should explain what the node believes based on its inputs. Decision
output should be a constrained JSON object for the current role. Observation
should be bounded and scoped. Routing should follow wiring edges. Python should
patch state and enforce mechanical truths, not make semantic plans.

Important invariants:

- `SCREEN` belongs to `act`.
- `[ID]` targets belong only to the focused window.
- `WINDOWS:` titles are context, not actions.
- Planner plans from the goal, history, completed steps, traces, and state.
- Verify decides from intended step and action evidence unless wiring gives it
  more.
- Reflect diagnoses why a step failed.
- Self-modify changes wiring conservatively and validates the whole document.

The prior failures were mostly contract failures. The system improved when
reasoning was isolated, stale traces were demoted to structure, and mechanical
facts were handled by code.

## Methodology

The working methodology is deliberately narrow:

1. Reproduce or inspect the exact failure state.
2. Determine whether the failure is behavioral wiring or generic plumbing.
3. Prefer a wiring change for policy, role boundaries, wording, guards, and
   routing.
4. Use Python only for mechanics the model cannot safely infer: focus, cached
   target maps, validation, queueing, state persistence, or HTTP parity.
5. Keep runtime artifacts out of commits.
6. Keep the tracked file set small.
7. Validate with static checks in implementation-only sessions.
8. Save runtime and desktop validation for sessions that explicitly allow it.

For the current implementation session, no server runs, `/smoke`, colony tests,
desktop streaks, or goal executions should be performed. The allowed checks are
lightweight: JSON parsing, schema parsing, Python AST parsing, and
`git diff --check`.

## Current Gap

The system can repeatedly open a simple app. It is not yet proven on a
multi-application contingent workflow.

The target workflow is:

```text
open Chrome
start conversation with grok.com about endgame-ai
keep the conversation based on Grok's real responses for 3 turns
save a summary of the conversation in Notepad
play Shakira Waka Waka on YouTube
```

This combines several hard cases:

- browser navigation
- login or site-state uncertainty
- reading real model responses
- preserving conversational context
- producing a summary from actual observed content
- switching from browser to Notepad
- writing into the correct application
- returning to browser media playback
- avoiding stale trace or prompt literals

Blind autonomous runs are not the right first tool for this proof. The next
layer is a shared step/debug workbench where a human can inspect and guide the
same graph state that an AI sees through API calls.

## Workbench Direction

The dashboard should become a schema-driven wiring and stepping workbench.

The source now implements that direction, pending runtime validation.

It needs to expose:

- live graph topology from `prompts/wiring.json`
- generic editors derived from `prompts/wiring-schema.json`
- node boxes with editable data, prompts, inputs, guards, and routing metadata
- edge connections that can be added, removed, and reconnected
- current node, next node, signals, state patch, and full state after `/step`
- reasoning content from both-pass ROD execution
- wired prompt inputs, especially `SCREEN`, `HISTORY`, `COMPLETED_STEPS`,
  `CURRENT_WIRING`, action evidence, and traces
- cached observation target IDs and non-actionable `WINDOWS:` titles
- pause, resume, inspect, run, step, and hot-reload controls

The key research requirement is parity. A GUI action should correspond to an
HTTP API call. An API call should update the same state and be visible in the
GUI. There should not be a hidden special path for human debugging.

## Wiring-First Behavior Direction

The compound workflow should be enabled by task-agnostic behavior rather than
hardcoded browser policy.

Planner should:

- preserve the current user goal and not copy old trace literals
- plan contingent work as short observable steps
- explicitly wait for and use real responses when the task depends on them
- avoid focus-prep steps when Python already handles target focus
- maintain enough state for multi-turn browser conversation and summarization

Act should:

- prefer short deterministic chains for known UI transitions
- use `SCREEN` and cached `[ID]` targets as ground truth
- use `remember` to store compact visible response facts before context switches
- write only when the intended field or app is focused or targeted
- avoid rescanning or over-focusing inside deterministic chains
- fall back to observe when the target is not visible

Verify should:

- accept mechanical evidence Python can prove
- reject stale or unrelated evidence
- confirm memory capture only from `remember` outcome plus non-empty `MEMORY`
- distinguish "step progressed" from "whole goal done"

Reflect should:

- identify whether failure came from stale state, missing target, wrong app,
  site state, insufficient observation, or a bad plan
- choose a conservative recovery route

Self-modify should:

- understand the current wiring summary
- prefer small prompt, guard, or input-boundary patches
- avoid broad topology changes unless the defect is plainly topological
- keep patches task-agnostic and reusable

## Open Questions

- How strict should `prompts/wiring-schema.json` become before it blocks
  useful self-modification?
- Should the server own first-class named step sessions, or is persisted state
  plus `/step` enough for now?
- What is the minimum browser observation needed for Grok and YouTube without
  adding external dependencies?
- How should ignored trace memory be curated if traces remain outside commits?
- When should self-modify be allowed to change topology rather than prompts and
  guards?

## Progress Estimate

Approximate state after the previous session:

- Desktop actuation substrate: 60 percent
- ROD role separation: 70 percent
- Simple-goal reliability: 65 percent
- Compound browser workflows: 35 percent
- Self-modifying wiring UX: 45 percent
- Colony as useful work router: 35 percent
- Breeding reactor with trace selection: 20 percent

The next useful progress is not another claim of generality. It is a practical
step/debug workbench plus a successful compound workflow proof.

## Next Proof Plan

The next validation session should:

1. Review this file, `README.md`, and the current diff.
2. Start the server only in a validation session.
3. Open the dashboard and call `/step` through API side by side.
4. Confirm GUI actions and API calls produce equivalent state transitions.
5. Step Chrome open/navigation.
6. Step the Grok conversation one real response at a time.
7. Save a summary to Notepad based on observed content.
8. Step YouTube search/playback.
9. Move any task-specific lesson back into task-agnostic wiring or generic
   plumbing.

The research milestone is complete only when the workflow succeeds with
step-level evidence a human can inspect.
