# endgame-ai

Single-rod Windows desktop organism. Intelligence is the wiring graph plus a reasoning loop, not one monolithic prompt.

**Branch:** `experiment/endgame` (active development — do not commit to `main`).

**Latest tag:** `PROGRESS-TODO-LAN` on commit `96ec326`.

**Ultimate goal:** one process on real Windows hardware that can pursue arbitrary-length desktop tasks without a human in the loop.

**Today:** one rod, one `prompts/wiring.json`, LM Studio on `localhost:1234`, dashboard on port `9078`.

---

## 1. What this repository is

endgame-ai is a stdlib-only Python program (`server.py`) that:

1. Accepts a natural-language **goal**.
2. Runs a **directed graph** of node handlers defined in `prompts/wiring.json`.
3. Calls LM Studio for five LLM **circuits**: planner, act, verify, reflect, self_modify.
4. Observes the Windows desktop via UIA **hover-probe** (`desktop.py`).
5. Executes mouse/keyboard actions via data-driven **verbs** (`actions.py`).
6. Serves a browser **dashboard** (`wiring-editor.html`) for diagram view, stepping, and prompt editing.

There is no pip install step. There is no separate database. Policy lives in JSON; Python interprets it.

---

## 2. Session log — what was built (experiment/endgame arc)

This section records the real development arc visible in `git log` and session transcripts. It is the authoritative story of how the repo reached its current shape.

### 2.1 Early experiment (before slim-down)

- Colony / multi-rod / reactor / personalities existed on older branches (`archive/colony-dev`, `archive/reactor-personalities`, tags `unify-cut-*`).
- Those paths were **removed** from `experiment/endgame`. They are not in the 10 tracked files.
- Tag `WIRING-SEPARATION` marks the pivot to honest single-rod + wiring.json brain.

### 2.2 Consolidation commits (documented in git)

| Commit | What actually changed |
|--------|----------------------|
| `64e4e2c` | Docs rewrite: wiring-separation architecture stated honestly |
| `3ccbb8e` | Policy moved into wiring.json; Python as executor only |
| `35088b0` | Single README focus; colony/persona bloat removed from docs |
| `56146ca` | Dev harness scripts deleted (`probe_circuits.py`, `validate_stack.py`, fixtures) |
| `ab3527d` | Five circuit `.txt` prompt files inlined into `wiring.json` (`prompts.base` + `prompts.roles`) |
| `b6680b5` | Prompts bound to topology nodes; top-level `request` and `node_circuits` removed |
| `03932bf` | Wiring editor prompt editing + `POST /wiring` hot-reload; gitignore tightened |
| `2ab6acb` | **desktop.py restored to hover-probe only** — UIA tree walk removed (was noisy: writable `Text "Windows PowerShell"`) |
| `652aa0b` | **Multi-JSON parse fix** in `extract_json_objects()` — act/planner no longer fail when LLM emits multiple JSON blocks |
| `e8ca171` | React wiring editor JSX/layout fix; native toolbar wired to React handlers; SSE event names matched server |
| `b99dabd` | **React Flow replaced by Cytoscape**; `runtime.http_bind: 0.0.0.0` for LAN dashboard |
| `171baeb` | Responsive `100dvh` layout; legacy browser fallbacks removed (Chrome/Opera only) |
| `bd80bfa` | **ThreadingHTTPServer** — phone SSE no longer blocks `/health` and other requests |
| `1572c33` | **Circuit separation**: planner abstract subtasks; only act sees SCREEN; verify uses outcomes not SCREEN |
| `1c15861` | Runtime data cleaned; `state.json` gitignored; workspace scrubbed |
| `96ec326` | README rewrite (prior version) |
| Tag `PROGRESS-TODO-LAN` | Milestone: LAN dashboard + circuit separation + Cytoscape editor working |

### 2.3 Tag `CLEANUP-MORE`

Marks wiring-editor editable prompts + 4-minute Shakira test session + gitignore hardening (`03932bf` era).

### 2.4 What was observed in runtime logs (not committed)

These are real failure modes seen in `state.json` during development (file is gitignored; content described here for diagnosis):

