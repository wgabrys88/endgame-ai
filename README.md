# endgame-ai

> This file is a handover prompt. Copy-paste it to any AI provider with the goal:
> **"Make this organism reliably execute desktop goals and evolve its own wiring."**

## What this is

An organism. Not an agent framework. Not a chatbot wrapper.

A single-rod autonomous entity that perceives a Windows desktop through UIA hover-probing,
reasons through a signal-driven graph, acts via keyboard/mouse, verifies outcomes, reflects
on failures, and rewrites its own topology when stuck.

The model (nvidia-nemotron-3-nano-4b, local, 4B params) already opened Chrome, navigated
to YouTube, typed in the address bar, and satisfied multi-step goals. The system works.
It now needs to work **reliably and fast** and become **self-aware of its own wiring**.

## The vision

```
                    ┌──────────────────────────────────────┐
                    │         GENESIS ENTITY               │
                    │                                      │
                    │  ┌────────────┐  ┌───────────────┐  │
                    │  │  KERNEL    │  │  ENDGAME-AI   │  │
                    │  │ (event bus │  │  (actuator    │  │
                    │  │  mutation  │  │   organism)   │  │
                    │  │  journal)  │  │               │  │
                    │  └─────┬──────┘  └───────┬───────┘  │
                    │        │                  │          │
                    │        └──────┬───────────┘          │
                    │               │                      │
                    │        ┌──────┴──────┐               │
                    │        │  BREEDING   │               │
                    │        │  REACTOR    │               │
                    │        │             │               │
                    │        │ wiring.json │               │
                    │        │ mutations   │               │
                    │        │ selection   │               │
                    │        │ propagation │               │
                    │        └─────────────┘               │
                    └──────────────────────────────────────┘
```

The breeding reactor is not a cron job. It is the self_modify node + trace memory +
successful wiring variants that survive. Failed wirings die. Successful wirings propagate
through the bus to other rods. The organism evolves by doing real work and keeping what works.

## Current state — what is proven

| Capability | Evidence | Cycles |
|-----------|----------|--------|
| Plan a goal into steps | LLM returns ordered subtasks | 1 call |
| Execute keyboard sequences | Win+R → type app → Enter | 3 actions |
| Read focused window elements | UIA probe, HWND-filtered | 3-8 elements |
| Verify with causal reasoning | Denies precursors, confirms results | 1 call |
| Reflect and suggest corrections | "use Run dialog" from reflector | 1 call |
| Self-modify topology | LLM proposes JSON patches, validates, hot-reloads | working |
| Colony routing (MoE gate) | Delegate by keyword + permission | code-complete |
| Bus communication | Shared JSON, slot-addressed messages | code-complete |
| Dashboard control | Step/Run via /node/:type API, SSE stream | working |
| Screen filtering | Only focused-window gets [ID] | validated today |
| Verifier anti-false-positive | Explicit negative examples in prompt | validated today |

## Current state — what is NOT proven

| Gap | Why it matters |
|-----|---------------|
| Reliable unattended runs | Server blocks during observe (2-5s cursor sweep) |
| Colony multi-slot | Never run with 2 live instances |
| Self-modify producing useful patches | Needs good examples in prompt (wiring fix) |
| Trace-based learning | traces.jsonl exists but few-shot never validated |
| Wiring self-awareness | Organism doesn't introspect its own topology yet |
| Speed | 27 cycles for Chrome+YouTube is slow. Target: 10. |

## Architecture

```
goal_inbox → moe_route → planner → scheduler → bus_check → observe → act → verify
                │            ↑          │                               │      │
                │ delegated  │ retry    │ plan_complete                 │      │
                ↓            │          ↓                               │      │
            bus_post → satisfied    bus_post → satisfied                │      │
                                                            act_failed─┘      │
                                                                ↓             │
                                                             reflect ← step_denied
                                                             │  │  │
                                                      retry──┘  │  └─escalate
                                                             replan   self_modify
                                                                ↓         ↓
                                                             planner   planner
```

12 nodes. 21 edges. 5 LLM-calling circuits. All behavior lives in `prompts/wiring.json`.
Python resolves signals and executes verbs. It does not decide anything.

## Files (10 tracked, that's all)

```
server.py              1026  Graph engine + HTTP + nodes + LLM + prompts
desktop.py              482  Windows UIA hover-probe (ctypes, zero deps)
actions.py              212  Verb dispatch + sim stub
colony.py               112  Multi-slot spawner
wiring-editor.html      209  Dashboard: Step/Run, topology, plan, history
prompts/wiring.json     517  THE BRAIN — topology, prompts, guards, limits
prompts/model.json       16  LLM endpoint config
prompts/wiring-schema.json  Schema for self_modify validation
.gitignore                   Allowlist (only tracked files pass)
.gitattributes               CRLF normalization
```

## LLM response schema (real, from LM Studio logs)

