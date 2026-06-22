# endgame-ai

A self-rewiring autonomous desktop organism. Not a react agent. Not a chatbot with tools. A persistent reasoning loop that observes, plans, acts, verifies, reflects, and evolves its own wiring over days-long sessions.

The system will install software, configure virtual machines, interact with web services, handle multi-hour tasks, replan when reality changes, and self-modify its own topology when its current design fails. The organism operates continuously — like a human at a desktop — not per-request.

Last verified: 2026-06-22.

## What ROD Is

ROD = Reason → Observe → Decide. A closed-loop cognitive architecture where:

- **Python** is the mechanical body: probes the screen, executes verbs, validates patches, hot-reloads wiring. Python never interprets tasks semantically.
- **prompts/wiring.json** is the mutable brain: topology, prompts, guards, limits, observation config. This is where semantic behavior lives.
- **Local 4B LLM** provides judgment: plans multi-step goals, chooses actions from observation, verifies outcomes, reflects on failure, and proposes structural self-modifications.
- **wiring-editor.html** is the live workbench: graph, state, SCREEN, SSE.

The two-pass LLM call is core: pass 1 generates internal reasoning (via native `<think>` tags captured as `reasoning_content`), then pass 2 receives that reasoning back and emits the final decision JSON. This creates a feedback loop where the model critiques its own first impulse before committing. The reasoning propagates between nodes — planner's thoughts inform act, act's thoughts inform verify, verify's thoughts inform reflect.

## ROD Loop

```
goal_inbox → moe_route → planner → scheduler → bus_check → observe → act → verify → scheduler
                                                                               ↓ fail
                                                                             reflect → retry | replan | escalate
                                                                                                          ↓
                                                                                                    self_modify
```

