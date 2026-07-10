# endgame-ai

`endgame-ai` is a task-agnostic autonomous organism for a real Windows 11 desktop. It reads the desktop through UI Automation, acts through a small capability surface, and carries one goal-narrative around a dynamically wired wheel of planning, execution, verification, reflection, self-modification, spawning, and deliberate rest.

This revision is based on the attached **2026-07-10 failure run**, not on an inferred story. The run did not prove that the requested LinkedIn task was impossible. It stopped after **105.243 seconds** of a 600-second leash because the self-modification path was broken and the evidence used to diagnose the first action was unreliable. The corrected code removes those general defects without adding LinkedIn-, browser-, or task-specific branches.

The full derivation is in [`FAILURE_RUN_FORENSICS.md`](FAILURE_RUN_FORENSICS.md). Raw immutable run artifacts are packaged beside this repository under `failure-run-evidence/`.

## Current verdict

| Question | Evidence-based answer |
|---|---|
| Did the organism use the full ten-minute leash? | No. It halted after 105.243 seconds with about 494.75 seconds remaining. |
| Did it try self-modification? | Reflection selected escalation five times, but zero patches reached application, validation, or Git. |
| Why did every self-modification fail? | `core_organism.py` called evolution functions on `core_node_base`, although those functions live in `core_nodes`. The rollback call failed the same way and masked the first missing function. |
| Was Chrome proven not to launch? | No. The selected click was `(339, 1050)` while the observation declared a `1536 × 864` screen. The click API reported only that a call returned, and verification used the pre-action observation. |
| Was `give_up` justified? | No. It followed a broken repair mechanism, stale verification evidence, incorrect elapsed-time estimates, and an unexhausted leash. |
| Should `give_up` exist? | Yes, as deliberate rest for completion, unsafe requests, a genuinely proven impossibility after working repair paths, or an external stop/deadline. A failed repair subsystem is evidence to repair the subsystem, not proof that the goal is impossible. |
| Is live completion now proven? | Not yet. The corrected mechanics and gates pass deterministic tests; a fresh Windows desktop run is still required. |

## The corrected wheel

Topology, prompts, contracts, aliases, capability descriptions, model configuration, and self-modification policy live in `wiring.json`.

```text
node_guidance:plan
        |
node_observe:plan
        |
   node_planner -> node_scheduler
                         |
                 node_guidance:act
                         |
                  node_observe:act
                         |
                    node_dispatch
                / browser | editor \
               + terminal faculties +
                         |
                    node_barrier
                         |
                node_observe:verify
                         |
                    node_verify
                         |
                    node_reflect
          retry / replan / frame / escalate
                         |
          self-modify / spawn / deliberate rest
```

The three observe instances are the same mechanical plugin loaded by name. They provide fresh evidence before planning, before action, and after the execution barrier. Every path returns to the wheel or reaches deliberate rest through a legal edge.

## What changed

### Self-modification is now executable

`core_organism.py` uses `core_node_base` only for dynamic node invocation and `core_nodes` for evolution operations. A proposed patch now follows one coherent path:

1. validate the wiring-derived record;
2. restrict every write/delete to the wiring's evolvable-file policy;
3. apply complete file replacements, deletions, and JSON patches;
4. run the mandatory coherence gate: wiring validation, topology/plugin reachability, and compilation of all root Python files;
5. run the proposal's validation commands;
6. force-stage only the already-approved paths, so convention-named runtime plugins can enter an allowlist-style Git worktree;
7. commit, advance `refs/endgame/known_good`, and optionally push;
8. hot-swap touched paths to known-good on failure.

The self-modification model alone receives a stable prefix containing the complete tracked Python/JSON source. Its contract requires typed arrays, non-empty rationale and validation, complete file contents, and no placeholders or Git ceremony. Other organs do not pay that source-context cost.

### Actions and observations now describe the same physical screen

The desktop thread opts into per-monitor DPI awareness before UI Automation starts. Click and scroll coordinates are checked against the physical screen and fail loudly when outside it. Mouse actions use physical global coordinates; the old window-message path incorrectly supplied global coordinates to an API that expected client coordinates.

The observation artifact records physical screen dimensions. A mandatory post-action observation now occurs in the graph before verification. An action returning without an exception is therefore no longer treated as evidence that the intended UI state changed.

### Exact time replaces model estimation

State now carries invocation start, deadline, elapsed seconds, and remaining seconds in the model brief. Reflection is told to use those values and never estimate elapsed time. The external leash remains mechanical and authoritative.

### Deliberate rest remains legal but is harder to misuse

Reflection can still emit `give_up`; Python does not override its choice. The prompt now requires working repair paths and materially different approaches to be exhausted before declaring a correctable organism defect impossible. Failed self-modification is explicitly not such proof. Completion, unsafe action, logical impossibility, and external stop/deadline remain legitimate reasons to rest.

### Direct capabilities are preferred over fragile gestures

Planning and execution prompts prefer the most direct deterministic capability available. For example, a URL may be opened through `open_url` rather than clicking a taskbar icon. This is a general action-selection rule, not a browser special case.

