# AGENTS.md — Colony Architecture

## Concept

5 parallel **slots**. Each slot runs one **persona** — a process with a goal and a personality.

- **Slot 1** = `comms_operator` (always, never swapped) — MoE softmax router
- **Slots 2-5** = dynamic — comms_operator assigns via blackboard `route` + reactor `reassign`

**Personas**: `comms_operator`, `architect`, `implementor`, `reviewer`, `devops`, `quality_critic`

## Priority Interrupt

| Level | Name | Meaning |
|-------|------|---------|
| 3 | HUMAN | Human typed a message |
| 2 | CRITICAL | MoE escalation / blocking |
| 1 | NORMAL | Routed work from comms_operator |
| 0 | MAINTENANCE | Idle until inbox |

## Pipeline (inside each persona)

```
scheduler → planner → actor → verifier → fission_judge
```

comms_operator: deterministic `engine._moe_route()` every 20s (no LLM). LLM planner only on human interrupt (pri=3).

Workers: idle until `route`/`request`/`ping` in inbox. One LLM call colony-wide (`LLM_MAX_CONCURRENT=1` for nemotron).

## Blackboard v1 (`comms.py`)

- Intent: `runtime/comms/messages.json`
- Observation: `runtime/comms/events_bus.jsonl`
- Control: `runtime/comms/control.jsonl` (reactor reassign)
- Schema: `schemas/bus_v1.json` — see `KNOWLEDGE.md`

## Pressure / MoE

- `stagnation` 0→1 stuck, `power` = 1−stagnation (confidence), `velocity` = Δstagnation
- Stuck 5 ticks at stag≥0.7 → `moe.escalate` + slot reassign
- Full map: `KNOWLEDGE.md`

## Process Tree

```
python tui.py --model-profile nemotron
  └── reactor.py
        ├── main.py [s1 comms_operator]
        ├── main.py [s2 architect]
        ├── main.py [s3 implementor]
        ├── main.py [s4 reviewer]
        └── main.py [s5 devops]
```

## Files

```
main.py engine.py agents.py reactor.py tui.py llm.py comms.py log.py config.py
prompts/ schemas/ plugins/
KNOWLEDGE.md  CHECKLIST.md
```

## Rules

1. Never create new .py files
2. No env vars for runtime config — CLI only
3. Personas communicate via bus, not shared state
4. Test with `CHECKLIST.md` on `grok-dev`