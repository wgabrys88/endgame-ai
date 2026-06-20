# RESEARCH.md - Reality, Direction, and Next Proof

This file is the strategic companion to `README.md`. The README is the
operational handover. This document explains why the system matters, what was
learned in the latest session, and what must be proven next.

## Thesis

endgame-ai is a small local desktop organism. It does not need to rewrite its
Python source to evolve. It rewrites and hot-reloads its topology and behavior
contract in `prompts/wiring.json`.

The research bet is that a small local model can perform useful desktop work
when the surrounding organism constrains the model's job:

- planner produces human subtasks
- scheduler selects the current step
- observe produces a bounded desktop view
- act maps the step and screen to verbs
- verify judges outcome evidence
- reflect diagnoses failure
- self_modify suggests wiring changes
- colony routes work across rods through a bus

That structure lets a weak local model act more like a stronger model because
it is filling a constrained role instead of improvising an entire agent loop.

## What This Session Proved

The work moved the system from "promising but brittle" to "locally repeatable on
a narrow desktop class."

Evidence:

- ROD is implemented as a two-call LLM pattern for every LLM node:
  reason first, decide second.
- The server queues autonomous runs instead of spawning overlapping run loops.
- HTTP remains available while the graph runner is doing slow observe/act work.
- Focus is no longer treated as an LLM planning crutch for normal element
  interaction. Python already has HWNDs and performs mechanical focus as part
  of click/write.
- Action execution now reuses the observation map that produced the act
  prompt's `SCREEN`, so deterministic chains do not rescan the desktop before
  every verb and `[ID]` targets remain tied to what the model saw.
- A small configured delay between chained verbs replaces the accidental delay
  that hover rescans previously provided.
- Post-action screen refresh is now opt-in because verify and reflect consume
  action evidence, not desktop elements.
- Observation exposes two layers:
  - focused-window actionable elements with `[ID]`
  - non-actionable `WINDOWS:` titles for top-level window awareness
- The prompt base now starts by requiring each circuit to deduce what it sees
  or knows from its input blocks.
- Planner and act were isolated from stale downstream reasoning that caused
  schema poisoning.
- Deterministic verifier preflights now cover mechanical truths that the model
  repeatedly misjudged:
  - successful focus means the window exists
  - `win+r`, app name, `enter` is app-launch evidence
- Colony delegation was validated between two slots.
- The loop completed 10 consecutive real desktop `open notepad` goals at 11
  cycles each.

## Methodology Used

The debugging pattern was:

1. Run a real goal with a tight cycle cap.
2. Inspect `state.json` for the exact failure.
3. Decide whether the failure belongs to wiring or Python plumbing.
4. Patch the smallest responsible surface.
5. Rerun the narrow proof.
6. Clean runtime artifacts.

Important examples:

- When act started copying reflector diagnosis JSON, the fix was not more
  retries. The fix was to remove verify/reflect reasoning from act's prompt
  inputs.
- When planner copied old trace literals into a new write goal, the fix was to
  label traces as structural examples only and instruct planner to preserve
  current-goal literals.
- When verifier denied a successful focus as evidence for "Notepad is open,"
  the fix was a deterministic preflight because Python knew focus succeeded.
- When chained actions caused repeated hover scans, the fix was to keep the
  focused-window element map from observe and execute against that map instead
  of scanning again for every verb.

This is the core engineering pattern for the organism: let the model handle
semantic choice, but make the plumbing enforce mechanical truths.

## How Much Closer Is The Vision?

Closer by one proof layer, not finished.

Before this session:

- ROD was described but not faithfully implemented as two calls per LLM node.
- The loop could work but was slow and fragile.
- Focus behavior confused the model and wasted cycles.
- Colony delegation was code-complete but unvalidated.
- The dashboard existed but was still too thin for serious step debugging.

After this session:

- The core ROD loop is real.
- A small local model can repeatedly complete a simple real desktop goal under
  the target cycle count.