This is not a simple plan-execute-done flow. For a complex goal like "install VirtualBox, create a VM, configure networking":
1. Planner decomposes into 8-10 steps
2. Each step cycles through observe → act → verify
3. If verify denies (action didn't achieve intent), reflect decides: retry (same approach), replan (decompose differently), or escalate (self_modify the wiring)
4. Self_modify can add guards, change prompts, adjust observation depth, restructure topology
5. After mutation, the whole loop restarts with evolved wiring

The organism is expected to run for hours, replan multiple times, and evolve its own behavior mid-task.

## File Map

| File | LOC | Purpose |
| --- | ---: | --- |
| `server.py` | ~2100 | HTTP API, ROD graph runner, node handlers, prompt assembly, two-pass LLM, self-modify patch engine, validation |
| `desktop.py` | ~1500 | Win32/UIA observation, single-pass hover probe, element classification, SCREEN rendering |
| `actions.py` | ~250 | Data-driven verb dispatch (click, write, press, hotkey, scroll, focus, remember, wait) |
| `colony.py` | ~90 | Multi-slot colony manager (future: parallel organisms sharing bus) |
| `wiring-editor.html` | ~280 | Zero-dependency Canvas2D workbench |
| `prompts/wiring.json` | - | The brain: topology, prompts, guards, limits, observe config |
| `prompts/wiring-schema.json` | - | JSON Schema for wiring validation |
| `prompts/model.json` | - | LM Studio connection parameters |

## The Two-Pass Reasoning Loop

Every LLM node (planner, act, verify, reflect, self_modify) executes:

```
┌─────────────────────────────────────────────────────────────────┐
│ PASS 1: system + user → LLM                                    │
│   Model: <think>reasoning_content</think>content                │
│   Python captures reasoning_content                             │
│                                                                 │
│ PASS 2: system + user + ROD_REASONING_CONTENT + "DECIDE NOW"   │
│   Model: <think>brief</think>final JSON                         │
│   Python parses JSON from content                               │
│                                                                 │
│ Reasoning stored in state.reasoning[circuit] → propagates       │
│ to downstream nodes via reasoning_chain                         │
└─────────────────────────────────────────────────────────────────┘
```

This is not overhead. This is the organism thinking before committing. The reasoning chain is the organism's memory of WHY it made each decision — critical for reflect and self_modify to diagnose failures.

### Measured Performance (4B Nemotron Q6, single GPU)

| Metric | Value |
| --- | --- |
| Prompt eval (cached) | 50-170 tok/s |
| Prompt eval (cold) | 60-80 tok/s |
| Generation | 6.0-6.4 tok/s |
| Reasoning tokens/call | 13-240 |
| Content tokens/call | 37-109 |
| Per-node wall time | 12-90s |
| Full single-step goal | ~3.5 min |

The hard constraint is **6.14 tok/s generation speed**. Everything else (prompt eval, observation, routing) is negligible by comparison.

## Observation Pipeline

Single full-screen hover probe (primary observation method):

1. Cursor moves across screen at configurable step size (default 70px)
2. At each point: `SetCursorPos` + `IUIAutomation::ElementFromPoint`
3. Elements are deduplicated, classified by scope, and rendered to SCREEN text
4. SCREEN is the only input to the act circuit

```
Current config:
- hover_scan_step_px: 70  (was 40, now 3x fewer points)
- Single pass: 405 probe points covers full 1920x1080
- UIA is secondary enrichment for modern apps and web content
- SCREEN size: ~4-6KB depending on active window complexity
```

### Why Hover Scan is Primary

UIA tree walking misses:
- Custom-rendered web elements (Canvas, WebGL, React portals)
- Hover-only tooltips and dynamic menus
- Elements inside embedded frames not exposed to UIA
- Modern Electron/Chromium content that exposes minimal UIA nodes

The cursor probe via `ElementFromPoint` captures what's VISUALLY there, regardless of framework. UIA enriches with accessibility metadata. Together they form complete observation.

## Prompt Architecture

All prompts live in `wiring.json` under `prompts.base` and `prompts.roles.*`. System prompts are assembled at runtime by combining base + role for the active circuit.

### Current Budget

| Prompt | Chars | Purpose |
| --- | ---: | --- |
| base | 863 | Shared context: what ROD is, runtime facts |
| planner | 972 | Goal → subtasks decomposition |
| unified (act) | 1724 | SCREEN → deterministic verb chain |
| verifier | 974 | Evidence → confirmed/denied |
| reflector | 834 | Failure → retry/replan/escalate |
| self_modify | 1648 | Diagnosis → validated wiring_patch |

### Prompt Rules

- Every role specifies exact JSON output schema
- No prose in model output (content = JSON only)
- Task semantics in prompts/guards, never in Python
- `<think>` content is for the model's own reasoning, never parsed as output

## Self-Rewiring

When reflect escalates (retries exhausted, replans exhausted):

```
reflect → escalate signal → self_modify node → LLM emits wiring_patch → validate → backup → write → hot-reload → planner (restart with evolved brain)
```

### Patch Operations

```
set_observe       — tune observation (step size, depth, filters)
set_limit         — adjust numeric caps (attempts, replans, cycles)
set_guard         — add/change behavioral guards
append_role_rule  — add rule to a prompt role
set_prompt_base   — modify shared system prompt
set_role          — replace a role prompt entirely
set_reasoning     — tune reasoning config
add_node / update_node / remove_node — topology changes
add_edge / remove_edge — signal routing
```

### What Self-Modify Is For

- "Observation is too noisy" → `set_observe` render filters
- "Keep retrying the same wrong approach" → `append_role_rule` or `set_guard`
- "Need more attempts before giving up" → `set_limit`
- "Wrong node handles this signal" → topology edits

Self-modify is the organism's adaptation mechanism. It doesn't solve tasks — it evolves the organism's capability to solve future tasks.

## Verify Preflight Guards

Before calling the LLM for verification, mechanical Python guards check for structurally unambiguous outcomes:

- `hotkey win+r → write → press enter` → confirmed (app launch pattern)
- `focus browser → ctrl+l → write URL → enter` → confirmed (navigation)
- `typed text + editor focused` → confirmed (write-to-editor)
- Outcome doesn't start with "OK:" → denied (action failed mechanically)

These guards save ~30-60s per step by avoiding unnecessary LLM calls for obvious outcomes. They are generic patterns, not task-specific.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Status, capabilities, self_modify_ops |
| GET | /wiring | Current wiring |
| GET | /state | Persisted run state |
| GET | /events | SSE live stream |
| POST | /run | Start autonomous goal |
| POST | /step | Execute one graph node |
| POST | /resume | Resume saved state |
| POST | /pause | Pause running goal |
| POST | /wiring | Validate and hot-reload wiring |
| POST | /node/{type} | Direct node execution |
| POST | /interrupt | Inject goal into running loop |

## LLM Configuration

```json
{
  "host": "http://localhost:1234",
  "model": "nvidia-nemotron-3-nano-4b",
  "temperature": 0.3,
  "temperature_bump": 0.15,
  "timeout": 900,
  "max_tokens": 2048
}
```

LM Studio with prompt caching enabled. Context window: 16384 tokens. Single slot. The `temperature_bump` adds 0.15 per parse retry to escape local optima.

## Proven Capabilities

- [x] Full ROD loop: plan → observe → act → verify → satisfied
- [x] Two-pass reasoning with inter-node propagation
- [x] Self-modify cycle: LLM emits wiring_patch → validate → backup → hot-reload
- [x] Single-pass full-screen observation (405 points, ~4-6KB SCREEN)
- [x] Verify preflight for structurally obvious outcomes
- [x] Render filters: 37KB → 6KB SCREEN (83% reduction)
- [x] Compact prompts for 4B model (~7KB total)
- [x] SIGINT/SIGTERM state persistence and resume
- [x] Colony multi-slot architecture (implemented)

## Current Limitations

- Generation speed: 6.14 tok/s hard limit (hardware-bound)
- Single-step goals take ~3.5 min (two-pass × 2 nodes)
- Complex multi-step goals will take proportionally longer
- Model typed "hello" instead of "hello from endgame" (verifier too lenient)
- `server.py` is 84KB (graph runtime + HTTP + prompt plumbing in one file)
- No formal test suite

## Non-Negotiable Constraints

- Do not reintroduce SCREEN prompt truncation
- Do not reintroduce `parse_fallback`
- Do not add site-specific or task-specific Python branches
- Do not hide errors with `except/pass`
- Python = mechanical. Wiring = semantic.
- Validate and hot-reload wiring after mutations
- Commit every coherent verified batch
- Do not remove or weaken the two-pass reasoning loop

## Handover Session Prompt

```text
You are continuing endgame-ai in C:\Users\px-wjt\Downloads\endgame-ai.

Read README.md first. Treat it as the source of truth unless /health or code proves it stale.

This is a ROD organism (Reason → Observe → Decide), not a react agent. The two-pass
reasoning loop is CORE — pass 1 generates reasoning, pass 2 receives it back and
decides. This creates self-critique between impulse and commitment. Do NOT propose
removing it. The reasoning chain propagates between nodes and is the organism's
memory of WHY decisions were made.

Current reality (verified 2026-06-22):
- Single-pass full-screen hover probe: 405 points at 70px step (~1-2s)
- SCREEN: 4-6KB after render filters
- Two-pass LLM per node: 12-90s depending on prompt size and reasoning depth
- Generation: 6.14 tok/s (hard limit — the constraint is HARDWARE not software)
- Prompt eval: 50-170 tok/s (benefits from LM Studio prompt cache)
- Verify preflight eliminates LLM for structurally obvious outcomes
- Self-modify exercised and proven
- First autonomous goal completed

Non-negotiables:
- Do not reintroduce prompt truncation or parse_fallback.
- Do not add task/site-specific Python.
- Do not hide errors. Do not remove the two-pass reasoning.
- Python = mechanical body. Wiring = mutable brain.
- Put semantic fixes in prompts/guards, not code.
- Validate wiring. Hot-reload with absolute path.
- Commit coherent verified batches.

Immediate analysis approach:
- Read the LM Studio server log for the latest run:
  C:\Users\px-wjt\.cache\lm-studio\server-logs\2026-06\<latest>.log
- The log contains FULL request bodies and responses — this is ground truth.
- Map each LLM call to its pipeline node (planner P1/P2, act P1/P2, etc.)
- Measure: prompt_tokens, reasoning_tokens, content_tokens, total_time
- Identify: what consumed the most tokens, what was redundant reasoning

Key constraints for efficiency work:
- Generation at 6.14 tok/s is FIXED (hardware). Cannot improve.
- The only levers are: reduce output tokens, improve prompt cache hits,
  reduce prompt size (fewer input tokens = faster prompt eval).
- The two-pass stays. But within it, we can:
  - Reduce reasoning tokens per pass (shorter prompts = less to think about)
  - Improve cache overlap between pass 1 and pass 2 (already 87.9% for act)
  - Reduce SCREEN tokens sent to non-act nodes (they shouldn't see it anyway)
  - Reduce reasoning chain pollution between unrelated nodes
- Strengthen verify preflight to cover more structural patterns
  (every pattern matched = 2 LLM calls × 30-60s saved)
- IMPORTANT: changes must be GENERIC not task-specific

The system will run complex multi-day tasks. Optimizing for "open notepad"
is misleading. The real workload is: install software, configure systems,
interact with web services, handle failures, replan mid-task.

First actions:
1. git status, compileall, JSON parse, git diff --check
2. Confirm /health and /wiring
3. Read LM Studio server log for latest run
4. Full request/response forensics: map data flow through the topology
5. Identify the highest-leverage generic efficiency improvement
6. Implement, test, commit, update README

When something fails:
- Model lacked data → fix observation/rendering/filters
- Model had wrong policy → patch prompts/wiring.json
- Graph flow wrong → patch topology/guards/limits
- Mechanics failed → patch Python mechanically
- Fix names one website/app → it belongs in prompt policy or not at all
```

## Decision Rules

- Model lacked data → fix observation/rendering/filters
- Model had wrong policy → patch `prompts/wiring.json`
- Graph flow wrong → patch topology/guards/limits
- Mechanics failed → patch Python mechanically
- Fix names one app/site → it belongs in prompt policy or not at all
- If unsure whether a change is generic → it's probably not, don't add it

## Session Close Checklist

- [ ] README updated when reality changed
- [ ] Wiring validates (POST /wiring returns 200)
- [ ] Server reports healthy (GET /health)
- [ ] Current limitations stated directly
- [ ] Commit exists for the coherent batch
