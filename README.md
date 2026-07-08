# endgame-ai

This branch is the token-reduced organism branch.

The tracked repository is treated as self-evolution prompt material during
`topology_patch`, so the refactor removed duplicate runtime source, unused
transports, forensic helper scripts, repeated prompt text, datasheet-style
metadata, and fallback paths that kept old behavior alive without being
selected by `wiring.json`.

This README is intentionally the exception. It is now large because it is the
handover document for what changed, what stayed, why removed behavior was
removed, and how a future agent can reintroduce specific capabilities in the
smaller architecture. The next architecture step should exclude `README.md`
from any runtime prompt or stable-prefix source bundle if prompt size matters.

Branch truth at the time this file was rewritten:

- Current branch: `token-reduction`.
- Main source used for reinterpretation: `main:README.md`.
- Current runtime topology is still bus-routed and hot-swappable through
  dynamic `node_*.py` imports.
- Current selected LLM transport is only `transport_xai`.
- Current UI observation is Windows UI Automation through `core_observation.py`
  and `core_desktop.py`.
- Current execute capability still uses unrestricted local `exec(code, ns)`.
- Current self-modify path still applies file writes, file deletes, wiring
  patches, commands, git commits, known-good updates, and hot-swap on failure.
- Runtime state, control, and events are still untracked `runtime_*` files.
- The refactor commits before this README rewrite were:
  - `fc1c1b6 Reduce prompt surface and remove guardrail bloat`
  - `5d869f4 Compact observation and execution runtime`
  - `860289e Hit LOC target with compact brain and node contracts`
  - `79bd49d Cross token and LOC reduction thresholds`

Measured before this README expansion:

| Surface | Main | Branch before README expansion | Delta |
|---------|------|--------------------------------|-------|
| Runtime/code tracked files excluding README | 31 files, 6196 counted lines, 258083 chars | 24 files, 3038 counted lines, 144990 chars | 7 files deleted, about 51% line reduction, about 44% char reduction |
| Entire tracked repo before README expansion | about 291k chars | about 146k chars | about 50% char reduction |

The README expansion intentionally changes the entire-repo prompt-size number.
That is accepted for this task because this document is meant to be future
reference material and should be excluded from runtime prompt ingestion later.

## Read This First

The old main README described a Phase 3 organism with diagrams, long contracts,
multiple transports, forensics helpers, and a token-reduction appendix that was
still a plan. This branch makes Appendix A real in code while preserving the
organism's core contract:

1. The topology is still a graph, not a fixed call stack.
2. `wiring.json` is still the single source for selected transport, topology,
   prompts, observe config, paths, control defaults, and self-modify config.
3. `core_organism.py` still routes by emitted node signals.
4. Nodes are still hot-loaded from files named in topology as `node_*.py`.
5. The selected transport is still hot-loaded by name.
6. Observation still performs UIA RAW -> FILTER -> MAP and writes
   `fresh_observation`, `desktop_tree_text`, and `action_index`.
7. Planner, scheduler, execute, verify, reflect, frame, self-modify, satisfied,
   and error nodes still cooperate through state patches.
8. Every LLM node still receives a fresh observation payload before a brain call.
9. `effective_goal` is still rewritten through the cycle.
10. Execute still runs model-supplied Python through local `exec(code, ns)`.
11. Self-modify still writes repo files, applies wiring patches, runs commands,
    commits, updates the known-good ref, and reloads wiring.

The old README also described several things that are no longer true:

- There is no tracked `transport_openai.py`.
- There is no tracked `transport_opencode.py`.
- There is no tracked `transport_browser_ai.py`.
- There is no tracked `transport_file_proxy.py`.
- There is no tracked `export_brain_forensics.py`.
- There is no tracked `analyze_graph.py`.
- There is no tracked `check_events.py`.
- There is no `runtime_self_evolution_enabled.json` gate.
- There is no per-node datasheet contract.
- There is no patch-key write whitelist enforced by bus datasheets.
- There is no code-generated Mermaid topology helper.
- There is no full JSON Schema validator.
- There is no tracked `requirements.txt`.
- There is no local LLM fallback if xAI is unavailable.

Those removals were intentional prompt-surface deletions. The sections below
explain how to reintroduce each item in the reduced architecture if it becomes
important again.

## Current Organism In One Screen

The current cycle is:

```text
node_observe
  initial_screen -> node_planner
  screen_ready    -> node_execute

node_planner
  step_ready -> node_scheduler
  reflect    -> node_reflect

node_scheduler
  step_ready    -> node_observe
  plan_complete -> node_satisfied

node_execute
  verify  -> node_verify
  frame   -> node_observe
  reflect -> node_reflect

node_verify
  step_confirmed -> node_scheduler
  step_denied    -> node_reflect

node_reflect
  retry          -> node_observe
  replan         -> node_planner
  frame          -> node_frame_action
  escalate       -> node_self_modify
  topology_patch -> node_self_modify
  give_up        -> node_satisfied

node_frame_action
  framed  -> node_observe
  reflect -> node_reflect

node_self_modify
  modified      -> node_planner
  modify_failed -> node_reflect

node_error
  planner -> node_planner
  reflect -> node_reflect
  halt    -> halt

node_satisfied
  halt -> halt
```

This is still the main README's observe -> plan -> execute -> verify -> reflect
organism, but the branch makes the wiring contract compact and executable:

- The topology is in `wiring.json`.
- Routing is implemented by `core_organism.next_node_for`.
- Signal validation is implemented by `core_node_base.call_node` through
  `core_bus.validate_signal`.
- Node modules are imported dynamically by `core_node_base._load_node`.
- Brain transport modules are imported dynamically by
  `core_brain._load_transport_module`.
- Execute namespace injection is built by `core_nodes.build_capability_runtime`.

## Main README Reinterpretation Ledger

This table maps the old README concepts to the current branch truth.

| Main README concept | Current branch truth | Why changed | Compact reintroduction path |
|---------------------|----------------------|-------------|-----------------------------|
| Badges and marketing header | Removed from README runtime checkpoint and replaced here by branch facts | Badges cost prompt tokens and do not affect runtime | Keep badges only in an excluded README, never in source prompt material |
| "No cloud, no secrets" | Selected transport is `transport_xai`, which calls `https://api.x.ai/v1/responses`; secrets are not stored in repo and `XAI_API_KEY` is expected in environment | The old sentence conflicted with xAI usage | If local-only mode is needed, reintroduce `transport_openai.py` or another transport and select it in `wiring.model.transport` |
| "No fallback" intent | Preserved for selected brain transport failure; `transport_xai` and `_load_transport_module` fail hard | Duplicate fallback transports were deleted | Reintroduce transports as explicit selected modules, not automatic fallbacks |
| UIA observation numbers such as 253 probes and 79 elements | Not fixed numbers. Counts are runtime scan results from `core_observation.gather_raw` and `build_tree_and_map` | Hard-coded example counts become stale and waste tokens | Keep examples in excluded docs; runtime evidence lives in `fresh_observation.scan_stats` |
| Goal narrative memory | Preserved. Nodes append `[PLANNER REWRITE]`, `[SCHEDULER]`, `[EXECUTE]`, `[VERIFY]`, `[REFLECT]`, `[FRAME_ACTION]`, `[SELF_MODIFY]`, and `[SATISFIED]` text into `effective_goal` | This behavior is core organism state, not deleted | If richer narrative is needed, adjust node patch text in `node_*.py`, not duplicated prompts |
| Bus frame propagation | Preserved as `_last_bus_frame` trace added by `core_node_base.call_node` | The shape is compacted but still logged in state/events | Extend `core_bus.NodeOutput.trace` if more fields are required |
| Per-node datasheets and write whitelists | Removed. There is no datasheet object and no patch-key subset check | Datasheets duplicated code and prompts; topology plus record rules now carry the contract | Add a compact `wiring.contracts.<node>.writes` map and check it in `core_node_base.call_node` if write validation is required |
| Many transport table entries | Removed except `transport_xai` | Unselected transports were recurring prompt cost | Reintroduce one transport module at a time with `call(messages, cfg)` and one config entry |
| `runtime_self_evolution_enabled.json` safety gate | Removed. `node_self_modify` can propose patches when routed; `core_organism` applies them without that flag | The branch preserves unsafe-by-design evolution and removes guardrail bloat | If a gate is intentionally wanted later, add one compact check before `nodes.apply_evolution_patch` in `core_organism.run` |
| Forensics export scripts | Removed as tracked code | They are operator tools, not organism runtime | Recreate as untracked tools that parse `runtime_events.jsonl`, or add a compact command outside prompt surface |
| Mermaid generator in runtime modules | Removed | Topology is already data in `wiring.json`; generated diagrams are docs, not runtime | Generate diagrams from `wiring["topology"]["edges"]` in an excluded tool |
| Appendix A token reduction plan | Implemented substantially | This branch was created to do it | Remaining reduction should focus on code/wiring, excluding README |
| Appendix B fractal topology | Still not implemented | Parallel routing and child organisms need new execution semantics | Add list-valued edge support in routing, a barrier node, and `spawn_organism` in execute runtime |
| Appendix C missing plans | Still mostly missing, now with clearer insertion points | Refactor prioritized deletion/unification | Use the reintroduction notes below |

