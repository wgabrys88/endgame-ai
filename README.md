# endgame-ai

Autonomous Windows desktop agent. Cannot see the screen. Cannot click directly.
Writes Python, executes it, reads stdout, reasons, acts, verifies, reflects.

Local 4B-class model. Artificial persistence via graph topology, not open-ended reasoning.

---

## For the AI reading this

You are the next session. Read every file before changing anything.
This system is NOT like other agent frameworks. Do not restructure it.

The rules:

1. Python is dumb plumbing. All behavior lives in `prompts/wiring.json`.
2. There are exactly 4 LLM calls: planner, act, verify, reflect (+self_modify on escalate).
3. Everything else is deterministic graph traversal driven by signals and edges.
4. Prefer wiring.json changes over code changes. Always.
5. Testing happens via HTTP API (`/run`, `/state`, `/smoke`) — not unit test files.
6. The `wiring-editor.html` IS the dashboard. It must become the test harness too.
7. Code reduction is always correct. If Python can be deleted because wiring handles it, delete it.

Read these files in this order: `prompts/wiring.json` → `server.py` → `actions.py` → `desktop.py`

---

## Topology (the brain)

```
                              ┌─────────────────────────────────────────────────────┐
                              │                                                     │
  goal_inbox ─→ moe_route ─→ planner ─→ scheduler ─→ bus_check ─→ observe ─→ act ─→ verify
                   │  delegated    ↑ retry_plan        │ plan_complete               │  │
                   ↓               │                   ↓                             │  │
               bus_post ─→ satisfied                bus_post ─→ satisfied            │  │
                                   │                                                 │  │
                                   │              ┌──────────────────────────────────┘  │
                                   │              │ step_confirmed → scheduler           │
                                   │              │                                     │
                                   │              │ step_denied ─→ reflect               │
                                   │              │                  │  │  │             │
                                   │              │          retry ──┘  │  │             │
                                   │              │         replan ─────┘  │             │
                                   │              │       escalate ────────┘             │
                                   │              │            ↓                         │
                                   │              │       self_modify ─→ planner         │
                                   │              │                                     │
                                   └──────────────┴── act_failed ───→ reflect ──────────┘
```

Signals flow through edges. Python resolves them: `find_targets(node_id, signals, topology)`.

Each node is a pure function: `(state, config) → {signals: [...], patch: {...}}`

LLM nodes call the model and parse structured JSON. Non-LLM nodes are 3-10 lines of logic.

---

## What works (proven on real desktop + nvidia-nemotron-3-nano-4b)

- `open notepad` — 11 cycles, 1 plan step, satisfied
- `open notepad and type hello` — 16 cycles, 2 plan steps, satisfied
- `open Chrome, focus it, type youtube.com in address bar and press enter` — 27 cycles, 3 steps, satisfied
- Colony multi-slot delegation via shared bus.json
- Self-modification: LLM proposes topology patches when stuck
- Full simulate mode (`ENDGAME_SIM=1`) for development without Windows

---

## What doesn't work yet

1. **Reasoning chain poisoning** — the 4B model mimics format from prior circuit outputs.
   Fixed partially: chain clears on plan_ready. Still leaks within a step's retry loop.
   Root cause: `reasoning_content` from all circuits is concatenated into REASONING_CHAIN.

2. **Verifier false positives** — model confirms steps too eagerly (e.g. confirms "Chrome open"
   after just pressing Win+R). The `done_when` criteria are ambiguous for a 4B model.

3. **Screen pollution** — UIA probe captures ALL visible windows (Task Manager, LM Studio, Terminal)
   not just the focused app. Agent sees 60-80 elements when 5 matter.

4. **Implicit goals fail** — "open Chrome and go to youtube.com" fails because the planner
   doesn't always emit the focus step. Explicit goals succeed.

---

## Code reduction opportunities