**Notepad hello (simple goal):**

- Architecture loop behaved correctly: planner → act → verify → reflect cycles ran.
- Simple goals can complete in ~5 minutes when SCREEN is the real desktop and act uses `win+r` → `notepad` → `enter`.
- `bus.json` telemetry (runtime) once recorded `goal: "open notepad and write hello"`, `step: 2`, `satisfied: false` — rod advanced past first subtasks before session ended.

**Shakira / long web goal (4–8 min test):**

- **FAIL** — not an architecture loop bug.
- Causes: LLM latency (~90–120s per act+verify round), wrong UIA targets, browser DOM gaps, SCREEN captured wiring-editor chrome instead of target app.
- Loop correctly did planner → act → verify → reflect → replan; goal too hard for current observe + model speed.

**act_failed / step_denied patterns logged:**

| Symptom | Real cause |
|---------|------------|
| `act_failed` + `parse_failed` | LLM mixed record_types in one response; fixed by `652aa0b` multi-JSON parser |
| `act_failed` + `CANNOT` | Act correctly refused when SCREEN had no path to subtask |
| `act_failed` after reflect | Act clicked wiring-editor UI (`Vertical Large Increase` button) because browser was focused |
| `step_denied` | Verify correct: `done_when` not met — Notepad not in SCREEN, or LAST_OUTCOME not OK |
| `retry_plan` on planner | Planner emitted wrong record_type (diagnosis instead of task) before parse fix |
| `ConnectionAbortedError` on GET `/` | Browser refreshed mid-response; now suppressed in server |
| Dashboard freeze with phone open | Single-threaded HTTP blocked on SSE; fixed by `bd80bfa` |

**Planner before circuit separation (1572c33):**

- Planner received SCREEN and emitted UIA-specific `done_when` ("window titled Untitled - Notepad appears in SCREEN").
- Act received CANNOT when SCREEN was the IDE/browser.
- Reflect suggested clicking visible chrome buttons — wrong layer.

**After circuit separation (1572c33):**

- Planner emits: `open notepad`, `write hello in notepad` with plain-language `done_when`.
- Only act reads SCREEN and maps to `hotkey`/`write`/`press`.
- Verify judges `LAST_OUTCOME` against `done_when` without observing desktop.

---

## 3. Tracked files (exactly 10)

```
.gitattributes
.gitignore
LICENSE
README.md
actions.py
desktop.py
prompts/model.json
prompts/wiring.json
server.py
wiring-editor.html
```

Nothing else belongs on `experiment/endgame`. No `tests/`, no `docs/`, no `.txt` prompts, no colony scripts.

---

## 4. Runtime files (never commit)

Listed in `.gitignore` and safe to delete anytime:

```
state.json          persisted rod state (_resume_node, plan, step, reasoning, screen, history)
bus.json            optional telemetry bus between rods (slot messages)
__pycache__/        Python bytecode
*.log               any run output
terminals/          agent session terminal captures
_*.py               scratch scripts
shakira_test.json   test dump
prompts/wiring.backup.json   written by self_modify before mutation
```

Clean command (PowerShell):

```powershell
Remove-Item state.json, bus.json -ErrorAction SilentlyContinue
Remove-Item __pycache__ -Recurse -Force -ErrorAction SilentlyContinue
```

---

## 5. Quick start

### 5.1 Prerequisites

- Windows 10/11 (developed on Windows 11)
- Python 3.11+ (tested on 3.13)
- LM Studio running OpenAI-compatible server on `http://localhost:1234`
- Model loaded in LM Studio (settings in `prompts/model.json`)

### 5.2 Start server

```powershell
cd endgame-ai
python server.py
```

Console output (real example):

```
endgame-ai [1] bind=0.0.0.0 port=9078  nodes: ['entry', 'planner', ...]
  local   http://127.0.0.1:9078
  lan     http://192.168.16.31:9078
  phone   same WiFi → open LAN URL in browser
  firewall (once, admin PS): netsh advfirewall firewall add rule name="endgame-ai" dir=in action=allow protocol=TCP localport=9078
```

Port formula: `9077 + instance.slot` → slot `1` → **9078**.

