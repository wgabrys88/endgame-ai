# endgame-ai

A single **rod** — one Windows desktop organism. Intelligence is wiring, not one monolithic prompt.

**Branch:** `experiment/endgame` · **Do not touch `main`.**

**Ultimate goal:** replace a human for arbitrary-length desktop tasks. **Today:** one rod, one `wiring.json`, local LM Studio.

---

## Essential files (10)

```
README.md
wiring-editor.html      ← visual editor + live step/run (reads wiring from server)
server.py               ← graph engine, LLM circuits, HTTP
actions.py              ← verb dispatch
desktop.py              ← hover-probe observe + mouse/keyboard
prompts/wiring.json     ← THE brain (topology, prompts, policy)
prompts/model.json      ← LM Studio endpoint
LICENSE · .gitignore · .gitattributes
```

**Runtime (never commit):** `state.json`, `bus.json`, `*.log`, `__pycache__/`

---

## Quick start

```powershell
# Prerequisites: Windows, Python 3.11+, LM Studio on localhost:1234
cd endgame-ai

python server.py
# → http://127.0.0.1:9078  (slot=1 → 9077+1)
# Startup prints LAN URLs for phone/tablet on same WiFi

python server.py --run "open notepad and write hello"

start http://127.0.0.1:9078    # wiring-editor (wiring auto-loads — no file button needed)
```

### Phone / LAN dashboard

Same idea as LM Studio: server must listen beyond localhost and Windows Firewall must allow the port.

1. `wiring.json` → `runtime.http_bind`: `"0.0.0.0"` (default in repo)
2. Start server — note the `lan http://192.168.x.x:9078` line in console
3. On phone (same WiFi), open that URL in Chrome
4. **Firewall (once, admin PowerShell):**
   ```powershell
   netsh advfirewall firewall add rule name="endgame-ai" dir=in action=allow protocol=TCP localport=9078
   ```
5. LM Studio stays on PC (`localhost:1234`) — only the **dashboard** is exposed to LAN; the rod still calls LM Studio locally

Override bind: `$env:ENDGAME_BIND="127.0.0.1"` for localhost-only.

---

## Architecture

```
prompts/wiring.json
  ├── topology.nodes[]     graph + prompt per LLM node
  ├── topology.edges[]     signals between nodes
  ├── prompts.base         shared system preamble (all circuits)
  ├── prompts.roles        per-circuit system text
  ├── reasoning.*          capture + feed reasoning_content
  ├── guards, act, limits, errors, runtime, verbs
  └── instance.slot        HTTP port offset

server.py                  runs topology, calls LM Studio, executes verbs
desktop.py                 mouse-hover grid → element_from_point (NO tree walk)
actions.py                 click/write/hotkey/focus from [ID] in SCREEN
```

### Signal flow

```
goal_inbox → planner → scheduler → bus_check → observe → act → verify
                ↑                              ↓ fail
             reflect ←─────────────────────────┘
                ↓ replan / escalate → self_modify
```

### LLM circuits (on topology nodes)

| Node | role key | record_type |
|------|----------|-------------|
| planner | planner | task |
| act | unified | action |
| verify | verifier | verdict |
| reflect | reflector | diagnosis |
| self_modify | self_modify | wiring_patch |

**System prompt** = `prompts.base` + `prompts.roles[node.prompt.role]`  
**User message** = assembled from `node.prompt.user.blocks`  
**Reasoning** = LM Studio `reasoning_content` → `state.reasoning` → downstream blocks  
**Act never emits DONE** — verify confirms steps.

### Desktop observe

**Hover probe only** — cursor sine-grid over focused window, `element_from_point` at each point. No UIA tree walk (tree walk added noise like writable `Text "Windows PowerShell"`).

SCREEN shows `[ID]` for actionable elements. Targets must exist in SCREEN.

---

## Changing behavior

| Change | Edit |
|--------|------|
| Flow / retries | `topology.edges`, `limits.*` |
| What a circuit sees | `node.prompt.user.blocks` |
| Circuit rules | `prompts.roles.*` or `prompts.base` |
| Guard hints | `guards.advance_hints` |
| New node type | Python `server.py` + wiring topology |

---

## wiring-editor.html

