# endgame-ai

Autonomous Windows desktop agent. Local 4B model. Zero pip dependencies.

It cannot see pixels. It cannot click coordinates. It probes the Windows UIA tree via
cursor hover, gets a text list of elements with IDs, sends that to a local LLM, gets back
a structured JSON action, executes it via Windows API, observes result, verifies, reflects.

The intelligence is in `prompts/wiring.json`. Python is plumbing.

---

## For the next AI session

**Read every `.py` and `.json` file before proposing ANY change.**

This system is architecturally different from every other agent framework you know.
Do not restructure it. Do not add dependencies. Do not create new files unless replacing old ones.

### What this is NOT

- NOT a LangChain/AutoGPT style agent with plugins and tool-calling
- NOT a vision model looking at screenshots
- NOT a system that needs tests/ directories or pytest
- NOT something where more code = more capability

### What this IS

- A directed graph where nodes emit signals, edges route those signals to the next node
- 4 LLM calls total per cycle (planner, act, verify, reflect)
- Everything else is deterministic Python reading config from wiring.json
- Behavior changes happen in wiring.json prompts/guards/limits — not in Python
- Testing happens via HTTP API: POST `/run`, GET `/state`, GET `/smoke`

---

## Topology

```
goal_inbox ──→ moe_route ──→ planner ──→ scheduler ──→ bus_check ──→ observe ──→ act ──→ verify
                  │              ↑            │                                     │       │
                  │ delegated    │ retry      │ plan_complete                       │       │
                  ↓              │            ↓                                     │       │
              bus_post ──→ satisfied      bus_post ──→ satisfied                    │       │
                                                                                   │       │
                                                                    act_failed ─────┘       │
                                                                        │                  │
                                                                        ↓                  │
                                                                     reflect ←── step_denied
                                                                     │  │  │
                                                              retry ──┘  │  └── escalate
                                                                        │          ↓
                                                                     replan    self_modify
                                                                        │          │
                                                                        ↓          ↓
                                                                     planner    planner
```

Each node: `(state, config) → {signals: [...], patch: {...}}`

Graph engine in `server.py` function `run()`: resolve signals → find edge → call next node → repeat.

---

## Proven results (nvidia-nemotron-3-nano-4b, real Windows desktop)

| Goal | Cycles | Steps | Result |
|------|--------|-------|--------|
| open notepad | 11 | 1 | ✓ satisfied |
| open notepad and type hello | 16 | 2 | ✓ satisfied |
| open Chrome, focus it, type youtube.com, press enter | 27 | 3 | ✓ satisfied |

---

## Forensic findings from LM Studio logs (2026-06-20)

### Bug 1: Reasoning chain poisoning — FIXED

The model's `reasoning_content` from each circuit was concatenated into a REASONING_CHAIN
block and passed to ALL subsequent circuits. The 4B model would read the chain, see
`[planner]` entries with `record_type: task`, and then output `record_type: task` from
the act circuit instead of `record_type: action`.

**Fix applied:**
- REASONING_CHAIN removed from act, verify, reflect, and self_modify nodes
- Only planner retains REASONING_CHAIN (for replan context)
- reasoning_chain clears on every plan_ready

### Bug 2: Verifier false positives — FIXED

The verifier confirmed "Chrome is open" after seeing `OK: hotkey win+r: pressed win+r`.
Pressing Win+R opens the Run dialog, not Chrome.

**Fix applied:** Verifier prompt now requires DIRECT causal match:
"confirmed=true requires LAST_OUTCOME to DIRECTLY demonstrate done_when — a precursor
action (e.g. pressing Win+R) is NOT confirmation that an app is open"

### Bug 3: Screen pollution — FIXED

The UIA probe captured elements from ALL visible windows. The model saw 58-84 elements
when only 3-5 belonged to the focused app.

**Fix applied:** `_render()` now accepts `focused_hwnd`. Only elements matching the
focused window's HWND get `[ID]` (targetable). Other elements render as plain text
context — visible but not clickable.

### Bug 4: Model outputs JSON in reasoning_content instead of content

The model sometimes puts structured JSON in `reasoning_content` and leaves `content` empty.
The `parse_fallback` config handles this by checking both channels.

**Not a bug** — correct compensation for small model behavior.

---

## File purposes

