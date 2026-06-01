# Endgame-AI

A persistent, self-regulating, self-improving autonomous desktop agent. It observes the screen, plans semantically, acts via real input, verifies outcomes, and rewrites its own prompts during execution based on what it learns.

No dependencies. No pip install. No frameworks. Pure Python 3.13 + Windows 11.

---

## What It Does

Endgame-AI controls your Windows desktop exactly like a human does: it looks at the screen, decides what to click or type, does it, checks if it worked, and repeats until your goal is done. It gets better at your specific tasks over time because it reflects on what worked and rewrites its own instructions during each run.

**Proven in live execution (2026-06-01):**

In a single uninterrupted 41-iteration run, the system:

1. Opened Chrome, navigated to YouTube, found and played Shakira - She Wolf
2. Opened Opera, navigated to grok.com
3. Conducted a 5-question deep philosophical conversation with Grok about consciousness (qualia, hard problem, philosophical zombies, panpsychism, meta-cognition limits)
4. Navigated to x.com, composed and published a 519-character research summary
5. Navigated to linkedin.com, composed and published a 691-character research post
6. Terminated naturally with verified evidence of both publications

During execution, the system caught its own premature completion attempt (verifier denied a false "done" claim at iteration 14) and self-corrected without human intervention. It also spawned 4 distillation children that analyzed its own chaos metrics and produced evolutionary recommendations - all completing in 1 iteration without blocking the main agent.

---

## How to Run

```
python main.py "your goal here" --backend lmstudio
python main.py "your goal here" --backend acp
python main.py --resume --backend acp
```

Run as Administrator in case of permission issues. The system needs low-level ui-automation access.

**Backends:**
- `lmstudio` - local LLM via LM Studio HTTP API (localhost:1234)
- `acp` - remote via kiro-cli ACP protocol in WSL2

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐
│  OBSERVER   │────▶│   PLANNER   │────▶│    ACTOR    │────▶│ EXECUTE  │
│             │     │             │     │             │     │          │
│ UI tree walk│     │ Decides WHAT│     │ Resolves to │     │ SendInput│
│ + cursor    │     │ to do next  │     │ element IDs │     │ or shell │
│ probe scan  │     │ (semantic)  │     │ from screen │     │          │
└─────────────┘     └─────────────┘     └─────────────┘     └──────────┘
       ▲                                                          │
       │                                                          │
       │            ┌─────────────┐     ┌─────────────┐           │
       └────────────│  REFLECTOR  │◀────│  VERIFIER   │◀──────────┘
                    │             │     │             │
                    │ Rewrites    │     │ Confirms or │
                    │ own prompts │     │ denies done │
                    └─────────────┘     └─────────────┘
