# endgame-ai

`endgame-ai` is a local Windows desktop organism. The tracked repository is part of the prompt sent to the model during self-evolution, so source size is runtime cost.

## Contract

- `core_organism.py` owns the cycle, state writes, stop/deadline checks, topology routing, and self-modify apply/commit/hot-swap.
- `wiring.json` is the single source of truth for model transport, paths, topology, observe config, self-modify config, and organ prompts.
- `core_node_base.py` dynamically loads `node_*.py` modules named by `wiring.json`.
- `core_brain.py` dynamically loads the selected `transport_*.py` module.
- `node_execute.py` runs model-emitted Python through `exec(code, ns)` with GUI, subprocess, filesystem, module, state, wiring, and observation helpers injected by `core_nodes.py`.
- `node_self_modify.py` emits `git_evolution_patch`; `core_nodes.py` applies file writes, deletes, wiring patches, commands, commits them, and updates the configured known-good git ref.
- The organism is intentionally unsafe. Evolution is constrained by code contracts and git mechanics, not by sandboxing or policy guardrails.

## Cycle

```mermaid
stateDiagram-v2
  [*] --> node_observe
  node_observe --> node_planner: initial_screen
  node_observe --> node_execute: screen_ready
  node_planner --> node_scheduler: step_ready
  node_planner --> node_reflect: reflect
  node_scheduler --> node_observe: step_ready
  node_scheduler --> node_satisfied: plan_complete
  node_execute --> node_verify: verify
  node_execute --> node_observe: frame
  node_execute --> node_reflect: reflect
  node_verify --> node_scheduler: step_confirmed
  node_verify --> node_reflect: step_denied
  node_reflect --> node_observe: retry
  node_reflect --> node_planner: replan
  node_reflect --> node_frame_action: frame
  node_reflect --> node_self_modify: escalate
  node_reflect --> node_self_modify: topology_patch
  node_reflect --> node_satisfied: give_up
  node_frame_action --> node_observe: framed
  node_self_modify --> node_planner: modified
  node_self_modify --> node_reflect: modify_failed
  node_error --> node_planner: planner
  node_error --> node_reflect: reflect
  node_satisfied --> [*]: halt
```

Every node emits a signal plus a state patch. `effective_goal` is rewritten through planner, scheduler, execute, frame, verify, reflect, self_modify, and satisfied so the current narrative is carried forward while `state.goal` keeps the root goal.

## Runtime Files

- `runtime_state.json`: resumable state.
- `runtime_control.json`: `run`, `pause`, or `step` control.
- `runtime_events.jsonl`: bus, node, and brain forensics.
- `runtime_stop.json`: stop request.
- `runtime_*.pid`: process registry.

These files are ignored by git and are not part of the prompt surface.

## Start

```powershell
python core_organism.py "goal" --reset --duration-seconds 300
python core_organism.py "continue goal" --duration-seconds 300
```

Selected transport comes from `wiring.json:model.transport`. The default is `transport_xai`; set `XAI_API_KEY` for API mode or change the transport intentionally.
