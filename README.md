# endgame-ai

A local computer becomes a living organism. No cloud. No API keys. No programming required to use it. A 4-billion parameter model running on consumer hardware plans, observes, acts, verifies, reflects, and evolves its own wiring — working for hours or days on complex goals the way a human works at a desktop.

This is not a chatbot with tools. Not a react agent. Not a copilot. It is a self-rewiring autonomous organism that turns any Windows PC into a thinking machine.

## Why This Exists

Every AI agent today requires: cloud APIs, programming skills to configure, RAG pipelines, tool definitions, prompt engineering per task, and constant human oversight. endgame-ai requires: one local model, one Python file, one JSON brain. The human says "install VirtualBox, create an Ubuntu VM, configure NAT networking" and walks away. The organism plans, executes, handles failures, replans, and evolves.

When this project is complete — when Python is purely mechanical and wiring.json fully governs behavior — the system becomes a true endgame: any person with a computer can have an autonomous digital worker that improves itself through experience. No programming. No cloud dependency. No per-token billing. The model runs locally, the reasoning stays local, the evolution stays local.

## Architecture: ROD (Reason → Observe → Decide)

```
Python = mechanical body (probe screen, execute verbs, validate, hot-reload)
prompts/wiring.json = mutable brain (topology, prompts, guards, limits, filters)
Local LLM = semantic judgment (plans, decides, verifies, reflects, evolves)
```

### The Closed Loop

```
goal_inbox → planner → scheduler → observe → act → verify → scheduler (loop)
                                                      ↓ fail
                                                    reflect → retry | replan | escalate
                                                                                  ↓
                                                                            self_modify
                                                                                  ↓
                                                                          planner (evolved)
```

For a goal like "install software X, configure it, verify it works":
1. Planner decomposes into 8-10 ordered steps with completion criteria
2. Each step cycles: observe screen → decide action → execute → verify outcome
3. If verify denies: reflect diagnoses → retry (different approach) or replan (different decomposition)
4. If replans exhausted: escalate to self_modify → organism evolves its own wiring
5. After mutation: restart with evolved brain — new prompts, guards, observation config
6. This continues for hours until the goal is satisfied or limits hit

The organism is designed for **sustained autonomous operation** — not single-shot requests.

## The Two-Pass Reasoning Loop

The core innovation. Every LLM node executes two passes:

```
PASS 1: [system + user] → LLM
  Model thinks internally: <think>reasoning</think>
  Model outputs: content (often contains the answer)
  Python captures: reasoning_content (the model's internal deliberation)

PASS 2: [system + user + reasoning_from_pass_1 + "DECIDE NOW"] → LLM
  Model sees its OWN prior reasoning as input
  Model self-corrects: catches errors, fixes targets, confirms logic
  Model outputs: final JSON decision
```

This creates **self-critique between impulse and commitment**. The model's first instinct (pass 1) is fed back to it for review (pass 2). Empirically proven: pass 2 caught a bug where pass 1 emitted `press target=""` and pass 2 corrected it to `press target="enter"`. Without this, the action would have failed, triggering a 120s+ retry cycle.

The reasoning propagates between nodes via the reasoning chain — planner's thoughts inform reflect, reflect's thoughts inform self_modify. This is the organism's memory of WHY it made each decision.

## Observation: Single-Pass Full-Screen Probe

The organism sees through cursor-based hover probing:

1. Cursor moves across entire screen in a grid (70px steps, 405 points)
2. At each point: Win32 `SetCursorPos` + UIA `ElementFromPoint`
3. Elements are deduplicated, classified by scope, rendered to SCREEN text
4. SCREEN is the sole input to the act circuit (~4-6KB, ~1200 tokens)

Why hover probe is primary (not UIA tree walking):
- Captures custom-rendered web elements invisible to UIA
- Sees hover-only tooltips and dynamic menus
- Works on any framework (Electron, WPF, Win32, web)
- Sees what a human would see, not what accessibility APIs expose

Current performance: 405 probe points in ~2-3 seconds. Negligible vs LLM time.

## Verify Preflight: Mechanical Intelligence

Before calling the LLM for verification, Python checks structural patterns:

| Pattern | Logic | Saves |
| --- | --- | --- |
| Win+R → write → Enter | App launch via Run dialog | ~120s |
| Focus browser → Ctrl+L → write → Enter | URL navigation | ~120s |
| Typed text + editor focused | Write-to-editor | ~120s |
| All actions are `remember` | No side effect, data captured | ~120s |
| Ctrl+S + done_when mentions "save" | File save | ~120s |
| Focus + target matches done_when | Window switch | ~120s |

