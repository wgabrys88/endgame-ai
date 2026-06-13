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
- **Pressure math**: stagnation field per persona (0=productive, 1=stuck) — feeds routing decisions

## Priority Levels

| Level | Name | When |
|-------|------|------|
| 3 | HUMAN | Human typed a message |
| 2 | CRITICAL | Blocking other personas |
| 1 | NORMAL | Assigned by comms_operator |
| 0 | MAINTENANCE | Self-directed (default) |

## Pipeline (inside each persona)

```
scheduler → planner → actor → verifier → fission_judge
```

Each persona contains these agents internally. The TUI shows their state as `S·P·A·V·F`.

## Session Logging

Every run creates `sessions/YYYYMMDD_HHMMSS/` — all event files go there. Previous sessions preserved. Workspace root stays clean.

## Files

```
main.py      — persona entry point
engine.py    — pipeline + priority interrupt + pressure math
agents.py    — scheduler/planner/actor/verifier/fission_judge
reactor.py   — 5 slots, respawn dead
tui.py       — 45-line fixed display with agent pipeline bars
llm.py       — LM Studio + ACP backend
comms.py     — message bus with priority
log.py       — JSONL events, session-based folders
config.py    — slots, personas, profiles, priorities
```

---

## Handover — Theoretical Foundation

This system maps directly to cutting-edge multi-agent research (2025-2026). Any AI coder continuing this work should understand these connections:

### 1. Mixture of Experts (MoE)

The paper "Multi-Agent Systems are Mixtures of Experts" (Bause et al., CISPA, 2026 — arxiv.org/html/2605.25929v1) formally proves that multi-agent LLM deliberation IS a Mixture of Experts.

In endgame-ai:
- `comms_operator` = the softmax gating network
- It routes based on **relative confidence** of each persona
- The **stagnation metric is the confidence signal inverted** — high stagnation = low confidence = route work elsewhere
- comms_operator reads ALL personas' pressure fields to make routing decisions

### 2. Blackboard Architecture

The paper "Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture" (CAS, 2025 — arxiv.org/html/2507.01701v1):

In endgame-ai:
- The message bus (`runtime/comms/messages.json` + `events_bus.jsonl`) IS the shared blackboard
- NO direct persona-to-persona communication — all coordination through the bus
- `comms_operator` = the "control unit" that reads the blackboard and selects which persona acts
- Result: best average performance while spending fewer tokens (their finding)

### 3. Pressure Fields (Control Theory)

The paper "Emergent Coordination via Pressure Fields and Temporal Decay" (Rodriguez, 2026 — arxiv.org/html/2601.08129v2, github.com/Govcraft/pressure-field-experiment):

In endgame-ai:
- `stagnation` = their "pressure function" — measures gaps in progress
- Failure pressure (0.15/fail) + time pressure (ramps after 60s without fission)
- Resets on fission or goal switch = their "temporal decay"
- Stagnation plateau → comms_operator evicts/reassigns = their "band escalation"
- Their result: **48.5% solve rate vs 1.5% hierarchical, 12.6% conversation-based**

### 4. AgentBreeder (Evolutionary)

The paper "AgentBreeder" (Oxford, 2026 — arxiv.org/html/2502.00757, github.com/jrosseruk/AgentBreeder):

Literally a "breeding reactor" for agent scaffolds. MAP-Elites + evolution. The reflector/mutator agents (currently removed, can return as plugins) ARE this mechanism — they mutate prompts and evolve persona behavior over time.

### 5. Orchestrator Pattern

Instead of 5 personas ALL calling LLM simultaneously (causing timeouts):
- `comms_operator` makes ONE routing decision: "who works on what?"
- Assigns goals to slots via bus messages with priority
- Personas execute deterministically (Python code) — only call LLM when they NEED a plan
- This reduces 5 parallel LLM calls to 1-2 at a time

Reference: "Beyond the Agentic Loop: The Orchestrator Pattern" (stackademic.com/blog/beyond-the-agentic-loop-the-orchestrator-pattern-for-multi-agent-systems)

### 6. Key Insight for Continuation

The LLM is NOT the agent. The LLM is a subroutine inside a deterministic state machine (CoALA framework, openreview.net/forum?id=1i6ZCvflQJ). Each persona is a control loop that occasionally consults the LLM for planning — but the loop itself is pure Python. This is "Flow Engineering" — explicit state transitions with the LLM filling in local decisions.

### Branches

- `unify-rewrite` — canonical development branch (this code)
- `main` — stable (behind, update via PR)
- `colony/nemotron-run` — contains HANDOVER.md with runtime forensics
- Other branches (`simplify-reduce`, `reactor-personalities`, `colony/dev`) — superseded, contain salvageable test harnesses and plugins