### 5.3 Autonomous run (CLI)

```powershell
python server.py --run "open notepad and write hello"
```

Starts HTTP in background thread, runs graph until `satisfied` or terminal edge.

### 5.4 Dashboard

Open `http://127.0.0.1:9078` in Chrome or Opera (desktop or phone).

Wiring loads from `GET /wiring` automatically. No file picker required.

### 5.5 Resume

```powershell
python server.py --resume
```

Requires existing `state.json` with `_resume_node`.

---

## 6. LAN dashboard (phone / tablet)

Same pattern as exposing LM Studio — bind address + firewall rule.

| Setting | Value |
|---------|-------|
| `prompts/wiring.json` → `runtime.http_bind` | `"0.0.0.0"` (default in repo) |
| Override localhost-only | `$env:ENDGAME_BIND="127.0.0.1"` |
| Phone URL | `http://<LAN-IP>:9078` printed at startup |
| Firewall (once, admin) | `netsh advfirewall firewall add rule name="endgame-ai" dir=in action=allow protocol=TCP localport=9078` |

**Important:** LM Studio stays on PC at `localhost:1234`. The phone dashboard is remote control / editing only. The rod still calls LM Studio locally on the PC.

**Threading:** `ThreadingHTTPServer` with `daemon_threads = True` so multiple phone SSE connections do not block `/health` or `/wiring`.

---

## 7. Architecture overview

```
                    prompts/wiring.json
                           │
                           ▼
                      server.py
                     /    |    \
            LM Studio   graph   HTTP
                │      engine    │
                │         │      └── wiring-editor.html
                │         │
                │    node handlers
                │         │
                └─────────┴── desktop.py + actions.py
```

### 7.1 Separation of concerns (current — commit 1572c33)

| Circuit | role key | Sees SCREEN? | Input | Output record_type |
|---------|----------|--------------|-------|------------------|
| planner | planner | **No** | GOAL, reasoning chain | `task` |
| act | unified | **Yes — only** | SUBTASK, SCREEN, history | `action` |
| verify | verifier | **No** | STEP, DONE_WHEN, LAST_OUTCOME | `verdict` |
| reflect | reflector | **No** | STEP, LAST_OUTCOME, verify reasoning | `diagnosis` |
| self_modify | self_modify | **No** | GOAL, reasoning, topology ids | `wiring_patch` |

**Planner** writes human subtasks:

```json
{"description":"open notepad","done_when":"Notepad is open"}
{"description":"write hello in notepad","done_when":"The text hello is written in Notepad"}
```

No `[ID]`, no UIA role names, no SCREEN quotes in planner output.

**Act** alone translates subtask + SCREEN → one verb per turn (`click`, `write`, `press`, `hotkey`, `focus`, `scroll`).

**Verify** never calls `observe_screen()`. It judges whether `LAST_OUTCOME` (e.g. `OK: hotkey win+r: pressed win+r`) satisfies `done_when` in plain language.

**Reflect** gives strategic hints ("use Run dialog") not element names — act maps hints to SCREEN.

### 7.2 Signal flow (topology edges)

```
goal_inbox ─ready─► planner ─plan_ready─► scheduler ─step_ready─► bus_check
                      │ retry_plan ▲          │ plan_complete ─► bus_post ─► satisfied
                      │            │          │
                      └─interrupt────┘          │
bus_check ─no_interrupt─► observe ─screen_ready─► act ─acted─► verify
                      │                              │ act_failed
                      │                              ▼
                      │                           reflect
                      │                              │ retry → scheduler
                      │                              │ replan → planner
                      │                              │ escalate → self_modify
verify ─step_confirmed─► scheduler
verify ─step_denied────► reflect
self_modify ─modified─► planner
```

Cycle delay between nodes: `runtime.cycle_delay_ms` = 300 ms.

Max graph cycles: `limits.max_cycles` = 300.

---

## 8. Topology nodes (wiring.json)

### 8.1 goal_inbox (type: entry)

- Handler: `node_entry` — returns signal `ready`.
- No LLM. Pass-through start.

### 8.2 planner (type: planner)

