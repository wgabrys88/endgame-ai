# AGENTS.md — Colony Architecture

## Concept

5 parallel **slots**. Each slot runs one **persona** — a process with a goal and a personality.

- **Slot 1** = `comms_operator` (always, never swapped) — routes work, assigns priority
- **Slots 2-5** = dynamic — comms_operator decides which persona runs where

**Personas** are the pool of available identities: `architect`, `implementor`, `reviewer`, `devops`, `quality_critic`. Only 4 can be active at once (slots 2-5). comms_operator picks who's needed.

## Priority Interrupt

Every cycle, each persona checks the bus for higher-priority messages. If one arrives:
- Current task is abandoned
- Goal switches to the new request
- Persona continues working on the new goal

Priority levels:
| Level | Name | Meaning |
|-------|------|---------|
| 3 | HUMAN | Human typed a message — always highest |
| 2 | CRITICAL | Blocking other personas, urgent |
| 1 | NORMAL | Assigned work from comms_operator |
| 0 | MAINTENANCE | Self-assigned, always interruptible |

## Lifecycle

```
1. comms_operator spawns persona with GOAL + PRIORITY
2. persona works: plan → act → verify → fission
3. Outcomes:
   a) GOAL COMPLETE → self-assigns maintenance (pri=0)
   b) INTERRUPTED → higher-pri message arrives, goal switches
   c) EVICTED → comms_operator kills slot, respawns different persona
```

## Pipeline (inside each persona)

```
scheduler → planner → actor → verifier → fission_judge
```

No math thread. No stagnation. No reflector/mutator (removed — add back as plugins if needed).

## Process Tree

```
python tui.py --model-profile nemotron
  └── reactor.py --model-profile nemotron
        ├── main.py [s1 comms_operator] pri=1
        ├── main.py [s2 architect]      pri=0
        ├── main.py [s3 implementor]    pri=0
        ├── main.py [s4 reviewer]       pri=0
        └── main.py [s5 devops]         pri=0
```

## Model Profiles

```bash
python tui.py --model-profile nemotron    # nvidia nemotron (reasoning)
python tui.py --model-profile gemma       # google gemma (fast)
python tui.py                             # auto-detect from LM Studio
```

## Files (core only)

```
main.py      — entry point per persona
engine.py    — pipeline loop + priority interrupt
agents.py    — scheduler/planner/actor/verifier/fission_judge
reactor.py   — 5 slots, respawn dead
tui.py       — fixed 45-line display
llm.py       — LM Studio + ACP backend
comms.py     — message bus with priority
log.py       — JSONL events per process
config.py    — slots, personas, profiles, priorities
```

## Bus

- `comms.post(from, role, text, priority=N)` — post with priority
- `comms.request(from, to, text, priority=N)` — routed request
- `@mention` in text → activates target persona
- Human messages auto-get priority 3

## Rules

1. Never create new .py files
2. No env vars for runtime config — CLI only
3. Personas communicate via bus, not shared state