Each pattern eliminates 2 LLM calls. For a 10-step goal where 8 steps match patterns: **16 minutes saved**. This is the highest-leverage optimization in the system — adding patterns is cheaper than faster hardware.

## Self-Rewiring

When the organism fails repeatedly (retries exhausted, replans exhausted), it escalates:

```
reflect → "I cannot solve this with current wiring" → self_modify
self_modify → LLM emits a validated wiring_patch → Python validates → backup → write → hot-reload
```

Patch operations: `set_observe`, `set_limit`, `set_guard`, `append_role_rule`, `set_prompt_base`, `set_role`, `set_reasoning`, `add_node`, `update_node`, `remove_node`, `add_edge`, `remove_edge`.

The organism can:
- Adjust observation depth when SCREEN is too noisy or too sparse
- Add rules to its own prompts when it keeps making the same mistake
- Change retry limits when tasks need more patience
- Restructure its own topology when the graph flow is wrong

Every mutation is validated against schema, backed up, and hot-reloaded. The organism cannot corrupt itself.

## Measured Performance

Source: LM Studio server log, nvidia-nemotron-3-nano-4b Q6_K_XL, single GPU.

| Metric | Value | Implication |
| --- | --- | --- |
| Generation speed | 6.14 tok/s | **THE WALL** — hardware bound |
| Prompt eval (cached) | 50-170 tok/s | Fast when cache hits |
| Prompt eval (cold) | 60-80 tok/s | One-time cost per circuit switch |
| Avg reasoning/call | 13-240 tokens | Model thinks proportionally to complexity |
| Avg content/call | 37-109 tokens | Compact JSON decisions |
| Two-pass per node | 40-156s | Depends on prompt size and output length |
| Verify preflight | <1s | Structural patterns eliminate LLM entirely |
| Observation | ~3s | Single-pass hover probe |
| Simple goal (1 step) | ~3.5 min | Planner + act + verify(preflight) |
| 5-step goal (estimated) | ~12 min | With preflight on most steps |
| 5-step goal (no preflight) | ~20 min | Every verify needs LLM |

### Where Time Goes (from log truth)

```
Generation (output tokens):     69%  ← HARDWARE LIMIT, cannot optimize
Prompt eval (input processing): 24%  ← Benefits from cache, mostly good
Non-LLM (observe, routing):      7%  ← Already negligible
```

The only software levers: reduce how many times we hit the LLM (verify preflight), reduce output tokens (tighter prompts), prevent failed actions (better guards).

## File Map

| File | Purpose |
| --- | --- |
| `server.py` | HTTP API, ROD graph runner, node handlers, two-pass LLM, prompt assembly, self-modify engine |
| `desktop.py` | Win32/UIA observation, single-pass hover probe, SCREEN rendering, scope classification |
| `actions.py` | Data-driven verb dispatch: click, write, press, hotkey, scroll, focus, remember, wait |
| `colony.py` | Multi-slot colony manager (future: parallel organisms) |
| `wiring-editor.html` | Zero-dependency Canvas2D workbench for live monitoring |
| `prompts/wiring.json` | The mutable brain — all semantic behavior lives here |
| `prompts/wiring-schema.json` | JSON Schema for wiring validation |
| `prompts/model.json` | LM Studio connection config |

## Runbook

```powershell
# Start
python "C:\path\to\endgame-ai\server.py"

# Stop
Get-NetTCPConnection -LocalPort 9078 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }

# Hot-reload wiring after edits
Invoke-WebRequest -Method Post -Uri 'http://127.0.0.1:9078/wiring' -InFile 'prompts\wiring.json' -ContentType 'application/json'

# Verify
python -m compileall -q .
GET http://127.0.0.1:9078/health
```

## Non-Negotiable Constraints

- Python is mechanical. It never interprets tasks semantically.
- Wiring is semantic. All behavior changes go through prompts/guards.
- Do not reintroduce prompt truncation.
- Do not reintroduce parse_fallback.
- Do not add site-specific or task-specific Python branches.
- Do not hide errors with except/pass.
- Do not remove or weaken the two-pass reasoning loop.
- Validate wiring after every mutation.
- Commit every coherent verified batch.