- The system now has a more truthful environment model.
- The next bottleneck is not "can it open an app?" but "can it be debugged and
  evolved through a human/AI shared step surface?"

Approximate progress toward the larger vision:

- Desktop actuation substrate: 60 percent
- ROD role separation: 70 percent
- Simple-goal reliability: 65 percent
- Compound browser workflows: 25 percent
- Self-modifying wiring UX: 20 percent
- Colony as useful work router: 35 percent
- Breeding reactor with trace selection: 20 percent

## The Next Proof

The next target workflow is intentionally hard:

```text
open chrome,
start conversation with grok.com AI about endgame-ai,
keep the conversation based on what Grok responds for 3 turns,
save the summary of conversation in Notepad,
then run Shakira Waka Waka on YouTube
```

This cannot be proven by blind `/run` alone. It needs step-level visibility.
The human dashboard and AI API must share the same control surface.

## Required Step Workbench

The HTML dashboard is now moving into the role of primary visual debugger. The
current version has a first-class `/step` backend endpoint and a graph workbench
that can inspect nodes and edges, edit wiring JSON, fetch the schema, and save
through `/wiring`.

It still must mature into a full runtime wiring lab:

- show the live wiring graph from `prompts/wiring.json`
- derive editable node and edge forms from `prompts/wiring-schema.json`
- render current node, pending signals, next edge, state patch, and reasoning
- let a human step the graph exactly as an AI can via HTTP
- support pause/resume and safe hot-reload of wiring
- expose schema validation errors before POST `/wiring`
- show the focused-window `SCREEN` and `WINDOWS:` context separately
- display history, last actions, last outcome, and verifier/reflector reasoning
- make every UI element meaningful: no decorative controls

The dashboard should not hardcode future schema fields if avoidable. It should
inspect the schema and the wiring document, then render generic object editors
for unknown properties.

## Wiring-First Direction

The long-term goal is that adding behavior does not require editing Python.
Python should be changed only when a generic capability is missing:

- a new endpoint for stepping sessions
- a generic schema validator
- a generic wiring patch operation
- a new mechanical verb
- a safer desktop observation primitive

Task policy, role personality, routing, guards, limits, prompt inputs, and graph
edges should live in `prompts/wiring.json`.

## Open Questions

- Should the server own a first-class step session, or should the dashboard keep
  doing client-side stepping through `/node/:type`?
- Should `prompts/wiring-schema.json` become strict enough to drive the editor
  without custom dashboard knowledge?
- How should trace memory be kept if `prompts/traces.jsonl` remains ignored and
  not committed?
- Should `self_modify` be limited to wiring prompt/guard edits until the UI can
  visualize topology mutations safely?
- What is the minimum browser observation needed for Grok and YouTube flows
  without adding dependencies?

## Research Position

The broader field is moving toward self-evolving agents, multi-agent routing,
and stronger desktop control. endgame-ai's differentiator remains:

- local-first
- stdlib-only
- Windows desktop control
- topology-level self-modification
- human-visible signal graph
- small enough to understand and mutate

The project is viable only if it proves real desktop reliability before cloud
agents make the baseline trivial. The next proof must therefore be practical:
the system should complete the Grok/Notepad/YouTube workflow with step-level
debug evidence, not just claim architectural potential.

## Next Session Checklist

1. Review `README.md`, this file, and current `git diff`.
2. Start the server locally.
3. Use the HTML dashboard and API `/step` side by side.
4. Continue upgrading the dashboard into a real wiring workbench.
5. Validate that GUI step and API step produce the same node transitions.
6. Step through the compound browser workflow in slices:
   - Chrome open and navigate
   - Grok prompt submit
   - capture/continue three turns
   - Notepad summary save
   - YouTube search/play
7. Move task-specific fixes into wiring prompts/guards first.
8. Commit only tracked essential files.
