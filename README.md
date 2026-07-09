# endgame-ai

A task-agnostic organism that operates a Windows 11 desktop like a person: it sees the screen through UI Automation, moves the hands (click, type, run Python and shell), and carries one goal-narrative that every node rewrites as it passes through. Not a pipeline with a first and last step — it turns on a wheel and stops only when it chooses to. This file is the living handover, read by the organism itself. Keep it minimal and true.

## Core commitment
Task-agnostic, always. The same 16 nodes serve any goal; behavior comes from the goal-narrative and the model, not from task branches. No task-specific code is ever added. It reaches the desktop with a handful of Python files — no agent SDK, no RAG, no MCP, no skills, no tool registry.

## The wheel (live topology)
`wiring.json` is the wheel and the contract book. It is entered at `node_guidance` each lap; every path returns to the wheel and nothing dead-ends. The only halt is a deliberate `node_reflect -> give_up -> node_satisfied`. 16 nodes, cycle_start = node_guidance, barriers = {node_barrier: 3}.

- node_guidance — reads guidance.txt, folds counsel into the narrative (guidance, not command)
- node_observe — sees the desktop via UIA
- node_planner — lays the ordered intent toward the goal
- node_scheduler — sets the single next step
- node_dispatch — wakes the faculties a step needs, fans out
- node_execute:{browser,editor,terminal} — the hands; write and run Python
- node_barrier — gathers the faculties back into one (arity = dispatch fan-out)
- node_verify — confirms or denies a step on evidence only
- node_reflect — the conscience: retry, replan, frame, escalate, topology_patch, spawn, give_up
- node_frame_action — studies the screen and frames how to strike
- node_self_modify — rewrites the organism's own code and wiring (git-backed, gated)
- node_spawn — begets a child organism (cap_spawn, depth-gated)
- node_satisfied — the only deliberate halt
- node_error — re-narrates a stumble and returns the wheel to motion

## Memory and sanity: the goal-narrative
One memory that matters: `state["effective_goal"]`. Every node appends a tagged line (`[PLANNER]`, `[DISPATCH]`, `[VERIFY]`, ...). It is never truncated — a missing field is a bug to fix at its source, never a defaulted `.get`. Coherence is psychological: because each node re-tells the shared goal in its own words, a company of fallible LLM nodes holds to one purpose.

## Prompts and contracts (single source of truth)
Each prompt = `wiring.shared_prompt_prefix` + the node fragment in `wiring.prompts`; `wiring.prompt_aliases` lets `node_execute:*` reuse the base execute prompt. Record contracts live in `wiring.record_contracts`; `core_brain` reads them to validate records and build the structured-output schema. Capabilities live in `wiring.capabilities`. No hardcoded mirrors in Python. The dynamic payload (narrative, step, observation) is serialized last, once, under a single `observation` key.

## Self-modification and recursion (built, not yet exercised live)
`node_reflect` may route to `node_self_modify`, which proposes a git-backed patch (files to read/write/delete, wiring patches, commands, expected validation). Wiring changes are gated by `core_wiring.validate_wiring` + `check_topology.coherence_problems` before activation. A known-good ref (`refs/endgame/known_good`) plus hot-swap guard a bad edit. `node_spawn` raises a depth-gated child organism and folds its narrative back. Both are wired and reachable; no live run has triggered them yet.

## Architecture
Substrate (small, stable core): `core_organism` turns the wheel; `core_loader` does dynamic file-based node/cap/transport loading (no registry); `core_node_base` is BaseNode (think -> build_payload -> signal -> patch); `core_bus` holds records, signals, emit, validate_signal, briefs; `core_brain` is the LLM call, contracts, structured outputs, event log; `core_wiring` loads/validates wiring; `core_state` holds state, tick, operator leash; `core_stop_check` is the stop-file/pid leash; `check_topology` is the coherence gate (also used by self-modify); `core_nodes`/`core_desktop`/`core_observation` are the capability runtime + Windows UIA eyes/hands (Windows-only via comtypes); `cap_spawn` is the child organism; `transport_xai` is the real xAI HTTP; `transport_file_proxy` is the off-host debug transport. Bus law: every node emits `(signal, patch)`; the bus validates the signal is a legal edge out of that node, applies the patch, ticks, and routes. Fan-out edge is a list; a fan-in barrier waits until its arity is met.

## The rules this system depends on
1. Task-agnostic, always. Never add task-specific handling; fix the prompt, contract, or a capability.
2. System = nodes + wiring, everything hot-swappable.
3. No branching, fallbacks, or defensive coding. Fail hard and loud. Prefer deleting code to adding it. Requirements live in `wiring.record_contracts`, not Python mirrors.
4. Plugins are dynamic and file-based — no compile-time registry.
5. Keep the load-bearing organs alive: hot-swap, self-modify, coherence gate.
6. When the graph changes, change prompts and contracts with it in `wiring.json`.
7. The narrative is never truncated.
8. A failure is information for the narrative, not a branch to add; it routes through node_error.
9. This README is the single living handover. Update it after every change; verify, then commit.

## Proven vs. not-yet-proven
Proven (observed on the Windows host): the wheel turns full laps; all three faculties fan out and the barrier joins them; it does real desktop work (opened a browser, typed a query, read the reply); it verifies honestly (denies its own incomplete step); it recovers from its own bad code via node_error without crashing; off-host gates pass. Not yet proven live: node_self_modify and node_spawn being self-chosen; runs longer than ~60s; completing a whole multi-step goal end to end; guidance.txt steering an active run.

## Running it
Windows 11 (UIA needs it). From repo root on the host: `python core_organism.py "goal in plain words" --reset --duration-seconds 120` (fresh), or omit `--reset` to resume. `duration_seconds=None` runs unbounded. Model config in `wiring.model`. Steer via `guidance.txt`. Watch it think in `runtime_events.jsonl` — read that file to evaluate a run: judge liveness and coherence, not task completion. Off-host gates (WSL/Linux; acting nodes need Windows/comtypes, rest is pure Python): `python3 -m py_compile *.py`; `python3 check_topology.py` (exit 0 = coherent). Push from WSL via `git.exe -C 'C:\Users\ewojgab\Downloads\endgame-ai' push origin <branch>`. This is autonomous software that operates a real PC after the user grants permission; coherence and replay integrity are not a safety certification. Require explicit consent, an operator leash during validation, audit of runtime_events.jsonl, and controls around what the account may access — keep safety at the environment and permissions, never as task branches inside the wheel.