| File | Lines | Role |
|------|-------|------|
| `server.py` | 1091 | Graph engine + HTTP API + all 12 node handlers + LLM caller + prompt assembly |
| `desktop.py` | 480 | Windows UIA hover-probe observer (cursor moves, reads elements by HWND) |
| `actions.py` | 195 | Verb executor + sim stub (click/write/press/hotkey/focus/scroll) |
| `colony.py` | 112 | Multi-slot spawner (N instances sharing bus.json) |
| `wiring-editor.html` | 277 | Canvas2D topology visualizer + SSE event log |
| `prompts/wiring.json` | 536 | **THE BRAIN** — topology, prompts, guards, limits, reasoning config |
| `prompts/model.json` | — | LLM endpoint (localhost:1234, nvidia-nemotron-3-nano-4b) |
| `prompts/wiring-schema.json` | — | Validation schema |

---

## What the next session must do

### Priority 1: wiring-editor.html becomes the test/control panel

Add to the HTML:
- A text input + "Run" button that POSTs to `/run`
- A state panel that polls `/state` every 2s and displays plan/step/history
- A "Smoke" button that GETs `/smoke` and shows pass/fail
- Goal history sidebar (localStorage)

No new files. No test frameworks. The HTML IS the interface.

### Priority 2: Live desktop verification

Run `python server.py --run "open notepad" --max-cycles 30` on real Windows desktop
with the screen pollution fix active. Confirm:
- Element count is now 3-8 (was 58-84)
- No clicks on wrong windows
- Verifier no longer false-confirms precursor actions

### Priority 3: Code reduction in server.py

Target: under 900 lines. Candidates:
- `_resolve_value` (50 lines): switch-case that could be table-driven
- `load_system_prompt` (23 lines): has dead legacy fallback paths (file-based prompts)
- `append_trace` / `recent_traces` (30 lines): trace system rarely used — consider removal
- HTTP endpoints (117 lines): /schema, /traces endpoints unused
- `validate_wiring` (40 lines): useful but could be startup-only

### Priority 4: Colony end-to-end

Colony multi-slot delegation via shared bus.json. Already wired. Needs real test:
POST to slot 2's `/run`, observe slot 1 receiving delegated goal and completing it.
Test via the HTML dashboard.

---

## Running

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
$env:PYTHONIOENCODING = "utf-8"

# Run a goal on real desktop
python server.py --run "open notepad" --max-cycles 30

# Server mode (goals via HTTP)
python server.py
# Then: curl -X POST http://localhost:9078/run -d "{\"goal\":\"open notepad\"}"

# Simulation (Linux/no Windows)
$env:ENDGAME_SIM = "1"
python server.py --run "open notepad"

# Colony
python colony.py 1 2
```

### API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/run` | Start goal: `{"goal": "..."}` |
| POST | `/resume` | Resume from state.json |
| POST | `/interrupt` | Push new goal mid-run |
| POST | `/wiring` | Hot-reload topology |
| GET | `/state` | Current ROD state |
| GET | `/health` | Node registry + slot info |
| GET | `/smoke` | 6-point self-test |
| GET | `/events` | SSE stream (node transitions) |
| GET | `/wiring` | Current wiring.json |
| GET | `/` | Serve wiring-editor.html |

---

## Environment

| Var | Effect |
|-----|--------|
| `ENDGAME_SLOT=N` | Instance slot, port = 9077 + N |
| `ENDGAME_PERMISSIONS=desktop_exec` | MoE routing permission |
| `ENDGAME_SIM=1` | Inline stub desktop (dev without Windows) |
| `PYTHONIOENCODING=utf-8` | Required on Windows |

---

## Architecture invariants (do not break)

1. `_trigger_rod_run` uses `http_port(slot)` — never a separate port function
2. Element resolver: only `[ID]` numeric targets, digits are never stripped from names
3. `PRIOR_TRACES` only emitted on replan (`replan_count > 0`)
4. Verify preflight denies `FAILED:` / `BLOCKED` outcomes before calling LLM
5. `node_satisfied`: false on `plan_failed`, true only when `step >= len(plan)`
6. Reasoning chain clears on plan_ready (prevents cross-circuit poisoning)
7. Act node does NOT receive REASONING_CHAIN (only VERIFY/REFLECT feedback)
8. Only focused-window elements get [ID] — others rendered as context without targeting
9. Verifier requires DIRECT causal match between LAST_OUTCOME and done_when
