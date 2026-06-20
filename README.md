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

## Critical bugs found via LM Studio log forensics (2026-06-20)

### Bug 1: Reasoning chain poisoning (PARTIALLY FIXED)

The model's `reasoning_content` from each circuit was concatenated into a REASONING_CHAIN
block and passed to ALL subsequent circuits. The 4B model would read the chain, see
`[planner]` entries with `record_type: task`, and then output `record_type: task` from
the act circuit instead of `record_type: action`.

**Evidence from logs:** At cycle 35, act node received a REASONING_CHAIN containing 8 entries
from planner/reflect/self_modify. The model's reasoning_content shows it literally
roleplaying each prior circuit: "We need to output content JSON with record_type task as
per planner" — then outputs task JSON from within the act node.

**Fix applied:** 
- REASONING_CHAIN block removed from act node's user blocks in wiring.json
- reasoning_chain clears on every plan_ready

**Remaining gap:** Within a single step's retry loop, the chain still accumulates
verify+reflect entries. The 4B model sometimes mimics those too. Solution: remove
REASONING_CHAIN from ALL LLM nodes except planner (which uses it for replan context).

### Bug 2: Verifier false positives

The verifier confirmed "Chrome is open" after seeing `OK: hotkey win+r: pressed win+r`.
Pressing Win+R opens the Run dialog, not Chrome. The model cannot reason about multi-step
causality — it sees "OK" prefix and confirms.

**Root cause:** `done_when: "Chrome is open"` is semantically unreachable from a single
`hotkey win+r` action, but the 4B model doesn't understand that.

**Fix needed in wiring.json:** Tighten verifier prompt: "confirmed=true requires the
LAST_OUTCOME to DIRECTLY demonstrate the done_when criteria, not merely a precursor step."

### Bug 3: Screen pollution (UNFIXED)

The UIA probe in `desktop.py` captures elements from ALL visible windows across the entire
screen — not just the focused application. A typical observation:

```
FOCUSED: Untitled - Notepad
ELEMENTS: 58
  [1] Button "Minimize"           ← Notepad (relevant)
  ...
  [26] Button "CPU 31% 3.07 GHz"  ← Task Manager (irrelevant)
  [44] Document "LM Studio"        ← LM Studio (irrelevant)
  [63] Button "Google Chrome pinned" ← Taskbar (irrelevant)
```

The model sees 58-84 elements when only 3-5 belong to the focused app. It clicks wrong
elements (e.g. "Edit bookmark for this tab" instead of using Run dialog to open Chrome).

**Fix needed in desktop.py:** Filter `_probe` results by the focused window's HWND.
Elements whose `el_hwnd != focused_hwnd` should be excluded or rendered without [ID].

### Bug 4: Model outputs JSON in reasoning_content instead of content

The model sometimes puts the structured JSON in `reasoning_content` (thinking channel)
and leaves `content` empty. The `parse_fallback` config in wiring.json handles this by
checking both channels — this works but it means the model wastes its content channel.

**Not a bug to fix** — the parse_fallback is correct compensation for small model behavior.

---

## File purposes

| File | Lines | Role |
|------|-------|------|
| `server.py` | 1091 | Graph engine + HTTP API + all 12 node handlers + LLM caller + prompt assembly |
| `desktop.py` | 480 | Windows UIA hover-probe observer (cursor moves across screen, reads elements) |
| `actions.py` | 179 | Verb executor: click, write, press, hotkey, focus, scroll |
| `colony.py` | 112 | Multi-slot spawner (N instances sharing bus.json) |
| `wiring-editor.html` | 277 | Canvas2D topology visualizer + SSE event log |
| `prompts/wiring.json` | 536 | **THE BRAIN** — topology, prompts, guards, limits, reasoning config |
| `prompts/model.json` | - | LLM endpoint (localhost:1234, nvidia-nemotron-3-nano-4b) |
| `prompts/wiring-schema.json` | - | Schema for wiring validation |

---

## What the next session must do

### Priority 1: Fix screen pollution in desktop.py

In `Desktop.observe()`, after getting the focused HWND, the `_probe()` results should
filter: only elements where `el_hwnd == focused_hwnd` get an [ID]. Others render as
read-only context (no [ID] = model can't target them = no wrong clicks).

This is a 5-line change in `_render()` or `_classify()`.

### Priority 2: Fix verifier prompt in wiring.json

Change the verifier role prompt to explicitly require causal connection:
"confirmed=true requires LAST_OUTCOME to DIRECTLY achieve done_when, not merely be a
precursor action. Example: pressing Win+R is a precursor to opening an app, NOT confirmation
that the app is open."

### Priority 3: wiring-editor.html becomes the test/control panel

Add to the HTML:
- A text input + "Run" button that POSTs to `/run`
- A state panel that polls `/state` every 2s and displays plan/step/history
- A "Smoke" button that GETs `/smoke` and shows pass/fail

No new files. No test frameworks. The HTML IS the interface.

### Priority 4: Code reduction in server.py

Target: under 900 lines. Candidates:
- `_resolve_value` (50 lines): switch-case that could be table-driven
- `load_system_prompt` (23 lines): has dead legacy fallback paths (file-based prompts)
- `print_listen_urls` / `http_bind`: already simplified, can be inlined
- `append_trace` / `recent_traces` (30 lines): trace system never produces output — consider removal
- `validate_wiring` (40 lines): useful but could be a startup-only check, not imported

### Priority 5: Remove REASONING_CHAIN from remaining LLM nodes

In `prompts/wiring.json`, remove the REASONING_CHAIN block from:
- verify node (doesn't need it — judges from LAST_ACTIONS/LAST_OUTCOME only)
- reflect node (doesn't need it — diagnoses from STEP/OUTCOME/VERIFY_REASONING)

Keep it ONLY in planner (needs replan context).

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

# Check state
curl http://localhost:9078/state
curl http://localhost:9078/smoke
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
| `ENDGAME_SIM=1` | Stub desktop (for dev without Windows) |
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