## Deterministic Traceback

This is the current branch's runtime call chain.

### Startup And Wiring

```text
core_organism.main(argv)
  -> argparse reads goal, --reset, --duration-seconds, --brain-call-budget,
     --start-node, --wiring
  -> core_organism.run(...)
  -> core_stop_check.register_pid("organism")
  -> core_wiring.load_wiring(wiring_path)
       -> core_wiring.root_path(path, "wiring.json")
       -> core_wiring.load_json(path)
       -> core_wiring.validate_wiring(cfg)
  -> optional brain_call_budget override in w["model"]
  -> reset path:
       -> core_wiring.reset_runtime(w)
       -> deletes runtime state/control if present
       -> core_stop_check.clear_stop()
  -> resume path:
       -> reads runtime_state.json if present
       -> resumes next_node/start_node from state/topology
  -> writes runtime_state.json
  -> logs organism_start or organism_resume
```

`core_wiring.validate_wiring` is strict about required key presence and selected
transport presence. It is not a full JSON Schema validator. It type-checks some
top-level and topology values, but many inner config paths are checked for
existence with `object`, which every Python value satisfies. This is a truthful
remaining gap from the original strict-schema goal.

How to tighten it:

1. Replace the broad `_require(cfg, path, object)` calls in
   `core_wiring.validate_wiring` with exact expected types.
2. Keep validation in `core_wiring.py`, not scattered through consumers.
3. Do not add fallback defaults in consumers; make malformed wiring fail at load.

### Node Dispatch

```text
core_organism.run loop
  -> state.wait_before_node(w, st, current, deadline_at)
  -> state.runtime_event("node_start", state=bus.state_brief(st))
  -> ctx = {"wiring": w, "state": dict(st), "goal": goal, "node": current}
  -> core_node_base.call_node(current, ctx)
       -> core_node_base._load_node(current, w)
            -> imports f"{paths.nodes}/{current}.py"
            -> requires module-level run(ctx)
       -> node module run(ctx)
       -> core_bus.coerce_node_output(...)
       -> core_bus.validate_signal(w, current, output.signal)
       -> output.trace(node=current)
       -> patch["_last_bus_frame"] = trace
  -> core_organism handles node_self_modify patch if present
  -> st.update(patch)
  -> next_node_for(w, current, signal)
  -> write runtime_state.json
  -> state.runtime_event("node_complete", ...)
```

The dynamic import contract is smaller than main:

- `paths.nodes` is `"."`.
- Each topology node maps to `<node_name>.py`.
- Each node file exports `run(ctx)`.
- LLM nodes usually subclass `core_node_base.BaseNode`.
- Mechanical nodes return `bus.emit(...)` directly.

### Brain Calls

```text
BaseNode.run(ctx)
  -> BaseNode.think(ctx)
       -> prompt = wiring["prompts"][prompt_key]
       -> payload = node.build_payload(ctx)
       -> core_brain.think(prompt, payload, w, expected_record_type=...)
            -> _with_fresh_observation(payload, w)
            -> json.dumps(dynamic payload)
            -> _record_response_format(expected_record_type) if structured outputs enabled
            -> core_brain.call(messages, w, request_config=...)
                 -> core_wiring.get_transport_config(w)
                 -> core_brain._load_transport_module(transport, w)
                      -> imports f"{paths.brains}/{transport}.py"
                      -> requires call(messages, cfg)
                 -> transport_xai.call(messages, cfg)
                 -> log brain_request / brain_response / brain_error
            -> _commit_record(...)
            -> _validate_record_contract(...)
  -> node.signal_from_data(record.data, ctx)
  -> node.patch_from_record(record, ctx)
  -> bus.emit(signal, patch, record=record, evidence=...)
```

`core_brain._RECORD_RULES` is the compact replacement for the old verbose
record-contract descriptions. It checks required data keys and enumerated
signals for:

- `plan`
- `schedule`
- `execution`
- `action_frame`
- `verification`
- `reflection`
- `git_evolution_patch`
- `satisfied`

Richer schemas were removed. To reintroduce them compactly, expand
`core_brain._record_response_format(record_type)` and `_RECORD_RULES` together.
Do not duplicate the same shape in every node prompt.

### Observation Dispatch

```text
node_observe.run(ctx)
  -> config = ctx["wiring"]["observe_config"]
  -> core_desktop.get_desktop(config).observe(config)
       -> Desktop.observe(config)
       -> core_observation.observe(self, hover_cache_config)
            -> gather_raw(cfg, desktop)
            -> filter_raw(raw_nodes, cfg, screen)
            -> build_tree_and_map(...)
  -> patch:
       observed_at
       desktop_tree
       desktop_tree_text
       action_index
       fresh_scan
       observation_artifact
       rendered_node_count
       max_llm_nodes
       llm_node_limit_hit
       fresh_observation
  -> signal:
       initial_screen if no plan exists
       screen_ready if plan exists
```

The current observation config consumed from `wiring.json` is:

```json
{
  "hover_cache": {
    "enabled": true,
    "scan": {
      "step_px": 64,
      "delay_ms": 0,
      "max_subtree_nodes_per_point": 2000,
      "max_total_nodes": 10000
    },
    "filter": {
      "max_elements": 500,
      "max_per_window": 30,
      "max_text": 200,
      "require_interactive": true
    }
  }
}
```

`build_tree_and_map` also reads optional filter keys if present:

- `max_depth`
- `max_children_per_window`
- `max_llm_nodes`

Those optional knobs were removed from `wiring.json` to reduce prompt surface.
They can be reintroduced by adding them under
`observe_config.hover_cache.filter` and tightening `validate_wiring` to require
them if they become part of the contract again.

Property IDs and pattern IDs were removed from wiring. They now live as Python
constants in `core_observation.py`:

- `SCAN_PROPERTY_IDS`
- `SCAN_PATTERN_IDS`
- UIA property constants like `PID_RUNTIME_ID`, `PID_NAME`, `PID_HWND`
- UIA pattern constants like `PID_VALUE_PATTERN`, `PID_TEXT_PATTERN`

This was done because exposing raw UIA ID lists in `wiring.json` made topology
prompt material bigger without giving the organism useful runtime choice. If
runtime-selectable UIA properties are needed later, add one compact named
profile in wiring and map it to constants inside `core_observation.py`.

### Execute Namespace Injection

`node_execute.py` still executes model-provided Python:

```python
exec(code, ns)
```

There is no sandbox. There is no command guard. There is no filesystem guard.
There is no import guard. The only current non-policy runtime checks around
execution are:

- The LLM must emit `conclusion == "EXECUTE"` with `next_signal == "verify"`.
- Empty code is rejected for `EXECUTE`.
- Non-execute conclusions cannot include code.
- A duration deadline can stop action before execution.
- Helper actions record action events and raise if the helper returns
  `ok != True`.
- Empty execute output is treated as failure if there is no result, stdout,
  stderr, or recorded body action.

The injected namespace comes from `core_nodes.build_capability_runtime(ctx)` and
currently includes:

| Name | Purpose |
|------|---------|
| `action_nodes(action=None)` | List actionable UIA nodes from latest observation |
| `node_by_id(node_id)` | Resolve latest actionable node |
| `click(x, y, hwnd=0)` | Win32 click |
| `click_node(node_id)` | Click center of latest actionable node |
| `read_node(node_id)` | Read node text/name/value from latest observation |
| `type_text(text)` | Type text through Win32 key events |
| `press_key(key)` | Press a named key |
| `hotkey(*keys)` | Press a key combination |
| `scroll(x, y, amount, hwnd=0)` | Scroll at coordinates |
| `scroll_node(node_id, amount=-3)` | Scroll at latest actionable node |
| `open_url(browser, url)` | Open browser in known local install paths or default |
| `observe_with_config(hover_cache_config)` | Run a fresh UIA observation with merged hover-cache config |
| `observe_area(left, top, right, bottom, max_llm_nodes=None, max_depth=None, step_px=None)` | Run a bounded UIA observation |
| `subprocess`, `ctypes`, `os`, `sys`, `json`, `re`, `time`, `pathlib`, `math`, `random`, `types` | Local Python modules |
| `capabilities` | `capability_manifest(ctx)` |
| `repo_root` | Repository root string |
| `python_executable` | Current Python executable |
| `topology_summary` | Current topology summary |
| `state`, `wiring`, `goal`, `last` | Current runtime context |
| `fresh_observation`, `desktop_tree`, `desktop_tree_text`, `action_index`, `observation_artifact` | Latest observation context |
| `observed_at`, `fresh_scan` | Observation freshness markers |
| `action_events`, `_action_events` | Recorded body-action events |

