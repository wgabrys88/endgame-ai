# PLAN.md — Handover for Next Session

**Branch:** `codex-unify-bus`  
**Date:** 2026-06-19  
**State:** Visual editor + node server working. Reflex arc only. NOT a complete rod.

---

## Current Reality (honest)

We have a **reflex arc**: stimulus → single action → loop.  
We do NOT have a **rod**: goal → plan → step → act → verify → evolve → never stop.

The system can execute desktop actions driven by an LLM, but it cannot:
- Plan multi-step sequences
- Verify its own work
- Diagnose failures
- Drive itself autonomously (browser must be open)
- Know who it is (no persona/identity)
- Communicate with other rods (no bus)
- Evolve its own behavior (no mutation)
- Reproduce (no fission)

### Files on Branch

```
server.py           (273 lines) — stateless node endpoints, passive
actions.py          (~200 lines) — desktop verbs (click, write, press, hotkey, scroll, focus)
desktop.py          (~300 lines) — pywinauto UIA wrapper + hover probe
wiring-editor.html  (601 lines) — React Flow visual editor + browser-driven execution
prompts/wiring.json — topology (11 nodes, 13 edges — reflex only)
prompts/unified.txt — single system prompt (executor mode)
prompts/manager.txt — manager prompt swap (peer orchestration)
prompts/model.json  — LM Studio endpoint config
prompts/schema.json — response format reference
```

### What Works

- `python server.py` → HTTP server on :9077
- Browser auto-loads wiring.json, renders graph
- 🚀 Run / ⏩ Step drives execution via server calls
- Desktop observe + execute works on Windows
- LLM call works when LM Studio is running
- Log replay works (load .txt log file, step through)
- Fan-out edges (one signal → multiple targets)
- Guards: repeat_block, premature_done

---

## The Gap: Reflex Arc → Complete Rod

### Phase 1: Autonomous Loop + Planning (CRITICAL)

**Goal:** Server can run unattended. Browser is dashboard, not brain.

#### 1.1 — Server autonomous mode

```
python server.py              → passive (current, for browser-driven)
python server.py --run "goal" → autonomous loop (new)
```

Add to server.py:
- Cycle loop: load wiring → start at cycle_start → follow edges → call own node handlers → loop
- Metabolism: configurable delay between cycles (limits.observe_interval_s)
- Stop condition: goal_complete or SIGINT
- WebSocket (or SSE) push: broadcast state to any connected browser for live observation

Estimated: +80 lines to server.py

#### 1.2 — Planner node

New node type: `planner` — LLM call with planning prompt that decomposes goal into steps.

```json
{"id": "planner", "type": "planner", "label": "Decompose goal into step sequence"}
```

Input state: `goal`, `screen`  
Output: `plan_steps: [{description, done_when}]`, signal: `plan_ready`

New prompt: `prompts/planner.txt` — "Given GOAL and SCREEN, output a JSON sequence of steps"

#### 1.3 — Scheduler node

New node type: `scheduler` — tracks current step index, emits `step_ready` or `plan_complete`.

```json
{"id": "scheduler", "type": "scheduler", "label": "Advance to next plan step"}
```

Pure logic (no LLM): read `plan_steps` + `current_step_idx` → emit next step or done.

#### 1.4 — Updated topology

```
goal_inbox → planner → scheduler → observe → build_request → llm_call → parse
                          ▲                                              │
                          │                                     EXECUTE──┤
                          │                                              │
                          └──── step_done ◄── verifier ◄── exec_done ───┘
```

### Phase 2: Verification + Reflection (HIGH)

#### 2.1 — Verifier node

New node type: `verifier` — LLM call that checks: "does SCREEN show evidence that the step's `done_when` is satisfied?"

```json
{"id": "verifier", "type": "verifier", "label": "Check step completion evidence"}
```

Input: `screen` (fresh capture), `current_step.done_when`, `last_actions`  
Output signals: `step_confirmed` or `step_denied`  
New prompt: `prompts/verifier.txt`

#### 2.2 — Reflector node

New node type: `reflector` — LLM call that diagnoses why a step failed.

```json
{"id": "reflector", "type": "reflector", "label": "Diagnose failure cause"}
```

Input: `screen`, `last_actions`, `last_error`, `denial_reason`  
Output: `diagnosis`, `suggestion` → feeds back into reasoning history  
Signal: `reflected` → scheduler (retry) or planner (re-plan)

#### 2.3 — Retry logic

Wiring edges:
- `verifier → scheduler` on `step_confirmed` (advance)
- `verifier → reflector` on `step_denied`
- `reflector → scheduler` on `retry` (same step, with diagnosis in history)
- `reflector → planner` on `replan` (too many retries, need new plan)

Counter: `step_retries` in state. After N retries → replan signal.

### Phase 3: Pressure + Metabolism (MEDIUM)

#### 3.1 — Pressure node

New node type: `pressure` — pure math, no LLM.

Runs at cycle boundary. Calculates:
- `fail_pressure = min(1.0, failures * 0.15)`
- `time_pressure` ramps after 60s without progress
- `stagnation = fail_pressure * 0.6 + time_pressure * 0.4`

Signals: `nominal` (stag < 0.7), `escalate` (stag >= 0.7 for 5 ticks)

#### 3.2 — Satisfied/metabolism node

After fission credit or goal_complete:
- Set `satisfied = true`
- Cycle delay → 15s (slow metabolism)
- Watch for new goals from bus/human
- On new goal → `satisfied = false`, resume normal speed

### Phase 4: Identity + Bus (HIGH for colony)

#### 4.1 — Identity in wiring.json

```json
"instance": {
  "role": "manager",
  "persona": "implementor",
  "slot": 3,
  "permissions": ["desktop_exec", "file_edit", "bus_post_telemetry"]
}
```