```

- **Observer** - walks the Windows UI Automation tree and probes the screen with physical cursor movement to discover elements invisible to tree enumeration alone. Produces a numbered element list.
- **Planner** - decides what to do next using semantic descriptions (no coordinates, no IDs). Modes: direct action, parallel decomposition, or done.
- **Actor** - resolves the planner's semantic instruction to specific element IDs from the fresh screen list. Outputs verb + target + value.
- **Execute** - performs the action: click, write, press, hotkey, scroll, wait, focus, read_file, write_file, spawn_agent, cmd, done.
- **Verifier** - confirms goal completion with concrete evidence from the screen. Denies premature claims.
- **Reflector** - analyzes execution history, rewrites prompts, adds lessons, rewrites goals. The system's self-improvement engine.

---

## Self-Improvement

The reflector rewrites `prompts/planner.txt`, `prompts/actor.txt`, and `prompts/verifier.txt` during execution based on concrete lessons from action history. It also accumulates insights in `lessons.json` and maintains an evolution ledger across runs.

The prompts in this repository are the post-DEMO genome, containing some evolutionary task specific data. After execution, your copy diverges. The system that ran on May 31 added 4 rules to its own planner prompt mid-execution - scroll limits, JSON enforcement, phase tracking, and LinkedIn-specific flow - all invented by the system to solve problems it encountered.

---

## Chaos System

A Lorenz attractor drives self-regulation. Inputs: action diversity, progress, stagnation, repetition. The chaos level gates behavior:

| Chaos Level | System Response |
|-------------|----------------|
| < 0.25 | Normal operation |
| 0.25 – 0.5 | Warning injected into planner context. Blocks recently-repeated actions |
| 0.5 – 0.7 | Forces parallel decomposition. Rejects premature done claims |
| 0.7 – 0.95 | Emergency reflection. Spawns recovery children |
| ≥ 0.95 (sustained 5 iterations) | System halts. Exit 1 |

Observed behavior: chaos rose from 0.00 to 0.35 during repetitive scrolling, then self-corrected to 0.08 as the system moved to novel actions. Self-regulating without external intervention.

---

## Fault Recovery

If screen observation fails (encoding errors, crashed applications, locked screen), the system does not go blind. The planner runs with stale screen data and the error in its PROBLEM field. It can recover using blind verbs (hotkey, cmd, wait, spawn_agent) without needing fresh element IDs.

If the planner or actor LLM fails (parse errors, refusals), the failure is recorded, chaos rises, and reflection triggers automatically. The system retries with adapted prompts.

---

## Multi-Agent

The planner can decompose goals into parallel sub-goals. Each child runs the same architecture as an independent process. Coordination happens via `blackboard_state.json`. Screen access is serialized via file-based locking so agents don't interfere with each other's observations.

---

## Termination

No cycle caps. The system runs `while True` and terminates on:

1. **Done** - goal achieved, verified with evidence → exit 0
2. **Chaos halt** - chaos ≥ 0.95 sustained 5 iterations → exit 1
3. **Interrupt** - Ctrl+C → exit 1
4. **Inbox kill** - external kill command via blackboard → exit 0

---

## Files

```
endgame-ai/
├── main.py                  Entry point, CLI
├── orchestrator.py          Core loop: plan → act → verify → reflect
├── state.py                 Blackboard, EventBus, Lorenz chaos system
├── observer.py              UI Automation tree walk + cursor probe scan
├── actions.py               12 verb handlers (click, write, cmd, etc.)
├── dispatch.py              LLM call + JSON extraction with salvage
├── llm.py                   LM Studio / ACP backend
├── config.py                All constants (no magic numbers elsewhere)
├── journal.py               Execution journal
├── lessons.py               Learned insights across runs
├── persistence.py           Blackboard state, evolution ledger
├── event_schema.py          Inter-agent event protocol
├── blackboard_controller.py Standalone CLI for blackboard management
├── win32.py                 Raw ctypes: UIA COM, SendInput, VK_MAP
├── acp_client.py            ACP backend via kiro-cli in WSL2
├── prompts/                 System prompts (rewritten by reflector)
│   ├── planner.txt
│   ├── actor.txt
│   ├── reflector.txt
│   └── verifier.txt
├── schemas/                 JSON schemas enforced on LLM output
│   ├── planner.json
│   ├── actor.json
│   ├── reflector.json
│   └── verifier.json
└── pyrightconfig.json       Type checking: strict mode, Python 3.13
```

---

## Design Philosophy

The wiring is the intelligence. The LLM is the brain. Everything else is dumb, honest plumbing that gives it the best possible current picture of reality every iteration.

No RAG. No skills database. No MCP. No API wrappers. No frameworks.

When the loop is tight and honest, even modest models become useful. When the model gets better, the same system becomes dramatically more capable. The future belongs to better wiring, not more wrappers.

---

*"If you're going to try, go all the way. Otherwise, don't even start."*


---

## Appendix A: Self-Evolution During Live Execution

During the 41-iteration run on 2026-06-01, the reflector rewrote both the planner and actor prompts mid-execution. These are task-specific adaptations the system invented to solve problems it encountered.

### Planner Prompt - Before Run (genome)

TODO:

### Planner Prompt - After Run (evolved)

TODO:

### What the Reflector Learned

The system discovered through trial and error:
1. Clicking taskbar buttons doesn't reliably foreground windows
2. Saving to intermediate files wastes iterations - type directly into web compose fields
3. Done detection must verify ALL sub-goals, not just the last action
4. The Grok conversation needs explicit topic progression to reach depth
5. Navigation via address bar is unreliable

These rules were not programmed. They emerged from the system observing its own failures and adapting.

---

## Appendix B: Distillation Output (Self-Analysis)

During execution, the system spawned 4 distillation children that analyzed its own chaos metrics. 

The system monitors its own entropy and recommends strategy adjustments to itself. It recognizes when it's becoming too predictable (stagnation risk) and when it's too chaotic (failure risk).

---

## Appendix C: Future Architecture - Event-Driven Model

The current architecture is a sequential pipeline: observe → plan → act → verify → reflect. This works but has a structural limitation: if observation fails, the entire pipeline stalls.

A future redesign would make the blackboard the single source of truth with components reacting to state changes independently.

In this model:
- Observer failure doesn't block the planner - it runs with stale data + error context
- Chaos level determines which components are active and what actions are permitted
- The system can self-kill and spawn a successor when damage is unrecoverable
- Components operate as independent responders, not sequential stages

This redesign is stored for when the sequential model proves insufficient. The current architecture is proven across 40+ iteration runs with zero unrecoverable failures.