| Area | Current | Opportunity |
|------|---------|-------------|
| `_resolve_value` (50 lines) | Giant switch for state lookups | Table-driven from wiring |
| `load_system_prompt` (23 lines) | Legacy fallback paths | Node prompt config is enough, remove file fallbacks |
| `check_repeat_block` + `_find_advance_hint` (30 lines) | Guard logic in Python | Move to wiring declarative eval |
| `validate_wiring` (40 lines) | Runtime schema check | Keep but could be separate script |
| `extract_json_objects` (40 lines) | JSON parser from raw text | Needed but could use regex first-pass |
| HTTP endpoints (117 lines) | Full REST API | Some endpoints unused (/schema, /traces) |
| Test files (4 files, ~400 lines) | Separate test infrastructure | Replace with `/smoke` + HTML test panel |

Target: server.py under 800 lines. Total Python under 1200 lines.

---

## Next session priorities

1. **wiring-editor.html becomes the test harness** — add a goal input + run button + state viewer.
   Testing = POST to `/run`, poll `/state`, display signals. No more test_*.py files.

2. **Screen filtering** — `observe` should only render elements from the focused window's HWND.
   The current probe scans the entire screen. Focused-only would cut noise by 80%.

3. **Reasoning chain isolation** — don't pass full chain to act. Act only needs its own
   last-attempt reasoning + reflect suggestion. Planner/verify reasoning is irrelevant to it.

4. **Colony P2** — slot 2 delegates to slot 1 via bus. Already wired, needs end-to-end test
   via the HTML dashboard (POST to slot 2's `/run`, observe slot 1 completing).

5. **Code deletion** — remove `test_*.py` files after HTML test harness works.
   Remove `start.sh`, `start_colony.ps1` (one-liners that add nothing).
   Remove `simulation.py` if HTML panel can mock responses.

---

## Files

| File | Lines | Role |
|------|-------|------|
| `server.py` | ~1090 | Graph engine + HTTP + all node handlers |
| `desktop.py` | ~300 | Windows UIA hover-probe observer |
| `actions.py` | ~180 | Verb dispatch (click/write/press/hotkey/focus/scroll) |
| `simulation.py` | ~115 | Fake desktop for dev without Windows |
| `colony.py` | ~112 | Multi-slot spawner |
| `wiring-editor.html` | ~280 | Canvas2D topology editor + SSE log |
| `prompts/wiring.json` | THE BRAIN | Topology, prompts, guards, limits, reasoning config |
| `prompts/model.json` | LLM endpoint config |
| `prompts/wiring-schema.json` | Validation schema |

---

## Running

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
$env:PYTHONIOENCODING = "utf-8"

# Single goal (real desktop + LLM)
python server.py --run "open notepad" --max-cycles 30

# Server mode (accepts goals via HTTP)
python server.py

# Simulation (no Windows needed)
$env:ENDGAME_SIM = "1"
python server.py --run "open notepad"

# Colony
python colony.py 1 2
```

API:
- `POST /run {"goal": "..."}` — start autonomous loop
- `GET /state` — current ROD state
- `GET /smoke` — 6-point health check
- `GET /health` — node registry + slot info
- `GET /events` — SSE stream (node transitions)
- `POST /wiring` — hot-reload topology

---

## Environment

| Var | Effect |
|-----|--------|
| `ENDGAME_SIM=1` | Use simulation.py desktop |
| `ENDGAME_SLOT=N` | Override instance slot (port = 9077 + N) |
| `ENDGAME_PERMISSIONS=desktop_exec` | MoE routing permission |
| `PYTHONIOENCODING=utf-8` | Required on Windows |

---

## Key insight from LM Studio logs (2026-06-20)

The 4B model's `reasoning_content` channel contains its full chain-of-thought.
When this is passed downstream as REASONING_CHAIN, the model at the next node
**role-plays all previous circuits** in its reasoning, then outputs the wrong record_type.

Example: act node receives chain containing `[planner]` reasoning about task decomposition.
The model's reasoning_content shows it literally re-deriving the plan, then outputs
`record_type: task` instead of `record_type: action`.

The fix: strict isolation. Each circuit should only see its own prior attempt + the
reflect suggestion. The full chain is useful for humans/debugging but toxic for the 4B model.

This is a wiring.json change: modify act's user blocks to remove REASONING_CHAIN,
keep only VERIFY_REASONING and REFLECT_REASONING.
