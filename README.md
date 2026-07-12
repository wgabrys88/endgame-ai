# endgame-ai

This file describes the system to itself. It is read as source by the running
organism. It states only what the code and wiring.json actually do. If a line
here disagrees with the code, the code is the truth and this line is a defect to
be corrected during self-modification.

## What this system is

A single Python process that pursues one natural-language goal by looking at the
real desktop, deciding one action at a time through a language model, acting
through faculties, and judging the observable result. The process can rewrite its
own source and wiring at runtime, commit the change to git, and continue.

The Python is a fixed kernel that executes a graph. The graph, the prompts, the
contracts, and the acceptance rules all live in `wiring.json`. Meaning lives in
the wiring; mechanism lives in the code.

## Execution model

`core_organism.run` loads `wiring.json`, then runs a frontier loop. Each turn:

1. Pop the current node from the frontier.
2. Stop if the deadline passed or a stop file exists.
3. Emit a `node_start` event, call the node, emit a `node_complete` event.
4. The node returns one signal and a state patch.
5. `next_nodes_for(node, signal)` resolves the topology edge to the next node(s)
   and extends the frontier.

Exactly one node runs per turn. An edge value may be a single node name (linear)
or a list of names (fractal one-to-many). A signal with no matching edge is a hard
`TopologyContractError`. A drained frontier is also a hard error: the wheel must
always turn back to itself.

## Node protocol

Every node module exports `run(ctx)`. `ctx` carries `wiring`, `state`, `goal`,
`node`. LLM-driven nodes subclass `BaseNode` (`core_node_base.py`): `build_payload`
assembles the prompt input, `think` calls the model and validates that the returned
`record_type` matches the node's `expected_record_type`, then the node maps the
record to a signal and a patch. `core_loader.load` resolves a node name to
`<name>.py` by file, with no registry, so new node files become loadable the moment
they are written. A name may carry an instance suffix `base:instance`
(for example `node_execute:browser`); the class comes from the base, the instance
label is threaded through `ctx`.

## Topology

`topology.cycle_start` is `node_guidance:plan`. `topology.nodes` holds 24 nodes.
The normal working wheel:

`guidance -> observe -> planner -> scheduler -> guidance:act -> observe:act ->
dispatch -> execute:{browser,editor,terminal} -> barrier -> observe:verify ->
verify`. On `step_confirmed` verify returns to `scheduler`; on `step_denied` it
goes to `reflect`, which replans or reframes the action.

The self-evolution sub-wheel:

`reflect` may escalate to `node_self_modify`, then
`node_repair_probe -> node_observe:repair -> node_repair_dispatch ->
node_observe:repair_verify -> node_repair_validate`. On `repair_resolved` the
validator routes to `node_verify` so a self-change is judged by the same verifier
as any other action; on `repair_unresolved` it routes to `node_reflect`.

## Record contracts

Every model output is validated against a named contract in
`record_contracts`: `plan`, `schedule`, `execution`, `dispatch`, `action_frame`,
`verification`, `reflection`, `git_evolution_patch`, `satisfied`, `repair_probe`,
`repair_validation`. A wrong `record_type` or a disallowed signal fails the turn
and is classified by `core_state.classify_node_exception` for possible repair.

## Faculties

Actions run through faculty instances of `node_execute`: `browser`, `editor`,
`terminal`. `node_dispatch` chooses which faculties act; `node_barrier` joins their
results; `node_observe:verify` captures the after-state; `node_verify` decides
whether the step's `done_when` is observably met.

## Perception

`core_observation` and `core_desktop` read the live desktop through Windows UI
Automation and produce a text tree of on-screen elements with stable ids. Nodes see
the world only through this observation and the goal; there is no hidden channel.
Whatever is visible on the physical screen can enter observation.

## Self-modification

`node_self_modify` proposes a `git_evolution_patch`: file writes, file deletes,
and `wiring_patches`. `core_organism` applies the patch, commits a candidate on the
current branch (`context_mode` is `checked_out_branch`), but does not advance the
known-good marker. The candidate is proven only by a fresh behavioral probe:
`node_repair_validate` compares before-evidence with after-evidence for the exact
retried failure. Only on `repair_resolved` does `accept_self_evolution` advance
`refs/endgame/known_good`. If application fails and `hot_swap_on_failure` is set,
`hot_swap_to_known_good` restores the touched files. `self_modify.evolvable.
activation.immediate` lists files that take effect this run; others take effect on
the next run.

## Source visibility

The organism's view of its own source is `git ls-files`: only tracked files exist
to it. `.gitignore` is a strict allowlist (`*` then `!name` per file), so a new
`.py` file created by self-modification must also be added to `.gitignore` and
git-tracked, or it stays invisible and unloadable. Runtime outputs are deliberately
not tracked and never enter the source view.

## State and journals

`runtime_state.json` is the resumable state snapshot; on start without `--reset`
the process resumes from it. `runtime_control.json` allows external run/step/pause.
`runtime_events.jsonl` is a write-only journal (schema `endgame-ai.runtime-event.v1`)
emitted by `core_state.runtime_event` and `core_brain.log_runtime_event`. Nothing
reads the journal back into decisions; it exists for outside inspection only. A stop
file requests a clean stop.

## The model call

`transport_xai.call` posts to the xAI Responses API (`grok-4.3`) with `urllib` and
returns content, reasoning, and usage. `transport_file_proxy` is an offline
substitute. Transport is selected by `model.transport`. `model.global.timeout` and
an optional `brain_call_budget` bound cost. A large stable source prefix is sent for
prompt caching, so smaller source and prompts lower cost.

## Fractal

`node_spawn` and `cap_spawn` can start a child organism with redirected state,
control, and event-log paths. `fractal.max_recursion_depth` is 3;
`fractal.child_duration_seconds` is 60. A child pursues a sub-goal under its own
budget and reports outcome to the parent.

## Invariants

- One node per turn, chosen by the topology, never hard-coded.
- Every model output validates against a record contract; every signal against the
  node's allowed signals.
- Self-changes commit to git and never become known-good until a behavioral probe
  proves the original failure resolved.
- The wheel always turns; a dead end is a contract violation to be repaired.
- Fewer lines and clearer wiring are always preferable to more code.

## Running

`python core_organism.py "GOAL" --reset --duration-seconds N`

The process exits itself at the deadline. `--reset` clears prior runtime state.
`--start-node` and `--wiring` override the entry node and wiring file.