Server reads persona on startup → loads `prompts/personalities/{persona}.txt` as system prompt base.

#### 4.2 — Bus server

Separate process (or endpoint group in server.py):
- `POST /bus/post` — publish message (envelope v1 format)
- `GET /bus/poll?slot=3&since=<ts>` — get messages for this rod
- `GET /bus/claims` — active work claims

Storage: `runtime/comms/messages.json` (same as main)

#### 4.3 — Bus nodes in topology

- `bus_check` node: poll bus for interrupts/goals → `interrupt` or `no_interrupt`
- `bus_post` node: publish telemetry/verdict/claim after events
- `bus_interrupt` node: preempt current plan with human pri=3 goal

### Phase 5: Fission + Mutation (Phase 1 in main README)

#### 5.1 — Fission judge node

After verifier confirms plan completion:
- Is this novel work? (not a repeat of prior fission)
- Evidence is real? (actual file/screen proof)
- → `fission_credit` or `fission_denied`

#### 5.2 — Local mutator node

Triggered by: pressure escalation + reflector diagnosis
- Reads reflector output
- Proposes prompt patch (actor.txt or verifier.txt only)
- Applies if shadow eval passes (bench scenario subset)

### Phase 6: Colony (Phase 2+ in main README)

#### 6.1 — Multi-instance

Each rod = `python server.py --slot N --persona X --port 907N`

All share:
- Same `wiring.json` (topology)
- Same bus endpoint
- Different persona → different prompt DNA

#### 6.2 — Reactor (supervisor)

Separate process that:
- Spawns rods
- Monitors health (ping /health)
- Respawns dead rods
- Processes fission/evolve events → MAP-Elites archive
- Softmax-routes maintenance work

#### 6.3 — comms_operator rod

Special persona (slot 1):
- No desktop execution permission
- Receives human goals exclusively
- Routes to specialist rods via bus
- MoE gate: reads colony telemetry, assigns by competence

---

## Execution Order (Next Sessions)

```
Session N+1:  Phase 1.1 (autonomous loop in server.py)
              Phase 1.2 + 1.3 (planner + scheduler nodes)
              Phase 1.4 (rewire topology)
              TEST: server runs unattended, plans multi-step, loops

Session N+2:  Phase 2 (verifier + reflector + retry wiring)
              TEST: system detects failed actions, retries, re-plans

Session N+3:  Phase 3 (pressure + metabolism)
              Phase 4.1 (identity/persona)
              TEST: rod runs eternally, slows when satisfied, persona-driven

Session N+4:  Phase 4.2 + 4.3 (bus)
              Phase 5 (fission + mutation)
              TEST: single rod with full lifecycle, posts to bus

Session N+5:  Phase 6 (colony: multi-rod + reactor)
              TEST: 2+ rods coordinate via bus, comms_operator routes

Session N+6:  Owner task validation (all 4 tasks from O.9)
              Ablation: unicore vs colony comparison
```

---

## Key Decisions for Next Session

1. **WebSocket or SSE for browser observation?**
   - SSE is simpler (unidirectional push), stdlib compatible
   - WebSocket needed if browser must send commands (pause/step) back
   - Recommendation: SSE for push + regular POST for commands

2. **Planner output format?**
   - Option A: JSON `{steps: [{description, done_when}]}` (structured)
   - Option B: Numbered text list (simpler for small LLM)
   - Recommendation: JSON, same as all other nodes

3. **Where does state persist between server restarts?**
   - Option A: In-memory only (current — lost on restart)
   - Option B: `runtime/state.json` written each cycle
   - Recommendation: B, with state node that auto-saves

4. **Wiring topology file stays single?**
   - Yes. Add nodes/edges to existing wiring.json
   - The topology grows from 11 → ~20 nodes as features add
   - HTML editor handles any size

---

## Files to Create (Next Session)

```
prompts/planner.txt     — planning prompt (goal → steps)
prompts/verifier.txt    — verification prompt (screen → confirmed/denied)
prompts/reflector.txt   — diagnosis prompt (failure → suggestion)
```

## Files to Modify (Next Session)

```
server.py              — add: autonomous loop, planner/scheduler/verifier/reflector nodes
                         add: SSE endpoint for browser observation
                         add: --run mode
prompts/wiring.json    — add: planner, scheduler, verifier, reflector nodes + edges
wiring-editor.html     — add: SSE listener for live autonomous observation
```

---

## Non-Negotiable Constraints

- **Python stdlib only** — no pip install, no requirements.txt
- **Wiring-first** — all control flow in wiring.json, Python is dumb executor
- **Browser is dashboard, not brain** — system must run without browser
- **Single HTML file** — no build step, CDN imports only
- **CRLF line endings** — Windows workspace
- **LM Studio local** — no cloud API keys
- **Part 1.0 doctrine** — unconstrained, real work, production organism
- **Prove by ablation** — colony only if it beats unicore

---

## Success Criteria for "One Complete Rod"

A rod is complete when ALL are true:

- [ ] `python server.py --run "open notepad and write hello"` executes without browser
- [ ] System plans: "1. open run dialog 2. type notepad 3. press enter 4. write hello"
- [ ] System executes each step, observing screen between steps
- [ ] System verifies: "is notepad open with hello written?"
- [ ] On failure: system diagnoses why and retries (up to max_attempts)
- [ ] On success: system enters satisfied state (slow metabolism)
- [ ] Pressure builds if stuck (stagnation score visible)
- [ ] Browser can connect to observe live state at any time
- [ ] All behavior defined in wiring.json (add nodes ≠ add Python if/else)
- [ ] Another rod = same server.py + different persona in wiring.json
