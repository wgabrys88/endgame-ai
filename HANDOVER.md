# HANDOVER — Session 2026-06-13

## What Was Done This Session

### Bugs Fixed
- `.endgame.lock` crash — 5/6 agents couldn't start (Windows can't unlink open files)
- TUI `recent()` method call on wrong object
- Actor using wrong ActionResult field names (`.ok`→`.success`, `.output`→`.observation`)

### Architecture Rewrite (2942 → ~1600 lines)
- **5 slots** (was 6). Slot 1 = comms_operator (fixed). Slots 2-5 = dynamic worker personas.
- **Priority interrupt** — personas check bus each cycle, switch goal if higher-priority message arrives (0=maintenance, 1=normal, 2=critical, 3=human)
- **Pressure math** — stagnation field per persona (0=productive, 1=stuck), computed per cycle, NOT during LLM waits
- **Plugin hot-swap** — `plugins/*.py` reloaded when modified, `run(board)` called each cycle
- **Session logging** — `sessions/YYYYMMDD_HHMMSS/` per run, workspace stays clean
- **Model profiles** — `--model-profile nemotron|gemma` CLI, full hyperparameter sets
- **TUI** — fixed 45 lines, shows agent pipeline bar (S·P·A·V·F) per persona

### Git Cleanup
- Branches archived via tags (archive/colony-dev, archive/colony-nemotron-run, archive/reactor-personalities, archive/simplify-reduce)
- Only `main` + `unify-rewrite` remain as active branches
- All prompts/personalities rewritten — no legacy references

## Current State

```
Branch: unify-rewrite (pushed, up to date)
Last commit: 6163bcd feat: restore plugin hot-swap + fix actor run_python integration
Run command: python tui.py --model-profile nemotron
             python tui.py --backend acp
```

## What Works
- 5 slots spawn, stay alive, get events
- Planner calls LLM, actor executes Python with full system access
- Verifier checks results, fission credits awarded
- Priority interrupts from bus
- Plugin hot-swap
- Pressure math per cycle
- bus_post/bus_id/bus_request available in actor code
- Model auto-detection from LM Studio

## What Needs Doing Next

### Priority 1: comms_operator as MoE router
Currently comms_operator plans like any other persona. It should:
- Read stagnation of ALL slots (from bus events)
- Make routing decisions: "slot 3 is stuck, reassign to quality_critic"
- NOT do code work itself — only coordinate

### Priority 2: Orchestrator pattern (fix timeouts)
5 parallel LLM calls overwhelm nemotron. Solution:
- comms_operator makes ONE routing LLM call first
- Assigns work to slots via bus with priority
- Other personas execute Python deterministically (no LLM) until they actually need a new plan
- Result: 1-2 LLM calls active at a time, not 5

### Priority 3: Self-evolution persona
A persona (could be quality_critic or a new mode) that:
- Reads failure patterns from event logs
- Writes plugins to fix recurring issues
- Modifies prompts (carefully, capped)
- This is the AgentBreeder mechanism

### Priority 4: Dynamic slot assignment
comms_operator should be able to:
- Kill a stuck slot and respawn with different persona
- Choose from persona pool based on what work exists
- The reactor already exposes `reassign(slot_id, persona, goal, priority)`

## Key Files
```
engine.py    — the main loop (pipeline + interrupts + plugins + pressure)
agents.py    — pipeline stages (scheduler/planner/actor/verifier/fission_judge)
reactor.py   — slot manager (spawn/kill/respawn)
comms.py     — message bus (the blackboard)
config.py    — all tunables + model profiles
tui.py       — display
log.py       — session-based event logging
actions.py   — run_python() — gives personas full system access
```

## Theoretical Foundation
See README.md "Handover — Theoretical Foundation" section for paper citations:
- MoE (Bause 2026), Blackboard (CAS 2025), Pressure Fields (Rodriguez 2026),
  AgentBreeder (Oxford 2026), Orchestrator Pattern, CoALA framework