The old README's idea of a broad execute runtime is preserved. What was removed
is the extra wrapper vocabulary and preflight logic that duplicated these
helpers.

If a `pyautogui`/`pag` facade is needed later, add it inside
`core_nodes.build_capability_runtime` as a thin adapter over existing helpers:

```python
pag = types.SimpleNamespace(
    click=lambda x, y: click(x, y),
    write=type_text,
    press=press_key,
    hotkey=hotkey,
    scroll=lambda amount: scroll(0, 0, amount),
)
ns["pag"] = pag
```

Do not add a second action stack unless UIA/Win32 cannot satisfy the workflow.

### Self-Modify Dispatch

```text
node_reflect emits escalate or topology_patch
  -> topology routes to node_self_modify
  -> node_self_modify.run(ctx)
       -> nodes.prepare_self_evolution(wiring)
       -> captures workspace manifest
       -> builds runtime and git context
       -> brain.think(... expected_record_type="git_evolution_patch")
       -> returns patch["git_evolution_patch"]
  -> core_organism.run detects current == "node_self_modify" and patch exists
       -> nodes.apply_evolution_patch(w, {"data": evolution_patch})
       -> nodes.commit_self_evolution(w, applied, evolution_patch)
       -> wiring.load_wiring(wiring_path)
       -> runtime_event("self_modify_applied", ...)
       -> if failure and hot_swap_on_failure:
            nodes.hot_swap_to_known_good(w, paths=touched or None)
```

Current self-modify patch data keys:

- `summary`
- `rationale`
- `read_files`
- `wiring_patches`
- `file_writes`
- `file_deletes`
- `commands`
- `expected_validation`

Current patch enforcement:

- Existing file writes must declare the file in `read_files`.
- Existing file deletes must declare the file in `read_files`.
- Wiring patches require `read_files` to include `wiring.json`.
- Evolution paths must stay under the repository root.
- Python writes are compiled before acceptance.
- JSON writes are parsed before acceptance.
- Wiring patches are applied in memory and then saved through `save_wiring`.
- Commands run locally with `subprocess.run`.
- On failure, file snapshots are restored if
  `self_modify.execution.rollback_on_failure` is true.
- On successful changed files, git add/commit is run and
  `refs/endgame/known_good` is updated through `update_known_good_ref`.
- If `self_modify.git.push_after_commit` is true, branch and known-good ref are
  pushed to the configured remote.

Removed from the old README:

- The `runtime_self_evolution_enabled.json` gate.
- Folklore patch-path blocking language like "blocked action_contract".
- Duplicate known-good commit seed in wiring.
- Extra safety narrative around disabled evolution.

Current truth:

- Evolution is routed by topology and record contracts, not by an external flag.
- `wiring.self_modify.known_good_ref` still names the git ref.
- The commit value is not duplicated in wiring.
- A runtime evidence file `runtime_known_good_commit.json` can be written by
  `update_known_good_ref`, but it is untracked and ignored.

How to reintroduce a flag gate if future operation requires it:

1. Add a compact `self_modify.enabled_flag_path` key to `wiring.json`.
2. Add an exact type check in `core_wiring.validate_wiring`.
3. In `core_organism.run`, before `nodes.apply_evolution_patch`, fail hard if
   the flag does not exist.
4. Do not add a second prompt telling self-modify about the gate unless the node
   must reason about it.

That would intentionally reduce the unsafe-by-design behavior and should only
be done if the operator changes the organism contract.

## Topology And Data Flow

The old README used Mermaid diagrams to show the graph. Runtime Mermaid
generation was removed. The real source is now only `wiring.json`:

```json
"topology": {
  "cycle_start": "node_observe",
  "nodes": [
    "node_planner",
    "node_scheduler",
    "node_observe",
    "node_execute",
    "node_frame_action",
    "node_verify",
    "node_reflect",
    "node_self_modify",
    "node_satisfied",
    "node_error"
  ],
  "edges": {
    "...": "..."
  }
}
```

The current topology is still one-to-one: every emitted signal maps to exactly
one next node string. The current bus and `next_node_for` do not support list
targets, fan-out, fan-in, or barrier joins.

Why list-valued edges were not added in this refactor:

- They are not a deletion/unification change.
- They require a new state shape for concurrent child frames.
- They require scheduler and verifier semantics for parallel completion.
- They require a barrier or join node.

How to add one-to-many compactly later:

1. Change `core_organism.next_node_for` to return `str | list[str]`.
2. Add a `node_barrier.py` mechanical node or an in-state join structure.
3. Extend `core_bus.validate_signal` only enough to accept the same signal
   contract while the topology edge value is list-valued.
4. Add node aliases or instance IDs only in wiring, not by copying node files.
5. Keep `BaseNode` unchanged if possible; concurrency belongs in the organism
   loop or a barrier node.

## Signal Contracts

Current signal contracts come from `wiring.json` topology edges and node code.

| Node | Kind | Inputs | Outputs | Writes |
|------|------|--------|---------|--------|
| `node_observe` | mechanical | `wiring.observe_config`, desktop | `initial_screen`, `screen_ready` | `fresh_observation`, `desktop_tree`, `desktop_tree_text`, `action_index`, observation stats |
| `node_planner` | LLM `plan` | goal, state brief, fresh observation, previous plan, completed steps | `step_ready`, `reflect` | `plan`, `root_plan_intent`, `step`, `plan_complete`, `reasoning`, `effective_goal` |
| `node_scheduler` | mechanical | `plan.intent`, `step`, `root_plan_intent`, completed steps | `step_ready`, `plan_complete` | `current_step`, `step_goal`, `action_frame`, `effective_goal`, completion state |
| `node_execute` | LLM `execution` plus raw `exec` | current step, action frame, state, observation, capability manifest | `verify`, `frame`, `reflect` | `last_action`, `last_code`, `last_result`, `last_error`, `last_failure`, `effective_goal` |
| `node_verify` | LLM `verification` | step, last action/result/error, observation | `step_confirmed`, `step_denied` | `verification`, `last_verification`, `completed_steps`, `step`, `failure_streak`, `effective_goal` |
| `node_reflect` | LLM `reflection` plus mechanical routing override | last failure, verification, action, observation, failure streak | `retry`, `replan`, `frame`, `escalate`, `topology_patch`, `give_up` | `reflection`, `last_reflection`, `failure_streak`, optional `topology_patch`, `effective_goal` |
| `node_frame_action` | LLM `action_frame` | step, observation, last failure evidence | `framed`, `reflect` | `action_frame`, `framing_attempted_for_step`, `effective_goal` |
| `node_self_modify` | LLM `git_evolution_patch` plus git/file runtime | failure, runtime evidence, git context, workspace manifest, topology summary | `modified` | `git_evolution_patch`, `self_modify`, observation freshness, `effective_goal` |
| `node_satisfied` | mechanical | final state | `halt` | `satisfied`, `last_error`, `effective_goal` |
| `node_error` | mechanical | `last_error`, `last_failure`, current state | `planner`, `reflect`, `halt` | `error_handled`, `recovery`, `last_failure`, `plan_failed`, `effective_goal` |

The old README said patch keys were checked against datasheet writes. That is
not true on this branch. The current check is:

1. Node output must be a `NodeOutput` or `(signal, patch)` tuple.
2. Signal must be non-empty.
3. Patch must be a dict.
4. Signal must be one of the keys in `wiring.topology.edges[current_node]`.
5. LLM records must pass `core_brain._RECORD_RULES` when a rule exists.

If patch-key validation is reintroduced, implement it once in
`core_node_base.call_node` after `output = bus.coerce_node_output(...)` and
before the trace is attached.

## Bus Frame Propagation

`core_bus.NodeOutput.trace(node=...)` is the current bus-frame shape:

```json
{
  "kind": "endgame.node_output.v1",
  "node": "node_execute",
  "signal": "verify",
  "record_type": "execution",
  "patch_keys": ["effective_goal", "last_action", "last_code", "last_error", "last_failure", "last_result"],
  "evidence_keys": ["capabilities", "goal", "last", "observation", "state", "step"],
  "record": {"record_type": "...", "data": {}, "reasoning": "..."},
  "patch": {},
  "evidence": {},
  "emitted_at": 0,
  "effective_goal": "..."
}
```

The trace is stored in:

- `patch["_last_bus_frame"]`
- runtime state after `st.update(patch)`
- `runtime_events.jsonl` under `node_complete.bus_frame`

The old README described full LLM request/response forensics. That remains in
`runtime_events.jsonl` through `core_brain.log_runtime_event`, but the tracked
export helper was removed. The event log is still the complete source of truth.

How to view the live bus without restoring scripts:

```powershell
Get-Content runtime_events.jsonl -Wait -Tail 10
```

How to reintroduce a compact tracked inspector only if it must be tracked:

1. Read `runtime_events.jsonl` line by line.
2. Print only `event`, `node`, `tick`, `signal`, and `next_node`.
3. Do not depend on `networkx`.
4. Keep it outside the LLM prompt surface if possible.

## Goal Narrative Memory

The old README's goal narrative section remains true in shape:

- `state["goal"]` is the root goal for the run.
- `state["effective_goal"]` is rewritten by nodes.
- `bus.state_brief` exposes both `root_goal` and `effective_goal`.
- LLM nodes receive the current effective goal through their payloads.
- Runtime events store state briefs and bus frames that carry the chain.

Current node-specific narrative writes:

| Node | Narrative write |
|------|-----------------|
| `node_planner` | Adds `[PLANNER REWRITE] Current plan focuses on: ... Next: ...` |
| `node_scheduler` | Adds `[SCHEDULER] Current step: ... Complete when: ...` |
| `node_execute` | Adds `[EXECUTE] Action executed: ... Result: ...` |
| `node_verify` | Adds `[VERIFY] Step confirmed...` or `[VERIFY] Step denied...` |
| `node_reflect` | Adds `[REFLECT] Routed to ... Lesson: ... Diagnosis: ...` |
| `node_frame_action` | Adds `[FRAME_ACTION] Focusing on ... via ...` |
| `node_self_modify` | Adds `[SELF_MODIFY] Proposed evolution: ... Patches/Writes/Deletes ...` |
| `node_satisfied` | Adds `[SATISFIED] Goal complete. Final assessment: ...` |
| `node_error` | Adds `[ERROR] ... Routing to ...` or fatal halt text |

The current implementation is intentionally simple string append. It does not
store a separate structured chain. If a structured chain is needed later, add a
single `goal_events` list in state and make nodes append compact event dicts
while still maintaining `effective_goal` for LLM context.

## Observation System

The old README's "RAW -> FILTER -> MAP" model remains correct.

### RAW

Implemented by `core_observation.gather_raw(config, desktop)`:

- Reads `scan.step_px`, `scan.delay_ms`,
  `scan.max_subtree_nodes_per_point`, `scan.max_total_nodes`.
- Uses current screen metrics from `user32.GetSystemMetrics`.
- Optionally uses `scan.area` when `observe_area` injects it.
- Generates probe points with a low-discrepancy pattern.
- Moves the cursor to probe points.
- Uses UIA `ElementFromPointBuildCache` when possible.
- Harvests subtree descendants through `UiaScanner.harvest_subtree`.
- Deduplicates raw nodes by UIA/runtime identity.
- Restores cursor position when possible.

Remaining fallbacks inside RAW:

- If cached bounding rect fails, current bounding rect is tried.
- If `ElementFromPointBuildCache` fails, plain `ElementFromPoint` is tried.
- COM/UIA property and pattern reads swallow some per-element failures.

Those fallbacks remain because UIA is noisy. They are not security guardrails.
If strict UIA failure behavior is desired later, remove the inner `try/except`
fallbacks in `core_observation.py` and expect more observation crashes.

### FILTER

Implemented by `core_observation.filter_raw(...)`:

- Removes offscreen and junk-role nodes.
- Ranks nodes with names/text first.
- Keeps at most `filter.max_elements`.
- Enforces `filter.require_interactive`.
- Enforces `filter.max_per_window`.
- Truncates text hints to `filter.max_text`.
- Builds `action_elements`, `text_hints`, `hwnd_to_z`, and counts.

The old config duplication around depth and property IDs was removed. The
filter surface in `wiring.json` now contains only keys directly consumed by the
default config.

### MAP

Implemented by `core_observation.build_tree_and_map(...)`:

- Finds window raw nodes.
- Sorts windows by z-order.
- Creates root `W0`.
- Creates window short IDs `W1`, `W2`, ...
- Places action elements under windows by point containment.
- Assigns child short IDs such as `W1E1`.
- Builds `node_index`, `action_index`, and `desktop_tree_text`.
- Limits LLM tree rendering by `max_llm_nodes`.

The old README said the runtime keeps full IDs while LLM sees `W1E1`. Current
truth:

- `desktop_tree_text` uses short IDs.
- `action_index` is keyed by short IDs.
- Each action entry still includes `runtime_id`, `hwnd`, `rect`, and other raw
  execution data.
- `node_index` is also keyed by short IDs.

The raw UIA ID string still exists in intermediate raw nodes, but the LLM and
execute helpers operate on short IDs.

## Self-Evolution

The old README described git-backed self-evolution. That remains true, with a
smaller and more direct contract.

Current `node_self_modify.py` builds the LLM payload from:

- `goal`
- `step`
- `failure`
- `runtime` state evidence
- `context_mode`
- `github_branch_url`
- `local_repo_root`
- `observation`
- `git_context`
- `workspace_manifest`
- `organism_contract`
- optional `fresh_observation`

`workspace_manifest` includes tracked and untracked files except runtime
prefixes and marks size/status/binary. This replaced the older broad narrative
around what the model might read.

Current `nodes.apply_evolution_patch` supports:

- `wiring_patches`
- `file_writes`
- `file_deletes`
- `commands`

Current `nodes.commit_self_evolution` supports:

- `git add -A -- <changed_files>`
- `git commit -m "Self-modify: ..."`
- known-good ref update
- optional push to remote and known-good ref

What was removed:

- External enable flag.
- Redundant known-good commit seed.
- Defensive folklore around unconsumed paths.
- Extra safety explanation.
- Transport and forensics code not consumed by selected wiring.

Why this is still unsafe-by-design:

- Self-modify can write Python.
- Self-modify can write JSON.
- Self-modify can delete files.
- Self-modify can run commands.
- Execute can run arbitrary Python.
- The system relies on git evidence and known-good recovery, not a sandbox.

## Phase History Reinterpreted

The main README listed Phase 1 through Phase 3. Those historical commits remain
the background, but this branch adds a Phase 4 reduction pass.

| Phase | Main README status | Current branch truth |
|-------|--------------------|----------------------|
| Phase 1: Observation Refresh | Complete | Still preserved. `node_observe` writes fresh observation and observe is routed before execute after scheduler/frame/retry. |
| Phase 2: Goal Narrative Memory | Complete | Still preserved through `effective_goal` patch writes. |
| Phase 3: Self-Evolving Topology + Verification | Complete | Still preserved. Self-modify can patch wiring/code and commit. Verification remains LLM record `verification`. |
| Appendix A: Token Reduction | Future plan | Implemented substantially by the four token-reduction commits. |
| Appendix B: Fractal Topology | Vision | Not implemented. Routing is still one-to-one. |
| Appendix C: Missing plans | Deferred | Still mostly deferred, but insertion points are clearer after deletion. |

## What Works Now

The following claims are traced to current code:

- Dynamic topology start is loaded from `wiring["topology"]["cycle_start"]`.
- `node_*.py` modules are imported by name through `core_node_base._load_node`.
- The selected brain transport is imported by name through
  `core_brain._load_transport_module`.
- `transport_xai.call` sends requests to xAI Responses API using `urllib`.
- Runtime events are appended as NDJSON through `core_brain.log_runtime_event`.
- `node_observe` writes fresh UIA observation data.
- Brain calls fail if no fresh observation exists before an LLM node.
- Execute runs `exec(code, ns)` with local process/file/module access.
- `observe_area` and `observe_with_config` exist in execute runtime.
- `effective_goal` is propagated and extended by nodes.
- Reflect can route task failures to frame/retry/replan.
- Reflect can route contract failures toward self-modify.
- `node_self_modify` can emit a `git_evolution_patch`.
- `core_organism.run` applies and commits that patch when current node is
  `node_self_modify`.
- Hot-swap can checkout known-good versions of touched paths on failure.
- Control file pause/step/run still exists through `runtime_control.json`.
- Stop file still exists through `runtime_stop.json`.

## What Is Not Proven Or Not Present

The following should not be claimed as working on this branch without a fresh
runtime run:

- Browser SPA DOM reliability on Grok/LinkedIn.
- Authenticated browser profile reuse.
- Multi-monitor observation.
- Parallel node execution.
- Barrier joins.
- Recursive child organisms.
- Local LM Studio transport.
- opencode transport.
- file-proxy handoff transport.
- Playwright/browser DOM transport.
- Event-log compaction.
- Visual forensics UI.
- Full JSON Schema validation.
- Full patch-write whitelist by node.

## Quick Start

The current branch has no tracked `requirements.txt`. The code imports Windows
and Python dependencies directly:

- Windows 11 or compatible Windows UIA environment.
- Python 3.10+ is expected by type syntax.
- `comtypes` must be installed in the Python environment.
- `XAI_API_KEY` must be available in the environment unless
  `wiring.model.transport_config.transport_xai.api_key` is supplied locally.

Run a fresh cycle:

```powershell
python core_organism.py "Test: open notepad and write hello" --reset --duration-seconds 10 --start-node node_observe
```