## Evolution Path

**Now (v1)**: Single organism, sequential ROD loop, proven capabilities
- Plans, observes, acts, verifies, reflects, self-modifies
- 6 verify preflight patterns, single-pass observation, render filters
- First autonomous goals completed

**Next (v1.x)**: Reliability and efficiency
- More verify preflight patterns (discovered from real multi-step runs)
- Tighter prompts (model reasons less redundantly, same quality)
- Better guards (prevent repeat actions, prevent impossible targets)
- Trace-based learning (successful goal traces inform future planning)

**Future (v2)**: Colony
- Multiple organisms sharing a bus, parallel execution
- Specialized slots (browser worker, file system worker, installer worker)
- Cross-organism teaching through shared wiring patches
- Pipeline parallelism (observe next step while acting on current)

**Endgame**: Any person with a computer runs a local organism that handles complex digital work — installs software, configures systems, manages files, interacts with services — autonomously, privately, without programming skills or cloud dependencies.

## Handover Session Prompt

```text
You are continuing endgame-ai — a self-rewiring autonomous desktop organism.

=== WHAT THIS IS ===

A local Windows PC becomes a living organism. A 4B parameter LLM runs locally
(LM Studio) and drives a closed ROD loop (Reason → Observe → Decide) that can
plan multi-step goals, observe the screen, execute desktop actions, verify
outcomes, reflect on failures, and self-modify its own wiring topology.

This is NOT a react agent. NOT a chatbot with tools. It is a persistent
reasoning loop designed to work for hours or days on complex goals: installing
software, configuring systems, interacting with web services, managing files.
The human provides a goal and walks away.

The endgame vision: any person with a computer can have an autonomous digital
worker. No programming. No cloud. No per-token billing. Local model, local
reasoning, local evolution. When Python is purely mechanical and wiring.json
fully governs behavior, the system becomes model-agnostic — swap in any local
LLM and the organism works.

=== ARCHITECTURE ===

Python (server.py, desktop.py, actions.py) = mechanical body.
  Probes screen, executes verbs, validates patches, hot-reloads wiring.
  NEVER interprets tasks semantically. Pure mechanical infrastructure.

prompts/wiring.json = mutable brain.
  Topology (graph nodes + edges + signals), prompts (base + roles),
  guards, limits, observe config, reasoning config, verbs config.
  ALL semantic behavior lives here. This is what self_modify mutates.

Local LLM (via LM Studio at localhost:1234) = judgment.
  Plans, decides actions, verifies, reflects, proposes wiring patches.
  Currently: nvidia-nemotron-3-nano-4b (4B params, Q6, runs on any GPU).

=== THE TWO-PASS REASONING LOOP (CORE — DO NOT REMOVE) ===

Every LLM node executes:
  Pass 1: system + user → model produces <think>reasoning</think>content
  Pass 2: system + user + reasoning_from_pass_1 + "DECIDE NOW" → final JSON

This creates self-critique. Pass 1 is impulse, pass 2 is commitment with
review. Proven: pass 2 caught real bugs that would have caused failures.
The reasoning propagates between nodes (planner → act → verify → reflect)
via the reasoning chain — the organism's memory of WHY.

=== ROD LOOP ===

goal → planner → [scheduler → bus_check → observe → act → verify] loop
                                                         ↓ fail
                                                       reflect → retry | replan | escalate → self_modify

Nodes: planner (decompose), observe (screen probe), act (decide+execute),
       verify (confirm/deny), reflect (diagnose), self_modify (evolve wiring)

=== OBSERVATION ===

Single full-screen hover probe: cursor grid at 70px step (405 points, ~3s).
SetCursorPos + ElementFromPoint at each point. Captures everything visible
regardless of framework. SCREEN rendered as text with [ID] targets (~4-6KB).
This is the act circuit's sole visual input.

Config in wiring.json "observe" section:
  hover_scan_step_px: 70 (grid density)
  render_class_name: false (suppress CSS class noise)
  render_automation_id: true (keep short UIDs)
  render_window_per_element: false (window shown in header only)
  desktop_tree_enabled: false (disabled, model works without)

=== VERIFY PREFLIGHT ===

Mechanical Python guards that confirm/deny without LLM — highest leverage
optimization. Each pattern saves 100-180s (2 LLM calls eliminated).
Current patterns: Win+R launch, browser navigation, write-to-editor,
remember (no side effect), Ctrl+S save, focus-matches-done_when.

Adding more structural patterns is the #1 efficiency lever.

=== MEASURED PERFORMANCE (GROUND TRUTH FROM LM STUDIO LOG) ===

Generation: 6.14 tok/s (HARDWARE WALL — cannot improve in software)
Prompt eval: 50-170 tok/s (cache-dependent)
Single-step goal: ~3.5 min (planner two-pass + act two-pass + verify preflight)
5-step goal: ~12 min (with preflight on most steps)

Where time goes: 69% generation (hardware), 24% prompt eval, 7% non-LLM.
The ONLY software levers: fewer LLM calls (preflight), fewer output tokens
(tighter prompts), fewer retries (better guards/prompts).

=== SELF-MODIFY ===

When retries+replans exhausted: reflect escalates to self_modify.
LLM emits a wiring_patch (validated JSON operation). Python validates
against schema, creates timestamped backup, writes new wiring, hot-reloads.
Operations: set_observe, set_limit, set_guard, append_role_rule,
set_prompt_base, set_role, set_reasoning, add/update/remove node/edge.
The organism cannot corrupt itself — validation prevents invalid mutations.

=== NON-NEGOTIABLES ===

- Python = mechanical. Wiring = semantic. Never cross this boundary.
- Do NOT reintroduce prompt truncation or parse_fallback.
- Do NOT add task-specific or site-specific Python branches.
- Do NOT hide errors with except/pass.
- Do NOT remove or weaken the two-pass reasoning loop.
- Do NOT optimize for trivial goals — the system runs complex multi-day tasks.
- Validate wiring after every mutation. Hot-reload with absolute path.
- Commit every coherent verified batch.
- Changes must be GENERIC — if it names one app/site, it's wrong.

=== WHAT TO WORK ON (priority order) ===

1. VERIFY PREFLIGHT COVERAGE — Run real multi-step goals, observe which
   verify calls go to LLM, add structural patterns for those cases.
   Each pattern = 100-180s saved per occurrence. Target: 80% coverage.

2. PROMPT PRECISION — Analyze reasoning tokens in LM Studio logs.
   Where the model re-derives rules from the system prompt, make the
   prompt more decisive so the model reasons less redundantly.
   Lever: 50-90 fewer tokens per call × 163ms each.

3. RELIABILITY — Run complex goals (install software, configure systems).
   When the model makes wrong actions, fix via prompts/guards in wiring.
   Every prevented retry = 300s+ saved. Better than faster pipeline.

4. TRACE LEARNING — Completed goal traces (prompts/traces.jsonl) inform
   future planning via few-shot context. More traces = better first plans.

=== HOW TO DIAGNOSE ===

The LM Studio server log is GROUND TRUTH:
  %USERPROFILE%\.cache\lm-studio\server-logs\<year-month>\<date>.log

It contains: full request bodies (system + user messages), full responses
(content + reasoning_content + token counts + timing). Map each request
to its pipeline node by matching system prompt role and user content.

Key metrics per call:
  - prompt_tokens: how large was the input
  - reasoning_tokens: how much the model thought
  - completion_tokens - reasoning_tokens: actual output size
  - total_time: wall clock for that call
  - tg (tokens generated per second): generation speed

If a goal fails or is slow:
  - Read the log, find which node produced wrong output
  - If wrong action → fix act prompt in wiring
  - If wrong plan → fix planner prompt in wiring
  - If wasted verify calls → add preflight pattern in server.py
  - If observation missed elements → tune observe config in wiring
  - NEVER add task-specific Python code

=== ENDPOINTS ===

GET  /health     — status + capabilities
GET  /wiring     — current brain
GET  /state      — persisted run state
GET  /events     — SSE live stream
POST /run        — start autonomous goal
POST /step       — execute one graph node
POST /pause      — pause running goal
POST /resume     — resume from saved state
POST /wiring     — validate + hot-reload wiring (JSON body)
POST /node/{id}  — direct node execution

=== FIRST ACTIONS ===

1. git status, python -m compileall, JSON parse check, /health
2. Read this README fully — it IS the architecture document
3. Pick a multi-step goal, run it, observe behavior
4. Read LM Studio log for that run — full forensics
5. Identify highest-leverage improvement (usually: more preflight patterns
   or tighter prompts to reduce wasted reasoning)
6. Implement, test with a goal, verify, commit, update README
```
