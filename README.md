# endgame-ai — slot-based AI colony with priority interrupts

**5 parallel AI personas** working on goals, interruptible by priority. A router persona (`comms_operator`) decides who works on what.

```bash
python tui.py --model-profile nemotron    # Nemotron (reasoning)
python tui.py --model-profile gemma       # Gemma (fast)
python tui.py --backend acp              # ACP/Kiro (sequential)
```

Space = pause/unpause. q = quit. Type to talk to the colony.

---

## How It Works

- **5 slots** run in parallel — each slot holds one persona process
- **Slot 1** = `comms_operator` (fixed) — routes work, assigns priority, bridges human
- **Slots 2-5** = dynamic — currently: architect, implementor, reviewer, devops
- Each persona **always works** — either on assigned tasks or self-maintenance
- **Priority interrupt**: if a higher-priority message arrives, persona drops current task and switches

## Priority Levels

| Level | Name | When |
|-------|------|------|
| 3 | HUMAN | Human typed a message |
| 2 | CRITICAL | Blocking other personas |
| 1 | NORMAL | Assigned by comms_operator |
| 0 | MAINTENANCE | Self-directed (default) |

## Pipeline

Each persona runs: `plan → execute Python → verify → fission credit`

## Quick Start

```bash
# 1. Start LM Studio, load a model
# 2. Run
python tui.py --model-profile nemotron
# 3. Watch. Type @persona messages to interact.
```

## Files

```
main.py      — persona entry point
engine.py    — pipeline + priority interrupt
agents.py    — plan/act/verify/fission
reactor.py   — 5 slots, respawn
tui.py       — 45-line fixed display
llm.py       — LM Studio + ACP
comms.py     — message bus + priority
log.py       — JSONL events
config.py    — slots, profiles, tunables
```