Resume a previous cycle:

```powershell
python core_organism.py "Continue the current goal" --duration-seconds 300
```

Use a brain-call budget:

```powershell
python core_organism.py "Inspect the current desktop and report next action" --reset --duration-seconds 120 --brain-call-budget 3
```

Use a different wiring file:

```powershell
python core_organism.py "Run with alternate wiring" --reset --wiring wiring.json
```

External runtime control:

```powershell
# runtime_control.json is created from wiring.control_default when missing.
# mode can be run, pause, or step.
Get-Content runtime_control.json
```

Stop a run:

```powershell
Set-Content runtime_stop.json '{"reason":"manual stop"}'
```

The old README's self-evolution enable step is obsolete on this branch:

```powershell
# Old main README step. Do not use as branch truth:
# New-Item runtime_self_evolution_enabled.json -ItemType File -Force
```

There is no current code that reads `runtime_self_evolution_enabled.json`.

## Current Files

| File | Current purpose |
|------|-----------------|
| `.gitattributes` | Text/eol normalization for tracked source |
| `.gitignore` | Whitelist tracked prompt-surface files; ignores runtime artifacts |
| `README.md` | This large handover document; should be excluded from future runtime prompt ingestion |
| `wiring.json` | Single source for selected transport, topology, prompts, observe config, paths, control defaults, self-modify config |
| `core_organism.py` | Main loop, resume/reset, node dispatch, topology routing, self-modify application, error reroute |
| `core_wiring.py` | Wiring load/save/path helpers, required-key validation, runtime state/control path helpers |
| `core_bus.py` | Record and NodeOutput types, signal validation, state/observation briefs, failure streak |
| `core_brain.py` | Stable prefix option, brain request logging, transport loader, structured record validation, xAI call orchestration |
| `core_node_base.py` | Base LLM node behavior and dynamic node loader |
| `core_nodes.py` | Self-evolution file/git helpers and execute capability runtime |
| `core_observation.py` | UIA RAW -> FILTER -> MAP scanner |
| `core_desktop.py` | Desktop singleton, UIA automation object, Win32 click/type/key/scroll/open_url helpers |
| `core_state.py` | Runtime event wrapper, deadline/stop/pause/step handling, exception classification |
| `core_stop_check.py` | Runtime stop file and PID file helpers |
| `node_planner.py` | LLM plan node |
| `node_scheduler.py` | Mechanical plan step selector |
| `node_observe.py` | Mechanical UIA observe node |
| `node_execute.py` | LLM execution node and raw `exec` runner |
| `node_verify.py` | LLM verification node |
| `node_reflect.py` | LLM reflection and recovery router |
| `node_frame_action.py` | LLM framing node |
| `node_self_modify.py` | LLM git evolution proposal node |
| `node_satisfied.py` | Mechanical halt node |
| `node_error.py` | Mechanical error recovery node |
| `transport_xai.py` | Only tracked selected brain transport |

## Removed Files And How To Reintroduce Them

### `transport_file_proxy.py`

What it did on main:

- Wrote a JSON request to `runtime_request.json`.
- Deleted any previous `runtime_response.json`.
- Polled for a JSON response file.
- Expected the response to be a direct bus record with `record_type`, `data`,
  and optional `reasoning`.

Why it was removed:

- It was not selected by current `wiring.json`.
- It duplicated message logging that `core_brain` already performs.
- It added request/response path config that the current transport system does
  not need.
- It kept a second human-in-the-loop execution path in the tracked prompt
  surface.

How to reintroduce it compactly:

1. Add `transport_file_proxy.py` with one function:
   `call(messages, cfg) -> {"content": json_string, "reasoning": str}`.
2. Reuse `core_brain.summarize_messages_for_log(messages)` instead of copying
   `_sha256_text`, `_dynamic_payload`, and `_logged_messages`.
3. Add only this config under `wiring.model.transport_config`:
   `request_path`, `response_path`, `poll_interval`, `timeout`.
4. Set `wiring.model.transport` to `"transport_file_proxy"` when intentionally
   using it.
5. Do not add automatic fallback from xAI to file proxy.

Small modern shape:

```python
def call(messages, cfg):
    request = {
        "schema": "endgame-ai.file-proxy.request.v2",
        "messages": core_brain.summarize_messages_for_log(messages),
        "expected_record_type": cfg.get("expected_record_type"),
        "response_format": cfg.get("response_format"),
    }
    # write request, poll response, return {"content": json.dumps(record), "reasoning": ...}
```

No core loader change is required because `core_brain._load_transport_module`
already imports selected transport modules by name.

### `transport_openai.py`

What it did on main:

- Called an OpenAI-compatible `/v1/chat/completions` endpoint.
- Defaulted to `http://localhost:1234`, which fits LM Studio.
- Sent `response_format` when provided.
- Parsed `choices[0].message.content`.

Why it was removed:

- Current selected transport is xAI Responses API.
- The local server config was unselected recurring prompt material.
- It created operator confusion around fallback behavior.

How to reintroduce it compactly:

1. Restore a `transport_openai.py` with `call(messages, cfg)`.
2. Keep only `base_url`, `path`, `model`, `temperature`, `timeout`,
   `max_output_tokens`, and optional `api_key`.
3. Convert current `_record_response_format` into OpenAI-compatible
   `response_format` inside the transport.
4. Add config under `wiring.model.transport_config.transport_openai`.
5. Select it explicitly with `wiring.model.transport = "transport_openai"`.

No changes are needed in `core_brain`, `core_node_base`, or node files.

### `transport_opencode.py`

What it did on main:

- Resolved an `opencode` executable.
- Flattened system/user/assistant messages into a prompt string.
- Ran `opencode run -m <model> --format json <prompt>`.
- Parsed line-delimited JSON-ish output and returned content.

Why it was removed:

- It was not selected.
- It depended on an external CLI not represented in the runtime contract.
- It duplicated message flattening that only that transport needed.

How to reintroduce it compactly:

1. Add `transport_opencode.py` with `_resolve_executable` and `call`.
2. Keep executable resolution local to the transport.
3. Keep message flattening local to the transport.
4. Add only `executable`, `model`, `extra_args`, and `timeout` to wiring.
5. Select it explicitly.

If opencode MCP or skills become the real integration path, do not restore this
transport. Instead add a small execute helper in `build_capability_runtime` that
invokes the desired CLI for a specific task.

### `transport_browser_ai.py`

What it did on main:

- Nothing useful at runtime. It raised a fail-hard stub saying browser AI was
  documented but unimplemented.

Why it was removed:

- A tracked fail-hard stub is pure prompt cost.
- The old README already marked Browser AI as future work.

How to reintroduce browser capability properly:

Choose one of two designs.

Design A, browser as LLM transport:

1. Add `transport_browser_ai.py`.
2. Implement `call(messages, cfg)` using a browser-side model or local browser
   automation that returns a bus record.
3. Select it in `wiring.model.transport`.

Design B, browser as execute/observe capability:

1. Keep `transport_xai` as the LLM.
2. Add Playwright or CDP helpers to `core_nodes.build_capability_runtime`.
3. Add helpers such as `browser_dom_snapshot`, `browser_click_selector`, and
   `browser_type_selector`.
4. Let `node_execute` choose DOM helpers when UIA cannot see SPA internals.

Design B is probably smaller for Grok/LinkedIn because it reuses the existing
LLM transport and adds browser control only where needed.

### `export_brain_forensics.py`

What it did on main:

- Parsed `runtime_events.jsonl` or xAI console JSONL.
- Paired brain requests and responses.
- Expanded embedded JSON strings.
- Wrote `phaseN.md` files.

Why it was removed:

- It was 400+ lines of operator tooling in the self-evolution prompt surface.
- It wrote markdown docs, which are not runtime organism behavior.
- Runtime events already preserve request/response content.

How to reintroduce it without hurting runtime prompt size:

1. Keep it untracked or outside the prompt whitelist.
2. Parse `runtime_events.jsonl`.
3. Pair rows by `seq`.
4. Render files outside tracked source.

If it must be tracked, implement the minimum:

```python
for row in jsonl:
    if row["event"] == "brain_request": requests[row["seq"]] = row
    if row["event"] == "brain_response": responses[row["seq"]] = row
```

Then print JSON to stdout instead of writing phase files.

### `analyze_graph.py`

What it did on main:

- Imported `networkx`.
- Read `runtime_events.jsonl`.
- Built a graph from node start/complete events.
- Printed edges and cycles.

Why it was removed:

- It added an untracked dependency assumption.
- The current topology is already explicit in `wiring.json`.
- Runtime call-flow graphing is for humans, not organism execution.

How to reintroduce compactly:

1. Avoid `networkx`.
2. Parse `runtime_events.jsonl`.
3. Print unique `(last_node, node)` transitions.
4. If cycle detection is needed, derive it from `wiring.topology.edges` with a
   tiny DFS.