- Handler: `node_planner` — calls `call_node("planner")`.
- Parses `record_type: task` → `data.steps[]`.
- Signals: `plan_ready`, `retry_plan` (parse fail, max `limits.planner_retries` = 3), `plan_failed`.
- User blocks: GOAL, REASONING_CHAIN, PLANNER_REASONING — **no SCREEN**.

### 8.3 scheduler (type: scheduler)

- Handler: `node_scheduler` — pure Python.
- Sets `current_step` and `step_goal` from `plan[step]`.
- Signals: `step_ready`, `plan_complete`.

### 8.4 bus_check (type: bus_check)

- Handler: `node_bus_check` — reads `bus.json`.
- Signals: `no_interrupt`, `interrupt` (new goal on bus for this slot).

### 8.5 observe (type: observe)

- Handler: `node_observe` — calls `observe_screen()` unless `no_desktop`.
- Sets `state.screen`.
- Signal: `screen_ready`.

### 8.6 act (type: act)

- Handler: `node_act` — calls `call_node("act")`, runs guards, executes verbs.
- Guards: reject `DONE` conclusion; block repeat identical action after OK.
- Signals: `acted`, `act_failed` (parse, CANNOT, guard block, LLM error).
- User blocks include **SCREEN** and **SUBTASK** (`state.step_goal`).

### 8.7 verify (type: verify)

- Handler: `node_verify` — calls `call_node("verify")` **without** fresh observe.
- Signals: `step_confirmed` (increments `step`, clears reasoning slots), `step_denied`.
- User blocks: STEP, DONE_WHEN, LAST_ACTIONS, LAST_OUTCOME, HISTORY — **no SCREEN**.

### 8.8 reflect (type: reflect)

- Handler: `node_reflect` — calls `call_node("reflect")`.
- Increments `retries`; max `limits.max_attempts` = 5 before replan.
- Signals: `retry`, `replan` (max `limits.max_replans` = 2), `escalate`.

### 8.9 self_modify (type: self_modify)

- Handler: `node_self_modify` — LLM proposes wiring patch, writes `wiring.json`, hot-reloads `WIRING` global.
- Backs up to `prompts/wiring.backup.json` (gitignored).
- Ops: `add_node`, `add_edge`, `remove_edge`, `set_guard`.

### 8.10 satisfied (type: satisfied)

- Handler: `node_satisfied` — sets `satisfied: true`, signal `idle`.

### 8.11 bus_post (type: bus_post)

- Handler: `node_bus_post` — appends telemetry to `bus.json`.
- Signal: `posted`.

### 8.12 moe_route (type: moe_route)

- Handler exists in `server.py` `NODES` registry but **is not in current topology graph**.
- Deferred / dead wiring — do not add without explicit design.

---

## 9. LLM integration

### 9.1 model.json (current values)

```json
{
  "host": "http://localhost:1234",
  "timeout": 600,
  "temperature": 0.3,
  "max_tokens": 2048
}
```

Server POSTs to `{host}/v1/chat/completions`.

Uses both `content` and `reasoning_content` from LM Studio response.

### 9.2 Prompt assembly

**System prompt** = `prompts.base` + `prompts.roles[node.prompt.role]` (unless `extends: none`).

**User message** = concatenation of `node.prompt.user.blocks[]`:

- Each block has `label`, `source`, optional `always`, `empty_template`.
- `source` resolved by `_resolve_value()` in `server.py` (`state.*`, `reasoning.*`, `topology.nodes`).

### 9.3 Reasoning capture

`reasoning_patch()` stores `reasoning_content` per circuit in `state.reasoning` and appends `state.reasoning_chain[]`.

Chain depth: `reasoning.chain_depth` = 8.

On `step_confirmed`, slots in `reasoning.clear_on_step_confirm` cleared: verify, reflect, act.

### 9.4 JSON parsing

`extract_json_objects()` scans all `{...}` in content (and reasoning if `parse_fallback`).

`parse_circuit_response()` picks object matching `reasoning.expected_record_type[circuit]`.

| circuit | expected record_type |
|---------|---------------------|
| planner | task |
| unified | action |
| verifier | verdict |
| reflector | diagnosis |
| self_modify | wiring_patch |

