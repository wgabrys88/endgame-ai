# endgame-ai

> HANDOVER PROMPT — this file IS the bootstrap for the next AI session.
> Read `prompts/wiring.json` → `server.py` → `actions.py` → `desktop.py` → `colony.py` in that order.

Autonomous Windows desktop agent. Local 4B model (nvidia-nemotron-3-nano-4b via LM Studio).
Zero pip dependencies. One stdlib Python process. ~2000 lines total.

It cannot see pixels. It probes the Windows UIA tree via cursor hover, gets a text list of
elements with IDs, sends that to a local LLM, gets back structured JSON, executes via Windows API,
observes result, verifies, reflects. The intelligence is in `prompts/wiring.json`. Python is plumbing.

---

## Status (2026-06-20)

### What works — proven on real desktop + real LLM

| Goal | Cycles | Result |
|------|--------|--------|
| open notepad | 11 | ✓ satisfied |
| open notepad and type hello | 16 | ✓ satisfied |
| open Chrome, focus, type youtube.com, enter | 27 | ✓ satisfied |
| Step-by-step via `/node/:type` API | manual | ✓ all nodes callable |

### What was fixed this session (10 commits from main)

1. **Screen pollution** — FIXED. `_render()` filters by focused HWND. Only focused-window
   elements get `[ID]`. Observation went from 58-84 elements to 3-8 elements.

2. **Verifier false-positives** — FIXED. Prompt now has explicit negative examples:
   `hotkey win+r` NEVER confirms "Notepad is open". The 4B model obeys concrete examples
   where it ignores abstract rules.

3. **Reasoning chain poisoning** — FIXED. REASONING_CHAIN removed from act/verify/reflect/
   self_modify nodes. Only planner keeps it for replan context. Chain clears on plan_ready.

4. **Code reduction** — server.py 1180→1026 lines. Total repo 23 files→10 files.
   Deleted: test files, simulation.py, start scripts, personality files, prompt .txt files,
   PLAN.md, NAVIGATION.md, TEST_RESULTS.md, reactor.py.

5. **HTML dashboard** — rewritten as control panel with Step/Run buttons that call
   `/node/:type` API directly. Real-time SSE log. `/push` endpoint for AI-to-dashboard
   communication.

### What doesn't work yet

1. **Full autonomous run blocks HTTP** — the observe probe (cursor movement) takes 2-5s and
   blocks the server thread. `ThreadingHTTPServer` helps but the GIL + UIA COM calls still
   cause timeouts. Fix: run the `run()` loop in a subprocess or use async.

2. **Colony untested end-to-end** — `colony.py` spawns N slots, bus routing is wired, but
   no real multi-slot run has been validated. The MoE gate delegates browser keywords to
   slot 1 but this hasn't been tested with 2 live instances.

3. **Model temperature/retry** — when parse fails, temperature bumps 0.15 per retry. This
   sometimes helps, sometimes produces worse JSON. The 4B model is highly sensitive to
   temperature. Consider keeping 0.3 fixed and just retrying.

---

## Architecture

```
goal_inbox ──→ moe_route ──→ planner ──→ scheduler ──→ bus_check ──→ observe ──→ act ──→ verify
                  │              ↑            │                                     │       │
                  │ delegated    │ retry      │ plan_complete                       │       │
                  ↓              │            ↓                                     │       │
              bus_post → satisfied        bus_post → satisfied                      │       │
                                                                    act_failed ─────┘       │
                                                                        ↓                  │
                                                                     reflect ←── step_denied
                                                                     │  │  │
                                                              retry ──┘  │  └── escalate
                                                                     replan    self_modify
                                                                        ↓          ↓
                                                                     planner    planner
```

- 12 nodes, 21 edges. 4 LLM calls per full cycle (planner, act, verify, reflect).
- All behavior in `prompts/wiring.json`. Python only resolves signals and executes.
- Each node: `(state, config) → {signals: [...], patch: {...}}`

---

## Files