### `check_events.py`

What it did on main:

- Printed selected runtime event fields from `runtime_events.jsonl`.

Why it was removed:

- It was a short script, but still not runtime behavior.
- Equivalent PowerShell one-liners can inspect events.

How to reintroduce compactly:

Use an untracked command or a short external helper. If tracked, keep it under
30 lines and read only fields that current events actually contain.

### Old `.gitignore` Whitelist Entries

Old `.gitignore` allowed the deleted transports and utility scripts. Current
`.gitignore` no longer whitelists them, so newly recreated versions will be
ignored unless the whitelist is updated.

If reintroducing a file as tracked source:

1. Add the file.
2. Add `!filename.py` to `.gitignore`.
3. Confirm `git status --short` shows the file.

If reintroducing a file as an operator-only tool:

1. Put it outside the repository or leave it ignored.
2. Do not whitelist it.

## Removed Runtime Concepts And Reintroduction Notes

### External Self-Evolution Enable Flag

Removed item:

- `runtime_self_evolution_enabled.json`
- `core_stop_check.self_evolution_enabled()`

Reason:

- It added a safety gate contrary to the current unsafe-by-design contract.
- It added README/runbook complexity.
- It made self-modify behavior depend on an untracked flag that was not part of
  topology.

Reintroduce only if desired:

- Add one check in `core_organism.run` before patch application.
- Keep the check mechanical and fail-hard.
- Do not add a broad safety framework.

### Execute Firmware/Git Preflight

Removed item:

- Extra preflight logic that blocked or classified certain execute code before
  `exec`.

Reason:

- Execute is intentionally unconstrained.
- The branch goal was shrink/unify, not protect.

Reintroduce only if the organism contract changes:

- Add a single `validate_execute_code(code, state)` in `node_execute.py`.
- Call it immediately before `exec(code, ns)`.
- Keep policy text out of prompts unless the LLM must know it.

### Datasheets

Removed item:

- Per-node datasheet metadata.
- Datasheet-driven write restrictions.
- Repeated descriptions of node inputs/outputs in source.

Reason:

- The same contract existed in code, prompts, topology, and docs.
- Datasheets were high-duplication prompt material.

Reintroduction path:

- Add a compact `contracts` section to `wiring.json`.
- Generate any human docs from `contracts`, not separate per-node constants.
- Enforce in `core_node_base.call_node`.

### Mermaid Runtime Helpers

Removed item:

- Runtime Mermaid generation helper described by main README.

Reason:

- Diagrams are derived from `wiring.json`.
- They are documentation, not runtime behavior.

Reintroduction path:

- External tool:
  `for node, edges in wiring["topology"]["edges"].items(): print(...)`.
- Keep generated diagrams outside tracked source.

### Local Multi-Transport Config

Removed item:

- OpenAI, opencode, file-proxy, browser-ai config blocks.

Reason:

- Only selected xAI transport was consumed.
- Unselected config blocks made every topology patch prompt pay for unused
  behavior.

Reintroduction path:

- Add exactly one transport config when selecting that transport.
- Do not keep inactive transport configs in `wiring.json`.

### Redundant Observation Config

Removed item:

- UIA property ID lists in wiring.
- UIA pattern ID lists in wiring.
- Depth config block.
- Separate accessor functions.

Reason:

- Python constants already define the UIA scanner.
- Optional depth keys are read from filter only when present.
- Wiring should contain knobs that are actually operator-chosen.

Reintroduction path:

- Add only consumed keys.
- Validate in `core_wiring`.
- Read in `core_observation` from one place.

### Event Log Rotation

Removed/not implemented item:

- `runtime_events.jsonl` compaction or rotation.

Reason:

- It was not necessary to preserve behavior and would add runtime policy.

Compact future path:

1. Add `paths.event_log_max_bytes` or `runtime.event_log.max_bytes` to wiring.
2. In `core_brain.append_ndjson`, before append, rotate if file size exceeds
   the threshold.
3. Keep latest events and optionally write a summary outside prompt surface.

### Stable Prefix

Not removed:

- `core_brain.StablePrefix` still exists.

Current truth:

- `wiring.model.stable_prefix.enabled` is false.
- `include_in_request` is false.
- If enabled, `StablePrefix` includes tracked `.py`, `.json`, `.md`,
  `.gitattributes`, `.gitignore`, and `LICENSE`, while skipping `.git`,
  `__pycache__`, `.pytest_cache`, and names starting `runtime_`.

Important README consequence:

- If stable prefix is enabled while README is tracked and included, this large
  README will become prompt material. Exclude README before enabling stable
  prefix for runtime use.

Compact exclusion path:

1. Remove `.md` from `STATIC_PREFIX_SUFFIXES`, or
2. Add `README.md` to a skip-name set, or
3. Move long docs outside tracked prompt source.

## Current `wiring.json`

`wiring.json` is one minified JSON line. That is intentional.

Why minified:

- It reduces tracked character count.
- It keeps the topology/prompt/config SSOT compact.
- It avoids duplicate comments or formatting.

What it contains:

- `schema`: `endgame-ai.wiring.v2`
- `model.transport`: `transport_xai`
- `model.transport_config.transport_xai`
- `model.global`
- `model.stable_prefix`
- `model.organs`
- `paths`
- `control_default`
- `observe_config.hover_cache`
- `self_modify`
- `topology`
- `prompts`

Current prompts were rewritten from zero during reduction. They are short
contracts, not append-only edits from old prompts:

| Prompt key | Current contract summary |
|------------|--------------------------|
| `node_planner` | Emit plan JSON with `step_ready` or `reflect` and complete remaining root-goal steps |
| `node_scheduler` | Mechanical selector, carry `effective_goal` |
| `node_observe` | Mechanical UIA scan writer |
| `node_frame_action` | Emit framing target/strategy/risk/notes |
| `node_execute` | Emit `EXECUTE` with code or empty `FRAME`/`CANNOT` |
| `node_verify` | Confirm or deny step using real evidence |
| `node_reflect` | Route failure or self-modify |
| `node_self_modify` | Emit git evolution patch fields |
| `node_satisfied` | Mechanical halt when complete and no error |
| `node_error` | Mechanical recovery |

If a prompt needs expansion later:

- Rewrite the relevant prompt from zero.
- Keep it aligned with current code and `_RECORD_RULES`.
- Do not paste old main prompt text back in.
- Do not describe removed transports or guards as current behavior.

## Architecture Deep Dive

### `core_organism.py`

Responsibilities:

- Parse run options.
- Register/unregister PID.
- Load wiring.
- Reset or resume runtime state.
- Enforce duration and stop-file checks.
- Wait for control mode before each node.
- Write `runtime_state.json`.
- Log lifecycle and node events.
- Dispatch dynamic nodes.
- Apply self-modify patches.
- Route signals.
- Re-enter the loop through `run(...)` after routable errors.

Removed compared with main:

- Extra stop/evolution flag paths.
- Some defensive branching.
- Larger context relay structures.

Current remaining fallbacks:

- Resume chooses state `next_node`, topology `cycle_start`, or default strings
  if older state is missing fields.
- Error handling attempts topology `error` route and recursively continues.
- These are compatibility/recovery paths, not security guards.

### `core_wiring.py`

Responsibilities:

- Resolve `${ROOT}` and `${HOME}` in paths.
- Load JSON.
- Validate required wiring keys.
- Write JSON atomically.
- Provide state/control/event paths.
- Create default control file when missing.
- Reset runtime state/control.
- Return topology summary.

Removed compared with main:

- Mermaid helper.
- Extra config accessors.
- Extra known-good seed helpers.

Current gap:

- Validation is required-key validation, not full strict schema.

### `core_bus.py`

Responsibilities:

- `Record`
- `NodeOutput`
- `emit`
- `coerce_node_output`
- `allowed_signals`
- `validate_signal`
- `state_brief`
- `observation_brief`
- failure signature and streak update

Removed compared with main:

- Datasheet write enforcement.
- Some redundant observation brief paths.

Current remaining compatibility:

- `Record.from_json` uses defaults if keys are missing, but brain record
  validation catches expected LLM record shapes.
- `state_brief` still supports `observation_artifact` fallback if
  `fresh_observation` is absent.

### `core_brain.py`

Responsibilities:

- Stable prefix construction if enabled.
- Message assembly.
- Fresh observation enforcement.
- Runtime event logging.
- Brain call budget.
- Dynamic transport loading.
- Structured output request format.
- Record extraction from content.
- Record validation.
- One-pass or two-pass reasoning pattern support.

Removed compared with main:

- Multiple transport modules from tracked source.
- Transport fallback logic.
- Larger schema/text duplication.

Current selected transport:

- `transport_xai`

Current important fail-hard behavior:

- If selected transport module is missing, fail.
- If `XAI_API_KEY` is missing, fail.
- If no fresh observation exists before an LLM call, fail.
- If brain output is not a valid expected record, fail.

