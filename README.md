# endgame-ai

`endgame-ai` is a task-agnostic autonomous organism for a real Windows 11 desktop. UI Automation supplies the eyes and hands; a wheel of dynamically loaded nodes carries one growing goal-narrative through planning, acting, verification, reflection, self-modification, recursion, and deliberate rest.

This repository contains the source, Git history, final state, runtime event log, model-provider request log, and per-phase forensic exports from the **2026-07-10 run**. That run proved liveness but not task completion. The code has since been corrected from the evidence. A fresh Windows run is still required to prove that the corrections produce sustained task progress.

## Status at a glance

| Claim | Status | Evidence |
|---|---|---|
| The wheel stayed alive for about ten minutes | Proven | `runtime_events.jsonl`, `runtime_state.json` |
| The provider and runtime logs describe 207 model calls | Proven | Both JSONL logs |
| The run completed its desktop task | False | No step was verified; only six actions ran |
| Most model-selected execute turns acted | False | 6 acted; 12 returned `FRAME` or `CANNOT` |
| 48 model-selected execute turns were empty | False | 36 of those 48 were intentionally idle fan-out branches |
| Planner refusal was a major loop source | Proven | 60 `reflect` results from 66 planner calls |
| Reflection could freely escalate or rest | False in the old code | 59 requested `give_up` choices were rewritten to `replan` by Python |
| The corrected code forbids planner and executor no-op exits | Proven statically and by contract replay | Commit `6fb1ab3`; validation commands below |
| The corrected code progresses on Windows | Not yet proven | Requires a new live run |

The complete evidence and derivations are in [`FORENSIC_AUDIT.md`](FORENSIC_AUDIT.md). Every statement unit from the previous README is tracked in [`README_SENTENCE_AUDIT.md`](README_SENTENCE_AUDIT.md).

## The wheel

The topology lives in `wiring.json`, not in a Python registry.

```text
node_guidance -> node_observe -> node_planner -> node_scheduler
      ^                                              |
      |                                              v
node_frame_action <- node_reflect <- node_verify <- node_barrier
      ^                                              ^
      |                                              |
      +---- node_dispatch -> browser/editor/terminal-+

node_reflect -> node_self_modify -> node_planner
node_reflect -> node_spawn -> node_reflect
node_reflect -> node_satisfied -> halt
errors -> node_error -> planner/reflect/guidance
```

Every node emits exactly `(signal, patch)`. The bus validates the signal against the edge for that exact node instance, applies the patch to the one persisted state dictionary, increments the tick, and routes the next frontier. Fan-out wakes the execute faculties; the barrier waits for all branches, including intentionally idle branches, before verification.

## What the 2026-07-10 run actually did

The provider log contains 207 requests for `grok-4.3`. The runtime log contains 207 matching `brain_request` and 207 `brain_response` events, 305 completed ticks, and one `duration_expired` event. Provider timestamps span `2026-07-10T06:23:54.685991Z` through `2026-07-10T06:33:52.702106Z`. Summed provider usage is 1,736,111 prompt tokens, 35,060 completion tokens, 441,088 cached prompt tokens, and `$0.179464635`.

The progress failure had three linked causes:

1. **Planner refusal:** 60 of 66 planner records selected `reflect`; only six produced a plan.
2. **Woken faculty refusal:** dispatch woke one faculty on each of 18 laps. Of those 18 model-selected execution records, six contained executable code, ten selected `FRAME`, and two selected `CANNOT`. The other 36 execute-node visits were expected idle branches created by the three-way fan-out.
3. **Reflection override:** the model requested `give_up` 59 times. `node_reflect.py` mechanically changed all 59 to `replan`, so the organism could neither honor deliberate rest nor treat the repeated task failure as grounds for self-modification.

Verification denied all 18 attempts. Reflection ultimately routed 66 times to replan, eight times to frame, and five times to retry. `node_self_modify`, `node_spawn`, `node_satisfied`, and `node_error` were never visited.

The observation system was also too narrow for the complex browser page. In the stuck profile state, the raw scan found 571 unique UIA nodes, but the filter rendered 31 nodes because `max_per_window` was 30. The model repeatedly saw the global navigation and only a small part of the profile controls.

## Corrections made from that evidence

### 1. Planner must produce executable intent

The plan contract now permits only `step_ready`; the obsolete planner `reflect` edge was removed. The prompt requires a complete remaining plan whose first step is executable from the current observation. Uncertainty must become an observation, reading, navigation, or other evidence-gathering step rather than a refusal to plan.

### 2. A woken execute faculty must act

Unchosen execute branches still pass through mechanically and make no model call. A chosen faculty now has one record field: non-empty Python `code`. `FRAME`, `CANNOT`, and their redundant pseudo-signals were removed from the execution contract and node code. When a direct target is absent, the faculty must use a listed observation or navigation capability to gather concrete evidence.

The generic record-contract machinery now supports wiring-defined JSON types, non-empty fields, and rejection of additional fields. For execution, the schema requires a non-empty string and rejects every extra key. This keeps the requirement in `wiring.record_contracts` rather than recreating it as an execute-specific Python enum table.

### 3. Reflection owns its choice again

The Python routing override and its task/contract failure classifications were removed from `node_reflect.py`. All seven legal reflection signals now pass through unchanged. The prompt treats repeated identical failure as evidence, requires a correctable organism defect to escalate before deliberate rest, and rejects cycling without materially new evidence.

### 4. The narrative no longer resets on accepted replans