---

## 10. desktop.py — SCREEN capture

**Method:** hover-probe only. **No UIA tree walk** (removed in `2ab6acb`).

1. Get foreground window HWND.
2. Move cursor in sine-modulated grid (`PROBE_STEP_PX` = 90) across window client area.
3. `element_from_point` at each probe point.
4. Deduplicate elements; assign `[ID]` keys.
5. Classify actionable: `write` for Edit/ComboBox/Document; `click` for buttons; Text is read-only in SCREEN output.

**Implication:** If the wiring-editor browser is focused, SCREEN shows browser/IDE elements — not Notepad. User must focus target app or minimize dashboard for desktop tasks.

**Output format (abbreviated):**

```
FOCUSED: Notepad
  [1] Edit "" = (empty, focused)
  [2] Button "Close"
```

Act must use `[ID]` or name substring from this text.

---

## 11. actions.py — verbs

Configured in `wiring.json` → `verbs`:

| verb | behavior |
|------|----------|
| click | center of element bbox, `SendInput` click |
| write | click target if named, Ctrl+A, type text |
| press | single key |
| hotkey | split target on `+` or `,` |
| scroll | wheel at element |
| focus | `SetForegroundWindow` by title substring |

`_resolve()` prefers Edit/ComboBox over fuzzy Text name match.

---

## 12. Guards (act node)

From `wiring.json` → `guards.advance_hints`:

- After `hotkey win` with Run dialog visible → hint to write app name in Open field.
- After `write` into Run Open → hint to press Enter.
- After `focus` → hint to interact with window content.

`check_repeat_block`: if same actions as last turn and last outcome contained `OK`, block repeat.

---

## 13. HTTP API (server.py)

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/health` | — | `{ok, nodes, node_circuits, slot, port}` |
| GET | `/wiring` | — | full wiring.json |
| POST | `/wiring` | wiring JSON | `{reloaded, nodes}` hot-reload |
| GET | `/state` | — | state.json contents |
| GET | `/bus` | — | bus.json contents |
| GET | `/` | — | wiring-editor.html bytes |
| GET | `/events` | — | SSE stream |
| POST | `/node/{type}` | `{state, config?}` | `{signals, state_patch, ...}` |
| POST | `/run` | `{goal}` | `{started: true}` background thread |
| POST | `/resume` | — | resumes from state.json |
| POST | `/interrupt` | `{goal}` | posts goal to bus |
| POST | `/bus/post` | message | append bus |

SSE events emitted by graph engine:

- `node` — `{c, id}` cycle and node id
- `result` — `{c, id, s}` signals
- `stop` — `{outcome}` when run ends
- `wiring_modified` — after self_modify or POST /wiring

CORS: `Access-Control-Allow-Origin: *` on JSON responses.

Connection abort on client disconnect: suppressed (no traceback spam).

---

## 14. wiring-editor.html

**Stack:** vanilla ES module script, Cytoscape 3.30.2, dagre layout, cytoscape-dagre. No React. No Babel. No build step.

**Layout:**

- Desktop: diagram left, full-height panel right (`clamp(16rem, 32vw, 22rem)`).
- Phone (≤720px): diagram ~58% `100dvh`, panel ~42% bottom.
- Toolbar scrolls horizontally on narrow screens.

**Features:**

- Auto-load `GET /wiring` on `location.origin`.
- Cytoscape chips colored by node type; bezier edges labeled with signal names.
- Click chip → edit `prompts.base`, role text, `user.blocks` JSON → Apply → Save (`POST /wiring`).
- Step / Run / Auto / Stop toolbar buttons.
- Step highlights active chip green; calls `POST /node/{type}` following topology edges.
- SSE `node` event highlights chip during `POST /run` autonomous mode.
- `ResizeObserver` on `#cy` resizes Cytoscape on window/panel changes.

**Browsers supported (explicit):** latest Chrome and Opera on Windows 11 and phone. No legacy polyfills.

---

## 15. State fields (state.json)

Populated during run (gitignored):