### `core_node_base.py`

Responsibilities:

- Shared LLM node payload/evidence defaults.
- Prompt lookup.
- `brain.think` invocation.
- Record type check.
- Dynamic node module loading.
- Signal validation and bus-frame trace attachment.

Removed compared with main:

- Some old base methods and datasheet integrations.

### `core_nodes.py`

Responsibilities:

- Self-evolution target validation.
- Atomic file writes.
- Wiring patch application.
- Git helpers.
- Known-good ref resolution/update.
- Hot-swap checkout.
- Self-evolution preparation.
- Evolution command execution.
- Rollback snapshots.
- Commit/push self-evolution.
- Execute capability manifest.
- Execute namespace construction.

This file is still large because it owns two heavy surfaces:

1. self-modify file/git mechanics
2. execute runtime helpers

Future reduction path:

- Split is not automatically better because every tracked file is prompt
  surface.
- Prefer deleting duplicate helpers or moving operator-only code out of tracked
  source.
- If splitting, split by runtime load path only when dynamic import prevents
  unused code from entering the actual prompt prefix.

### `core_observation.py`

Responsibilities:

- UIA module loading.
- UIA constants.
- Role/action classification.
- Window z-order.
- Safe-ish value conversion from COM values.
- Cache request creation.
- Raw element conversion.
- Subtree harvest.
- Probe-grid scan.
- Filtering.
- Tree/map rendering.
- Observation artifact assembly.

Removed compared with main:

- Wiring-exposed property/pattern ID lists.
- Some layered observation helper functions.
- Extra config knobs.

Current remaining broad exception handling:

- UIA per-element reads.
- Pattern text extraction.
- subtree/hit point fallbacks.

Reason:

- UIA automation frequently fails per element. Crashing the whole scan on a
  single bad COM property would reduce organism usability.

### `core_desktop.py`

Responsibilities:

- Desktop singleton.
- UIA automation object.
- `observe`.
- Win32 click/type/key/hotkey/scroll/open_url.

Removed compared with main:

- `get_window_tokens` style diagnostic helpers.
- Extra browser fallback layers.

Reintroduce window token diagnostics:

- Prefer an untracked diagnostic script that calls `core_desktop.observe`.
- If runtime needs it, add a helper in `build_capability_runtime` that reads
  `desktop_tree_text` instead of scanning twice.

### `core_state.py`

Responsibilities:

- Duration expiry.
- Stop-file detection.
- Runtime event wrapper.
- Exception classification.
- Pause/step/run control before nodes.

Removed compared with main:

- Additional stop/evolution flag helpers.
- PID wait/kill helpers.

Reintroduce kill/wait helpers:

- Keep them outside tracked runtime if they are operator controls.
- If runtime needs them, put compact functions in `core_stop_check.py`.

### `core_stop_check.py`

Responsibilities:

- Runtime stop file.
- PID file write/delete.
- Stop check.
- Stop request.
- Stop clear.

Removed compared with main:

- Self-evolution enabled flag reader.
- PID registry management beyond current process helper.
- Wait/kill convenience functions.

## Node Deep Dive

### `node_planner.py`

Current behavior:

- Builds payload from root goal, state brief, fresh observation, previous plan,
  root plan intent, completed steps, last reflection.
- Requires `data.intent` to be a non-empty list when `step_ready`.
- Requires every step to include string `description` and `done_when`.
- Preserves root plan obligations during replans.
- Writes complete remaining plan and `effective_goal`.

Removed compared with main:

- Long prompt protocol.
- Extra schema duplication.

### `node_scheduler.py`

Current behavior:

- Reads `plan.intent`.
- Uses `state.step`.
- Emits `plan_complete` only when all plan steps and root obligations are done.
- Emits next `current_step` and appends scheduler text to `effective_goal`.

Removed compared with main:

- LLM involvement. It is mechanical.

### `node_observe.py`

Current behavior:

- Runs UIA observe with `wiring.observe_config`.
- Writes full observation patch.
- Emits `initial_screen` before plan, `screen_ready` after plan.

Removed compared with main:

- No extra prompt or datasheet.

### `node_execute.py`

Current behavior:

- LLM emits `execution` record.
- Valid conclusion/signal pairs:
  - `EXECUTE` -> `verify`
  - `FRAME` -> `frame`
  - `CANNOT` -> `frame` or `reflect`
- `CANNOT` may be routed to frame if framing has not yet been attempted.
- Executes code with raw `exec`.
- Captures stdout, stderr, result, and action events.
- Routes errors to reflect.

Removed compared with main:

- Firmware/git preflight guard behavior.
- Extra action wrappers.
- Defensive code policy.

### `node_verify.py`

Current behavior:

- LLM emits `verification` record.
- Signal and boolean success must match.
- On success, increments step and appends completed step evidence.
- On denial, leaves step unchanged and updates failure evidence.

Possible future addition:

- A second LLM-as-judge can be added by having verify call `brain.think` twice
  or by adding `node_verify_judge`. That is not present now.

### `node_reflect.py`

Current behavior:

- Builds failure evidence.
- Updates failure streak.
- Lets LLM request a recovery signal.
- Mechanically overrides bad recovery choices:
  - task-route failures tend to frame/retry/replan
  - contract failures escalate after repeated streaks
  - non-contract escalations are rerouted to task recovery
- Can carry `topology_patch` in state if LLM emits one.

Removed compared with main:

- Longer reflection prompt and redundant routing middleware.

### `node_frame_action.py`

Current behavior:

- LLM emits `action_frame`.
- Writes target/strategy/risk/notes plus step index.
- Routes to observe for a fresh scan.

### `node_self_modify.py`

Current behavior:

- Captures git context and workspace manifest.
- Sends organism contract, topology summary, runtime evidence, failure context,
  and observation to LLM.
- Expects `git_evolution_patch`.
- Returns `modified` with patch data.

Important:

- `node_self_modify.py` does not itself apply the patch.
- `core_organism.run` applies the patch after the node returns.

### `node_satisfied.py`

Current behavior:

- Emits halt.
- Marks `satisfied` true only if no `plan_failed` and no `last_error`.

### `node_error.py`

Current behavior:

- Prints an error line.
- Halts if there is no observation data and the failure source means planning
  cannot proceed.
- Otherwise routes to reflect if a current step exists, planner otherwise.

## Transport Deep Dive

### `transport_xai.py`

Current behavior:

- Reads API key from `XAI_API_KEY` or `cfg["api_key"]`.
- Builds xAI Responses API payload.
- Supports:
  - `model`
  - `temperature`
  - `truncation`
  - `prompt_cache_key`
  - `store`
  - `metadata`
  - `max_output_tokens`
  - `include`
  - structured output `text.format`
  - reasoning effort
  - web search tool filters
- Calls `urllib.request.urlopen`.
- Parses `output_text` or `output` content parts.
- Returns `content`, `reasoning`, `usage`, and raw body.

Why only xAI remains:

- It is selected in current `wiring.json`.
- The organism should fail hard if selected model access is missing.
- Other transports can be restored one at a time when selected.

## Observability

Current observability sources:

- `runtime_state.json`
- `runtime_events.jsonl`
- `runtime_control.json`
- `runtime_stop.json`
- `runtime_organism.pid`
- `runtime_known_good_commit.json`

Only source files are tracked. Runtime artifacts are ignored by `.gitignore`.

Runtime event types currently emitted include:

- `organism_start`
- `organism_resume`
- `node_start`
- `node_complete`
- `brain_request`
- `brain_response`
- `brain_error`
- `self_modify_applied`
- `self_modify_hot_swap`
- `duration_expired`
- `stop_file_detected`
- `step_consumed`
- `paused_before_node`
- `halted`
- `interrupted`
- `error`

The old README's export-to-markdown forensics flow was removed. The data is
still present; only the renderer was removed.

## Missing And Deferred Plans

This section reinterprets the main README Appendix C.