## Architecture

### Stable substrate

| File | Responsibility |
|---|---|
| `core_organism.py` | Turns the frontier, persists state, applies self-evolution, and enforces the operator leash |
| `core_node_base.py` | One lifecycle for LLM nodes: payload → think → signal → patch |
| `core_loader.py` | Dynamic convention-based plugin loading; no compile-time registry |
| `core_bus.py` | Record and edge validation, state/evidence briefs, node-output frames |
| `core_brain.py` | The only model boundary: messages, source prefix, schema, validation, caching, logging |
| `core_wiring.py` | Loads and validates `wiring.json`; atomic JSON persistence |
| `core_state.py` | Runtime control, exact duration state, and exception classification |
| `core_nodes.py` | Capability runtime and Git-backed self-evolution primitives |
| `core_desktop.py` | Physical Windows input and deterministic launch capabilities |
| `core_observation.py` | UI Automation scan, filter, rendering, action index, screen metadata |
| `check_topology.py` | Reachability, dangling edges, barrier arity, contracts, prompts, and plugin files |

### Plugins

LLM nodes subclass one `BaseNode`; mechanical nodes remain pure state transformations. Instance names such as `node_observe:verify` and `node_execute:browser` resolve to convention-named files dynamically. A new wired node does not require a core registry edit.

### Bus law

Every node emits exactly `(signal, patch)`. The bus validates the signal against the edge for that exact node instance, applies the patch to the one persisted state dictionary, increments the tick, and routes the next frontier. Fan-out branches rejoin through the declared barrier. There are no side channels around the bus.

## Running on Windows 11

Install the repository's Python dependencies in the same environment used to launch the organism. Start a fresh run with `--reset`; omitting it intentionally resumes persisted state.

```powershell
python .\core_organism.py "your goal in plain words" --reset --duration-seconds 600
```

Useful operator surfaces:

- `guidance.txt` — external counsel read at guidance turns;
- `runtime_control.json` — run, pause, and step control;
- `runtime_stop.json` — external stop request;
- `runtime_state.json` — atomically persisted organism state;
- `runtime_events.jsonl` — append-only forensic event stream.

A fresh validation run should demonstrate all of the following from logs, not narrative claims:

1. the first observation reports physical screen dimensions consistent with action coordinates;
2. a selected direct capability or click produces a recorded action;
3. `node_observe:verify` scans after the action timestamp;
4. verification cites that post-action evidence;
5. any self-modification reaches `self_modify_applied` or records the original gate failure without a masked exception;
6. `refs/endgame/known_good` advances only after a validated commit;
7. deliberate rest states a valid terminal condition or the mechanical leash expires.

## Verification in this package

The corrected tree has passed:

```bash
python -m compileall -q .
python check_topology.py
```

The topology gate reports 19 reachable node instances, no dangling edges, correct barrier arity, coherent prompts/contracts, and a convention plugin file for every wired node.

Deterministic tests also proved:

- all five historical self-modification records with dictionary-shaped `file_writes` are rejected by the strict contract;
- a correctly shaped evolution record is accepted;
- the self-modification source prefix is present only for that organ;
- the route is `barrier → node_observe:verify → node_verify`;
- all observe instances emit the same legal `observed` signal;
- a disposable new plugin can be applied, gated, force-staged under the evolvable policy, committed, marked known-good, corrupted, and restored exactly;
- the attached event timestamps reproduce the 105.243-second halt and remaining leash.

These are mechanical proofs. This environment cannot operate the user's Windows desktop, so it does not claim that the LinkedIn goal has already been completed.

## Engineering rules

1. Stay task-agnostic. Improve prompts, contracts, capabilities, or topology; never branch on a goal, site, or application name.
2. Keep behavior in nodes and wiring. Core modules turn and validate the wheel.
3. Fail hard and fix the writer. Do not hide missing state behind defaults or swallowed exceptions.
4. Keep record requirements in `wiring.record_contracts`.
5. Preserve dynamic file-based plugins and the single LLM-node lifecycle.
6. Change topology, prompts, contracts, and aliases together.
7. Never truncate or silently reset the goal-narrative.
8. Treat failure as evidence for reflection and evolution, not as a reason to add task branches.
9. Prefer subtraction and reuse. Validate one coherent change, commit it, then advance known-good.

## Git history for this correction

- `8a4fee0` — source state contained in the uploaded failure archive;
- `b2c90c9` — restore truthful action, post-action verification, exact timing, and working self-evolution routing;
- `2669dd9` — permit only wiring-approved runtime plugin paths to be force-staged into the allowlist worktree;
- the final documentation commit records the forensic verdict and packaged acceptance tests.

## Safety

This software can operate a logged-in desktop, publish account data, execute generated Python, and modify its own source. Coherence is not a security certification. Run it only with explicit account-owner permission, least-privilege credentials, a bounded operator leash, active screen recording/log review, and external controls that the organism cannot silently widen.