| Field | Meaning |
|-------|---------|
| goal | user goal string |
| plan | steps[] from planner |
| step | index into plan |
| current_step | `{description, done_when}` |
| step_goal | description string for act SUBTASK block |
| screen | last observe SCREEN text |
| history | `[{attempt, action, outcome}]` |
| last_actions | string results from act execution |
| last_actions_raw | parsed action objects |
| last_outcome | e.g. `OK: hotkey win+r: ...` or guard message |
| last_error | parse/guard/LLM error string |
| retries | reflect retry count for current step |
| replan_count | reflect replan count |
| planner_retries | planner parse retries |
| reasoning | `{planner, act, verify, reflect, last, ...}` |
| reasoning_chain | `[{circuit, text, ts}]` |
| satisfied | true when plan complete |
| _resume_node | node id for --resume |
| no_desktop | skip real observe if true |

---

## 16. Changing behavior (where to edit)

| Goal | Edit |
|------|------|
| Add/remove graph step | `topology.edges`, `topology.nodes` |
| Retry limits | `limits.max_attempts`, `limits.max_replans`, `limits.max_cycles` |
| Planner subtask style | `prompts.roles.planner` |
| Act translation rules | `prompts.roles.unified` |
| What act sees | `topology.nodes[id=act].prompt.user.blocks` |
| Verify strictness | `prompts.roles.verifier` |
| Reflect hints | `prompts.roles.reflector` |
| Shared preamble | `prompts.base` |
| Run dialog hints | `guards.advance_hints` |
| HTTP port / bind | `instance.slot`, `runtime.http_port_base`, `runtime.http_bind` |
| New node type | add handler in `server.py` `NODES` + topology node + edges |

Prefer editing via dashboard Save (`POST /wiring`) so running server hot-reloads.

---

## 17. Debugging failures

1. Read `state.json` (or `GET /state` while server running).
2. Identify last node from `_resume_node` or history.
3. Check `last_error` for parse/guard strings.
4. Check `last_outcome` — verify uses this after 1572c33.
5. Check `screen` — only act should have driven actions from it; if SCREEN is browser UI, refocus desktop.
6. Check `reasoning.act` / `reasoning.verify` in reasoning object for LLM confusion.
7. Console prints `[cycle] node_id` and `→ [signals]` each step.

**step_denied is often correct** — means subtask not yet satisfied per verify rules, not a server bug.

**act_failed paths:**

- `parse_failed` — LLM JSON wrong (check content preview in console after 652aa0b)
- `CANNOT` — act refused (may need different SCREEN focus)
- repeat block — same action twice after OK

---

## 18. Known limits (honest)

- **Latency:** ~90–120 seconds per act+verify LLM round with current model/settings. Multi-minute goals need patience.
- **Web/video:** Shakira-style goals failed in testing — UIA + DOM complexity + latency.
- **SCREEN scope:** hover-probe only sees foreground window under cursor grid — not full multi-monitor tree.
- **model.json** not merged into wiring.json yet (`wiring.llm` planned).
- **Schema validation** not implemented — `POST /wiring` accepts any JSON.
- **moe_route / colony** code remnants in server.py but not wired in topology.
- **self_modify** rarely tested in production runs.

---

## 19. What was removed (do not re-add)

- Colony / multi-rod orchestration (Phase 2 deferred)
- `reactor.py`, personalities, `prompts/personalities/`
- Separate circuit `.txt` files (inlined into wiring.json)
- Top-level `request` and `node_circuits` in wiring.json
- UIA tree walk in desktop.py
- React + xyflow + Babel wiring editor
- `probe_circuits.py`, `validate_stack.py`, `run_*_test.py`, `probe_fixtures/`
- Extra markdown docs (`ARCHITECTURE.md`, `PLAN.md`, etc.)
- Import-file / offline mode in dashboard
- Multi-port server discovery in dashboard (uses `location.origin` only)

---

## 20. Target architecture (next session)

**Single source of truth:** `prompts/wiring.json` for everything configurable.

**Frozen generic dashboard:** `wiring-editor.html` should stop accumulating feature-specific code. Once schema-driven, it only reads/writes wiring shape via HTTP.

**Next steps:**