The planner now appends its plan retelling to `state["effective_goal"]`. The old code rebuilt the narrative from the root goal whenever a plan was accepted, which erased accumulated intermediate history six times in the analyzed run.

### 5. Observation breadth increased without a task branch

`observe_config.hover_cache.filter.max_per_window` increased from 30 to 120. This is a task-agnostic capability change. It does not assume a browser, website, or control name.

### 6. Forensic logs no longer duplicate the largest values

Node event summaries omit the full root/effective narrative. Node-output traces omit the full narrative and observation structures while retaining record data, patch/evidence key lists, action results, failures, and other compact evidence. Brain requests store each message once instead of storing the user content and a second parsed copy. The xAI transport logs usage and response metadata rather than embedding the full provider response body again.

Applying the new logging shape to every event in the old 44,105,081-byte runtime log produces a measured projection of 10,332,671 bytes: **76.57% smaller**. This is a deterministic replay projection, not a claim from a new live run.

Across the touched source and wiring files, the corrected version is 1,303 bytes smaller than commit `1b917b3` despite adding generic contract validation and repairing the error-node edge.

### 7. Error recovery no longer emits an illegal dead-end

`node_error` previously emitted `halt` when observation data was missing, but `halt` is not a legal edge from that node. It now emits the existing `guidance` signal, re-entering guidance and observation through the bus. Deliberate rest remains owned by `node_satisfied`.

## Architecture

### Stable substrate

| File | Responsibility |
|---|---|
| `core_organism.py` | Turns the frontier, persists state, applies self-evolution, and enforces the operator leash |
| `core_node_base.py` | One lifecycle for LLM nodes: payload, think, signal, patch |
| `core_loader.py` | Dynamic file-based loading by convention; no node registry |
| `core_bus.py` | Records, node outputs, edge validation, compact state/evidence summaries |
| `core_brain.py` | Model messages, structured schema, contract validation, cache key, event logging |
| `core_wiring.py` | Loads and validates `wiring.json`; atomic JSON persistence |
| `core_state.py` | Duration, pause/step control, exception classification |
| `check_topology.py` | Reachability, dangling-edge, barrier, prompt, and record-contract coherence gate |
| `core_observation.py` | UIA raw scan, filter, tree rendering, and action index |
| `core_nodes.py`, `core_desktop.py` | Local capabilities and desktop actions |

### Plugins

LLM nodes subclass `BaseNode`; mechanical nodes remain pure functions of state. Execute instances are loaded from the same `node_execute.py` by names such as `node_execute:browser`. A new convention-named node requires no compile-time registry change.

### Wiring as the behavioral source of truth

`wiring.json` contains topology, prompts, aliases, record contracts, capabilities, observation configuration, model configuration, and self-modification policy. A topology change must be accompanied by matching prompt and contract changes, then pass `check_topology.py`.

## Running

The real eyes and hands require Windows 11 and UI Automation dependencies.

```bash
# Fresh bounded run
python core_organism.py "your goal in plain words" --reset --duration-seconds 120

# Resume persisted state
python core_organism.py "your goal in plain words" --duration-seconds 300
```

The default development leash is 120 seconds. Use `guidance.txt` for external counsel. `runtime_control.json` supports run, pause, and step. `runtime_stop.json` is the external stop surface.

## Verification performed on the corrected code

```bash
python3 -m py_compile *.py
python3 check_topology.py
```

The topology gate reports 16 reachable nodes, no dangling targets, correct barrier arity, and nine coherent record contracts.

Additional deterministic checks verified that:

- an old planner `reflect` record is rejected;
- an old execution `FRAME/CANNOT` record is rejected for unexpected keys;
- blank execution code is rejected;
- a non-empty action program is accepted by the generated strict schema;
- planner output preserves the prior narrative;
- every legal reflection signal passes through unchanged;
- compact event traces remove the large duplicate fields while retaining action/failure evidence.

These checks prove the old no-op outputs are no longer contract-valid. They do not substitute for a fresh Windows desktop run.

## Development rules

1. Stay task-agnostic. Improve prompts, contracts, capabilities, or topology; never branch on a goal or application name.
2. Keep behavior in nodes and wiring. Core modules turn and validate the wheel.
3. Fail hard and fix the writer. Do not add silent fallbacks for missing state.
4. Keep record requirements in `wiring.record_contracts`.
5. Preserve dynamic file-based plugins and the single LLM-node base lifecycle.
6. Change topology, prompts, and contracts together.
7. Never truncate or reset the goal-narrative.
8. Treat failure as evidence for the narrative, not a new defensive branch.
9. Prefer deletion and reuse. Validate, commit one coherent change, then advance the known-good ref.

## Evidence and history

- Pre-correction evidence/docs commit: `1b917b3`
- Progress correction: `6fb1ab3`
- Forensic log slimming: `7f641fd`
- Legal error recovery: `df52e08`
- Escalation before premature rest: `36c9a0e`
- Historical runtime events: `runtime_events.jsonl`
- Provider ground truth: `request-logs-2026-07-10.jsonl`
- Final historical state: `runtime_state.json`
- Detailed derivation: `FORENSIC_AUDIT.md`
- Previous README sentence tracking: `README_SENTENCE_AUDIT.md`

## Safety

This software can operate a logged-in desktop and execute generated Python. Coherence is not a safety certification. Run it only with explicit permission, least-privilege accounts, a bounded operator leash, and active log review. Keep security boundaries in the environment and permissions rather than application-specific branches inside the organism.