| File | Lines | Role |
|------|-------|------|
| `server.py` | 1026 | Graph engine + HTTP + node handlers + LLM caller + prompt assembly |
| `desktop.py` | 482 | Windows UIA hover-probe (cursor moves, reads elements by HWND) |
| `actions.py` | 212 | Verb executor + sim stub (click/write/press/hotkey/focus/scroll) |
| `colony.py` | 112 | Multi-slot spawner (N rods sharing bus.json) |
| `wiring-editor.html` | 209 | Control panel: Step/Run, topology, plan/history, SSE log |
| `prompts/wiring.json` | 517 | **THE BRAIN** — topology, prompts, guards, limits |
| `prompts/model.json` | 16 | LLM endpoint (localhost:1234) |
| `prompts/wiring-schema.json` | 116 | Validation schema for self_modify |

---

## For the next AI — rules

1. **Read every file before changing anything.**
2. This is NOT LangChain/AutoGPT. Do not add frameworks, plugins, or abstractions.
3. Behavior changes go in `wiring.json` — not Python. Always.
4. Testing = HTTP API. `POST /run`, `GET /state`, `POST /node/:type`.
5. The HTML dashboard is the only UI. No new files for test harnesses.
6. Code deletion is always right if wiring.json handles the behavior.
7. Do not add pip dependencies. stdlib only.

---

## Running

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
$env:PYTHONIOENCODING = "utf-8"

# Real desktop goal
python server.py --run "open notepad" --max-cycles 30

# Server mode (HTTP API + dashboard)
python server.py
# Open http://localhost:9078/ in Chrome

# Step-by-step from dashboard
# Click Step button — calls /node/:type one at a time

# Colony (2 slots)
python colony.py 1 2
```

### API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/run` | Start goal: `{"goal": "..."}` |
| POST | `/node/:type` | Call single node: `{"state": {...}}` → `{signals, state_patch}` |
| POST | `/push` | Push to dashboard SSE: `{"type":"...", "text":"..."}` |
| POST | `/wiring` | Hot-reload topology |
| POST | `/interrupt` | Mid-run goal change |
| GET | `/state` | Current ROD state |
| GET | `/health` | Node registry + slot info |
| GET | `/smoke` | 6-point self-test |
| GET | `/events` | SSE stream |
| GET | `/wiring` | Current wiring.json |
| GET | `/` | Dashboard HTML |

---

## Colony + MoE + Bus

**Colony** (`colony.py`): spawns N `server.py` instances on consecutive ports (9078+slot).
Each rod has a `slot` and `permissions` from wiring.json.

**MoE gate** (`moe_route` node): checks if goal contains `delegate_keywords` (chrome,
browser, youtube) AND this rod lacks `desktop_exec` permission. If so, delegates to the
slot that has it via bus message + HTTP `/run` trigger.

**Bus** (`bus.json`): shared file. Messages have `{from_slot, to_slot, type, payload}`.
Types: `goal` (delegate), `telemetry` (status). `bus_check` node polls for interrupts.

**Status**: wired and code-complete. Not validated with 2 live instances. Next step:
run `python colony.py 1 2`, POST a browser goal to slot 2, confirm slot 1 executes it.

---

## Key invariants (do not break)

1. Only focused-window elements get `[ID]` in screen output
2. Reasoning chain clears on plan_ready
3. Act node does NOT receive REASONING_CHAIN
4. Verify preflight denies non-OK outcomes before calling LLM
5. Verifier: hotkey/press NEVER confirms app-opening goals
6. `http_port(slot)` = 9077 + slot. Slot 1 = port 9078.
7. Element resolver: `[ID]` targets only, digits never stripped from names
8. Self_modify validates wiring before writing, backs up first

---

## Next session priorities

1. **Fix server blocking during observe** — the UIA probe cursor sweep takes 2-5s and blocks
   all HTTP. Either: run `run()` in subprocess, or make observe non-blocking with a timeout,
   or use a dedicated worker thread for the graph loop separate from HTTP.

2. **Colony end-to-end test** — `python colony.py 1 2`, POST browser goal to slot 2's port,
   confirm delegation + slot 1 execution + bus telemetry.

3. **Server.py under 900 lines** — remaining targets: `_resolve_value` (table-driven),
   validate_wiring (separate module), compact node_act/node_self_modify.

4. **Observe filtering improvement** — current HWND filter may exclude taskbar elements
   that are needed (Start button for opening apps). Consider: include taskbar items as
   targetable when focused window is "Desktop" or "Program Manager".

5. **Model-specific prompt tuning** — the 4B model works with explicit examples, not
   abstract rules. Every new failure mode needs a concrete example in the prompt, not
   more English instructions.