Served at `/` when `python server.py` is running.

| Feature | API |
|---------|-----|
| Load wiring | `GET /wiring` |
| Save wiring | `POST /wiring` (💾 Save toolbar) |
| Step node | `POST /node/{type}` |
| Autonomous run | `POST /run` |
| Live highlight | `GET /events` (SSE) |

**Sidebar:** edit `prompts.base`, per-node role text + user blocks JSON → Apply → Save.

**Port:** auto-discovers `9078`, `9077`, `9079`, `9080` via `/health`.

**Save behavior:** `flowToWiring()` updates `topology` from canvas; merges with full wiring from server (prompts, reasoning, guards preserved).

---

## Known gaps

- Complex web/video goals unproven (UIA + LLM latency)
- ~90–120s per act+verify — budget 6–8+ min for real goals
- `model.json` not yet merged into wiring
- Multi-rod / colony deferred (Phase 2)

---

## Handover prompt (next session — paste to any AI)

```
You are continuing endgame-ai — a single-rod Windows desktop organism.

REPO: C:\Users\px-wjt\Downloads\endgame-ai
BRANCH: experiment/endgame (never touch main)

VISION: Replace a human for arbitrary-length desktop tasks. One rod today.
Intelligence = wiring topology + reasoning loop + verify gate — not one prompt.

SINGLE SOURCE OF TRUTH (target architecture):
  prompts/wiring.json is THE brain. Everything configurable lives there.
  server.py is a dumb interpreter (graph engine + muscles hookup).
  wiring-editor.html is a FROZEN generic viewer/editor — once correct, it
  never changes again; it only reads/writes wiring.json shape via HTTP.

  Next session goal: formalize wiring.json SCHEMA so HTML and server are
  schema-driven and never need feature patches. Deduce schema from current
  file before adding fields.

CURRENT wiring.json shape (endgame-topology/v1):
  schema, instance.slot
  topology: { cycle_start, nodes[], edges[] }
    LLM nodes carry: circuit, prompt { extends, role, user.blocks[] }
  prompts: { base, roles { planner, unified, verifier, reflector, self_modify } }
  reasoning: { store_as, expected_record_type, chain_depth, clear_on_step_confirm }
  node handlers use call_node("act") etc. — circuit role from node.prompt.role
  guards, act, limits, errors, runtime, verbs, context

ESSENTIAL FILES (only these are tracked):
  README.md, wiring-editor.html, server.py, actions.py, desktop.py,
  prompts/wiring.json, prompts/model.json, LICENSE, .gitignore

BODY:
  server.py — call_node(), reasoning_patch(), parse_circuit_response()
  desktop.py — hover-probe ONLY (element_from_point grid, NO UIA tree walk)
  actions.py — verbs; resolve [ID] from SCREEN; prefer Edit over Text

RUN:
  python server.py
  python server.py --run "goal"
  http://127.0.0.1:9078 — wiring-editor

HTML EDITOR (your focus next session):
  wiring-editor.html — React + xyflow, ~800 lines, served at GET /
  - Loads GET /wiring, draws topology.nodes/edges
  - POST /wiring saves full JSON (hot-reload server)
  - Click node → edit prompts.base, role text, user.blocks
  - Step/Run/Auto via POST /node/{type}, POST /run, SSE /events
  - flowToWiring() must preserve non-topology sections on save

  FUTURE: HTML becomes schema-generic:
    - Node types, edge signals, prompt block editors generated from schema
    - No hardcoded node type colors or circuit names in JS
    - Schema document drives validation (server + editor)
    - model.json merged into wiring.llm section

  First step: inventory wiring.json → write JSON Schema or equivalent →
  validate on POST /wiring → refactor editor to read schema for labels/fields.

CONSTRAINTS:
  stdlib only, Windows, static prompts in wiring (not runtime-mutated .txt)
  task-agnostic prompt text, no screen truncation, act never DONE

ANALYZE FAILURES:
  state.json — step, plan, reasoning.*, FULL screen, last_error
  Which node failed: planner / act / verify / reflect — evidence from SCREEN

DO NOT re-add: colony, personalities, probe_circuits, separate .txt prompts,
  UIA tree walk in desktop.py, extra markdown docs.
```