| Feature | Current status | Why not in this refactor | Compact implementation path |
|---------|----------------|--------------------------|-----------------------------|
| Meta-orchestrator `node_meta` | Not present | Adds a new node and behavior, not a reduction | Add `node_meta.py`, a topology edge from reflect or scheduler, and a compact prompt that emits topology health recommendations |
| Browser AI / Playwright DOM | Not present | Old file was only a stub; real DOM support needs design | Prefer execute helpers in `build_capability_runtime` over a new LLM transport unless browser itself is the model |
| Multi-monitor observe | Not present | Current scan uses primary screen metrics | Add monitor enumeration in `core_observation.gather_raw`; let `observe_area` accept monitor IDs or absolute rects |
| Event log compaction | Not present | Not needed to preserve behavior | Add rotation in `core_brain.append_ndjson` or `log_runtime_event` |
| Distributed goal sync | Not present | Requires new state consensus semantics | Add a new sync node or external shared file/Redis helper; keep `effective_goal` as the payload |
| Visual forensics UI | Not present | Operator UI, not organism runtime | Build as excluded external tool reading `runtime_events.jsonl` |
| Skill/plugin system | Not present | No native skill runtime in current code | Add execute helper or transport integration only when a real workflow needs it |
| MCP server integration | Not present | No current MCP abstraction in organism | Treat MCP as an execute helper layer or a transport, not both |
| Voice control | Not present | Outside current desktop organism loop | Add a node or external goal injector that writes runtime goal/control |
| Mobile companion | Not present | Separate app/sync problem | Sync through git or a file protocol outside core loop |
| Second-opinion LLM judge | Not present | Verify already uses one LLM record | Add optional second call inside `node_verify` or a separate `node_verify_judge` |
| Cross-platform UI | Not present | Current code is Windows UIA and Win32 | Abstract `core_desktop` behind platform modules; do not duplicate node logic |
| Formal verification | Not present | Documentation/modeling, not runtime reduction | Model `wiring.topology.edges`, signals, and state patch keys externally |
| Neural topology | Not present | Requires learned router and metrics | Add router node or edge weights in wiring after one-to-many support exists |

## Fractal Topology Vision Reinterpreted

The main README's fractal topology section is still a vision, not current code.

Current fixed properties:

- One emitted signal routes to one next node string.
- One current node runs at a time.
- There is one runtime state file.
- There is one effective goal chain.
- There is no child-organism primitive.
- There is no barrier join.

The organism can still spawn processes through `exec` because `subprocess` is in
the namespace. That means a model could manually run another
`python core_organism.py ...` command today. What is missing is a first-class
contract to collect the child result and merge it back into parent state.

Compact `spawn_organism` reintroduction path:

1. Add this helper inside `core_nodes.build_capability_runtime`:

```python
def spawn_organism(goal: str, duration: int = 60) -> dict:
    cp = subprocess.run(
        [sys.executable, "core_organism.py", goal, "--reset", "--duration-seconds", str(duration)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=duration + 30,
    )
    child_state = brain.load_json(ROOT / "runtime_state.json")
    return {"returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr, "effective_goal": child_state.get("effective_goal", "")}
```

2. Then fix the state collision problem. The sketch above reuses
   `runtime_state.json`, so it is not safe for concurrent parent/child runs.
3. Add child-specific path overrides through a temporary wiring copy or a
   `--wiring` file with unique `paths.state`, `paths.control`, and
   `paths.event_log`.
4. Add merge semantics in parent execute/verify/reflect.

Compact one-to-many topology path:

1. Allow edge values to be lists.
2. Change runtime state to hold pending branches.
3. Add `node_barrier.py`.
4. Let scheduler emit branch tasks.
5. Let barrier join results and route to reflect or scheduler.

Do not copy node files for `node_execute_browser`, `node_execute_editor`, and
`node_execute_terminal`. Use the same `node_execute.py` with instance metadata
in wiring if parallel roles are added.

## Known Issues

Current known issues from code and main README reinterpretation:

| Issue | Current impact | Current workaround | Proper compact fix |
|-------|----------------|--------------------|--------------------|
| Browser SPA UIA depth | UIA may not expose Grok/LinkedIn internals well | Use `observe_area` and keyboard/browser shortcuts | Add Playwright/CDP execute helpers |
| Event log growth | `runtime_events.jsonl` grows without rotation | Manually archive/delete untracked runtime log | Rotate in `core_brain.append_ndjson` |
| README prompt bloat | This file is now large | Keep stable prefix disabled | Exclude README from prompt/stable prefix |
| Only xAI transport tracked | Local/offline mode unavailable | Use xAI or reintroduce one selected transport | Add one transport module and config |
| Strict schema incomplete | Some malformed inner wiring values may fail later than load | Keep wiring generated carefully | Tighten `validate_wiring` types |
| No barrier/fan-out | No parallel execution topology | Sequential plan steps | Add list edges and barrier node |
| Runtime state collision for child runs | Manual child organism can overwrite parent runtime files | Do not spawn child without path isolation | Unique wiring paths per child |

## Future Agent Rules For This Branch

1. Treat `wiring.json` as SSOT for topology, prompts, transport selection,
   observation config, paths, control defaults, and self-modify config.
2. Do not restore deleted transports unless selecting one intentionally.
3. Do not add automatic fallback between transports.
4. Do not add safety guardrails unless the operator explicitly changes the
   unsafe-by-design contract.
5. Do not duplicate contracts across code, prompts, and docs.
6. If expanding node prompt text, rewrite the prompt from zero and align it with
   current code.
7. If adding documentation, keep it excluded from runtime prompt material.
8. If adding operator tooling, keep it untracked or outside the whitelist unless
   the organism itself must call it.
9. If adding config, consume it in code and validate it at wiring load.
10. If adding a removed feature back, prefer one compact module/function over
    resurrecting the old file verbatim.

## Exact Reintroduction Checklist By User Request

Use this when a reader spots a removed critical part and wants it back.

### Bring back file-proxy transport

Prompt to future agent:

```text
Reintroduce transport_file_proxy in the reduced architecture. Implement only
call(messages, cfg), reuse core_brain.summarize_messages_for_log, add a compact
transport_file_proxy config under wiring.model.transport_config, and select it
explicitly. Do not add fallback from xAI.
```

Expected touched files:

- `transport_file_proxy.py`
- `.gitignore`
- `wiring.json`

### Bring back local OpenAI/LM Studio transport

Prompt to future agent:

```text
Reintroduce transport_openai as an explicit selected transport. Keep the module
small: base_url, path, model, temperature, timeout, max_output_tokens, optional
api_key, response_format conversion, choices[0].message parsing. Add only the
selected config to wiring.
```

Expected touched files:

- `transport_openai.py`
- `.gitignore`
- `wiring.json`

### Bring back opencode transport

Prompt to future agent:

```text
Reintroduce transport_opencode only if opencode CLI is the selected model path.
Implement executable resolution and call(messages, cfg). Keep message flattening
inside the transport. Add executable/model/extra_args/timeout config only.
```

Expected touched files:

- `transport_opencode.py`
- `.gitignore`
- `wiring.json`

### Add browser DOM capability

Prompt to future agent:

```text
Add Playwright/CDP browser helpers to core_nodes.build_capability_runtime for
SPA tasks. Do not restore the old transport_browser_ai stub. Expose compact
helpers for DOM snapshot, selector click, selector type, and current URL/title.
Update node_execute prompt in wiring from zero to mention these helpers.
```

Expected touched files:

- `core_nodes.py`
- `wiring.json`
- optionally dependency/environment notes outside prompt source

### Add full strict wiring schema

Prompt to future agent:

```text
Tighten core_wiring.validate_wiring so every consumed wiring key has an exact
type. Do not add runtime fallbacks. Keep validation in core_wiring and update
wiring.json to satisfy the stricter contract.
```

Expected touched files:

- `core_wiring.py`
- `wiring.json`

### Add event log compaction

Prompt to future agent:

```text
Add compact runtime_events.jsonl rotation in core_brain.append_ndjson. Configure
max bytes in wiring only if needed. Preserve current event row schema and do not
add markdown export files.
```

Expected touched files:

- `core_brain.py`
- optionally `wiring.json`

### Add datasheet-like patch write validation

Prompt to future agent:

```text
Add compact patch-write validation by introducing wiring.contracts.<node>.writes
and enforcing it once in core_node_base.call_node before _last_bus_frame is
attached. Do not restore per-node datasheet constants.
```

Expected touched files:

- `core_node_base.py`
- `core_wiring.py`
- `wiring.json`

### Add fractal child organism

Prompt to future agent:

```text
Add spawn_organism to core_nodes.build_capability_runtime with isolated child
runtime paths. Use a temporary wiring copy or explicit path override so parent
and child do not share runtime_state.json. Return child effective_goal and
runtime evidence to parent execute.
```

Expected touched files:

- `core_nodes.py`
- possibly `core_organism.py`
- possibly `wiring.json`

### Add one-to-many topology and barrier join

Prompt to future agent:

```text
Extend topology edge values from string to string-or-list, update routing in
core_organism, add a compact mechanical node_barrier, and keep node code shared
instead of duplicating execute/verify files per branch.
```

Expected touched files:

- `core_organism.py`
- `core_bus.py`
- `core_wiring.py`
- `node_barrier.py`
- `.gitignore`
- `wiring.json`

## Final Handover

This branch is no longer the main README's architecture plus a TODO list. It is
the reduced architecture:

- fewer tracked files
- fewer transports
- shorter prompts
- compact wiring
- centralized record rules
- dynamic node imports preserved
- dynamic selected transport import preserved
- UIA observe preserved
- raw execute preserved
- effective goal chain preserved
- git-backed self-modify preserved

The cost of the reduction is that optional surfaces are no longer parked in the
tracked repo. That is the point. Future work should add capabilities only when
they are selected or consumed, and should add them in the smallest place that
matches the current call graph.