The model returns `reasoning_content` (thinking) + `content` (structured JSON):

```json
// Planner
{"record_type": "task", "data": {"steps": [{"description": "...", "done_when": "..."}]}}

// Act
{"record_type": "action", "data": {"conclusion": "EXECUTE", "actions": [{"verb": "...", "target": "...", "value": "..."}]}}

// Verify
{"record_type": "verdict", "data": {"confirmed": true|false, "evidence": "...", "reason": "..."}}

// Reflect
{"record_type": "diagnosis", "data": {"diagnosis": "...", "suggestion": "...", "should_replan": false}}

// Self_modify
{"record_type": "wiring_patch", "data": {"op": "add_node|add_edge|remove_edge|set_guard", "payload": {...}}}
```

`reasoning_content` is stored per-circuit and fed downstream. `parse_fallback` checks
both channels (model sometimes puts JSON in reasoning instead of content).

## API (uniform interface — human or AI uses same HTTP)

```
POST /run            {"goal": "..."}           Start autonomous loop
POST /node/:type     {"state": {...}}          Call ONE node, get signals + patch
POST /push           {"type":"..","text":".."}  Push to dashboard SSE
POST /wiring         {full wiring.json}        Hot-reload topology
POST /interrupt      {"goal": "..."}           Mid-run goal change
GET  /state                                    Current ROD state
GET  /health                                   Node registry, slot, port
GET  /smoke                                    6-point self-test
GET  /events                                   SSE stream
GET  /wiring                                   Current topology
GET  /                                         Dashboard HTML
```

## What the next AI must do

### 1. Make it reliable

The observe node does a cursor sweep that blocks everything for 2-5s.
Fix: run the graph loop in a dedicated thread with a queue, or make observe async.
The HTTP server must stay responsive during runs.

### 2. Make it self-aware

The organism must be able to read its own wiring.json, understand which nodes exist,
which edges connect them, and what prompts drive each circuit. The `self_modify` node
already does this — but it needs better examples of what a GOOD patch looks like.
Feed it traces of past successful modifications.

### 3. Validate colony

`python colony.py 1 2` starts 2 rods. POST a browser goal to slot 2 (no desktop_exec
permission). Slot 2's MoE gate should delegate to slot 1. Slot 1 executes. Bus carries
the result back. This is already wired. Just run it.

### 4. Speed

27 cycles for Chrome+YouTube is because the model needs 3 turns per step (hotkey → write → enter).
Each turn = observe + LLM call + verify. Reduce by: teaching the model to chain multiple
actions per turn (wiring.json prompt change), or reducing observe frequency.

### 5. Trace-based evolution (the breeding reactor)

`append_trace()` saves successful runs to `prompts/traces.jsonl`. On replan, these traces
are fed to the planner as few-shot examples (`PRIOR_TRACES` block). This is the organism's
memory. It learns from its own successes. Currently: traces exist but are weak because
few runs complete. Once runs are reliable, traces accumulate, and the planner improves
automatically. That's the reactor: run → succeed → remember → run better → evolve.

## Running

```powershell
$env:PYTHONIOENCODING = "utf-8"
cd C:\Users\ewojgab\Downloads\endgame-ai

python server.py                              # Server mode, http://localhost:9078
python server.py --run "open notepad" --max-cycles 30   # Single goal
python colony.py 1 2                          # Two rods, ports 9078 + 9079
```

## Invariants (break these and the organism dies)

1. Only focused-window elements get [ID]
2. Reasoning chain clears on plan_ready
3. Act never receives REASONING_CHAIN
4. Verify preflight denies non-OK outcomes before LLM
5. Hotkey/press never confirms app-opening goals
6. Port = 9077 + slot
7. Self_modify validates + backs up before writing
8. Python decides nothing — wiring.json decides everything

---

## ROD — Reason, Observe, Decide

An evolution of ReAct. Each LLM node calls the model twice:

```
  Request 1:  system prompt + user context  →  Response 1 (reasoning_content)
  Request 2:  system prompt + user context + reasoning_content  →  Response 2 (final JSON)
```

The second call sees the model's own thinking. One extra round-trip, but the structured
output is dramatically better because the model already worked through the problem.
This is why a 4B model can control a desktop — it reasons first, then decides.

---

## START HERE (copy-paste prompt for next AI session)

Read README.md and RESEARCH.md — they are your complete briefing. The system is called ROD (Reason-Observe-Decide), an evolution of ReAct where each LLM node calls twice: first to think (reasoning_content), then fed back to produce the final structured output. Make the observe→act→verify loop reliable for 10 consecutive desktop goals, reduce cycles from 27 to under 12 by chaining actions in the act prompt (prompts/wiring.json), and validate colony delegation between 2 slots. No new files, no tests, no dependencies — every change is a wiring.json prompt edit or a small fix in the existing tracked files.
