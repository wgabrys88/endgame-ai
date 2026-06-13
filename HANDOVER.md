# HANDOVER — grok-dev (2026-06-13)

## Branch

```
grok-dev  (push before test: git pull origin grok-dev)
python tui.py --model-profile nemotron
```

Docs: `KNOWLEDGE.md` (architecture) · `CHECKLIST.md` (test steps)

## Completed this session

### Stability
- TUI: session slot reset, sync output, respawn detection
- Reactor: `is_alive()` Windows API fix (was killing live slots every 5s)

### Orchestrator + Nemotron
- Workers idle until blackboard inbox
- `LLM_MAX_CONCURRENT=1`, thinking enabled for nemotron
- Staggered slot spawns

### Blackboard protocol v1
- Unified envelope: `schemas/bus_v1.json`
- Kinds: message, ping, request, **route**, **telemetry**, event, evolve, verdict, status
- Payload schemas: `schemas/route.json`, `schemas/telemetry.json`
- Control channel: `runtime/comms/control.jsonl` → reactor reassign

### MoE closed loop (Bause + Rodriguez)
- `engine._moe_route()` — deterministic softmax gating every 20s
- `comms.colony_state()` + `softmax_route()` + `route()`
- Stuck detection: stag≥0.7, |vel|≤0.01, 5 ticks → `moe.escalate` + `reassign`
- comms_operator LLM only on human interrupt (pri=3)

## Traceability matrix

| Component | File(s) |
|-----------|---------|
| MoE gate | `engine.py` `_moe_route`, `comms.py` `route/colony_state/softmax_route` |
| Pressure | `engine.py` `_update_pressure`, `plugins/comms_beacon.py` |
| Reassign | `reactor.py` `drain_control`, `comms.py` `post_control` |
| Prompts | `prompts/planner.txt`, `prompts/personalities/*.txt` |
| Schemas | `schemas/planner.json`, `bus_v1.json`, `route.json`, `telemetry.json` |
| Display | `tui.py` moe.route / moe.escalate phases |

## What works now

- 5 slots stable (no false respawn loop)
- Structured telemetry on blackboard
- MoE routes maintenance work to highest-power worker
- Escalation path wired to reactor reassign
- Human @mention wakes workers with pri=3

## Next (AgentBreeder)

- `kind=evolve` writer in mutator plugin
- reflector in pipeline for failure diagnosis
- quality_critic as default slot rotation target
- MAP-Elites fitness from fission + stagnation history

## Key files

```
engine.py  — _moe_route, _update_pressure, interrupt
comms.py   — blackboard v1 protocol
reactor.py — MoE reassign drain
agents.py  — orchestrator scheduler rules
config.py  — STAG_ESCALATE, STUCK_TICKS_ESCALATE, MOE_GATE_MIN
```