1. Inventory `wiring.json` → formal JSON Schema document.
2. Validate `POST /wiring` against schema in server.py.
3. Refactor editor: generate chip colors, prompt block editors, node types from schema — no hardcoded `COLORS` map in JS.
4. Merge `model.json` into `wiring.llm` section.
5. Optional: verifier lightweight SCREEN keyword check without full LLM (future).

---

## 21. Handover prompt (paste to next AI session)

```
You are continuing endgame-ai on branch experiment/endgame (never main).

REPO: C:\Users\px-wjt\Downloads\endgame-ai
TAG: PROGRESS-TODO-LAN (commit 96ec326+)

VISION: One Windows rod replaces a human for long desktop tasks.
Intelligence = wiring topology + reasoning loop + verify gate.

TRACKED FILES (10 only):
  README.md, wiring-editor.html, server.py, actions.py, desktop.py,
  prompts/wiring.json, prompts/model.json, LICENSE, .gitignore, .gitattributes

RUNTIME (gitignored, delete freely): state.json, bus.json, __pycache__/

ARCHITECTURE (as of 1572c33):
  planner: abstract subtasks, NO SCREEN
  act (unified): ONLY circuit with SCREEN — maps subtask → UIA verbs
  verify: STEP + DONE_WHEN + LAST_OUTCOME, NO observe_screen()
  reflect: strategic hints, NO SCREEN
  desktop.py: hover-probe only, NO tree walk
  server.py: ThreadingHTTPServer, extract_json_objects multi-parse
  dashboard: Cytoscape + dagre, responsive 100dvh, LAN 0.0.0.0:9078

YOUR FOCUS: wiring-editor.html + wiring.json JSON Schema
  - Schema drives validation and editor UI
  - HTML frozen generic — no more hardcoded node types in JS
  - POST /wiring validates against schema

TEST REALITY:
  - Notepad hello: can PASS in ~5 min with desktop focused
  - Long web goals: FAIL (latency + UIA) — architecture loops correctly
  - step_denied = verify says subtask not done (usually correct)
  - act_failed = parse, CANNOT, or guard — check last_error + screen focus

DO NOT RE-ADD: colony, personalities, .txt prompts, UIA tree walk,
  React editor, dev harness scripts, extra markdown files.

START:
  python server.py
  http://127.0.0.1:9078
```

---

## 22. License

See `LICENSE` file in repository root.

---

## 23. Appendix — full edge list (wiring.json)

| from | to | on (signal) |
|------|-----|-------------|
| goal_inbox | planner | ready |
| planner | scheduler | plan_ready |
| planner | planner | retry_plan |
| scheduler | bus_check | step_ready |
| scheduler | bus_post | plan_complete |
| bus_post | satisfied | posted |
| bus_check | observe | no_interrupt |
| bus_check | planner | interrupt |
| observe | act | screen_ready |
| act | verify | acted |
| act | reflect | act_failed |
| verify | scheduler | step_confirmed |
| verify | reflect | step_denied |
| reflect | scheduler | retry |
| reflect | planner | replan |
| reflect | self_modify | escalate |
| self_modify | planner | modified |
| self_modify | reflect | modify_failed |

---

## 24. Appendix — error strings (wiring.json errors)

| key | message |
|-----|---------|
| parse_failed | parse_failed: respond with JSON only |
| act_done_rejected | DONE is invalid — verify confirms completion |
| act_cannot | CANNOT |
| act_bad_conclusion | bad conclusion: {conclusion} |
| verify_parse_failed | verify parse failed |
| reflector_parse_failed | reflector parse failed or wrong record_type |
| planner_parse_failed | planner parse failed |
| planner_empty | planner empty plan |
| self_modify_invalid | LLM returned invalid patch |

---

## 25. Appendix — limits (wiring.json)

| key | value |
|-----|-------|
| max_attempts | 5 |
| max_replans | 2 |
| max_cycles | 300 |
| history_depth | 10 |
| bus_max | 200 |
| planner_retries | 3 |

---

*End of README. This document reflects repository state at tag `PROGRESS-TODO-LAN` and commits through `96ec326` on branch `experiment/endgame`.*