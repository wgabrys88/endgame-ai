# endgame-ai

One **rod** on Windows: a graph of LLM circuits that observes the desktop, acts, verifies, and retries until the goal is done.

**Branch:** `experiment/endgame` — do not use `main`.

Intelligence lives in `prompts/wiring.json`, not in a single prompt. `server.py` runs the graph. `wiring-editor.html` is the dashboard.

---

## Repo (10 files)

```
README.md
wiring-editor.html     dashboard — Cytoscape diagram, step/run, prompt editor
server.py              graph engine, HTTP API, LM Studio calls
actions.py             verb dispatch (click, write, hotkey, …)
desktop.py             hover-probe SCREEN capture + input
prompts/wiring.json    brain — topology, prompts, policy
prompts/model.json     LM Studio host + model
LICENSE · .gitignore · .gitattributes
```

**Never commit:** `state.json`, `bus.json`, `__pycache__/`, `terminals/`, `*.log`, `prompts/wiring.backup.json`

---

## Quick start

```powershell
# Windows 11, Python 3.11+, LM Studio on localhost:1234
cd endgame-ai
python server.py
```

Console prints:

- `local   http://127.0.0.1:9078`
- `lan     http://192.168.x.x:9078` — open on phone (same WiFi)

```powershell
python server.py --run "open notepad and write hello"
```

Dashboard: open the local or LAN URL in Chrome or Opera. Wiring loads automatically from `GET /wiring`.

### Phone + firewall

```powershell
netsh advfirewall firewall add rule name="endgame-ai" dir=in action=allow protocol=TCP localport=9078
```

LM Studio stays on the PC (`localhost:1234`). Only the dashboard is exposed to LAN.

Localhost-only: `$env:ENDGAME_BIND="127.0.0.1"` before `python server.py`.

---

## Circuit separation

| Circuit | Sees SCREEN? | Role |
|---------|--------------|------|
| **planner** | No | Ordered human subtasks from GOAL (`open notepad`, `write hello`, …) |
| **act** | **Yes — only** | Maps subtask + SCREEN → one UIA action per turn |
| **verify** | No | Confirms subtask from `done_when` + act `LAST_OUTCOME` |
| **reflect** | No | Strategic hint when verify denies; no element names |

```
goal → planner → scheduler → observe → act → verify
                      ↑                    ↓ deny
                   reflect ←──────────────┘
                      ↓ replan → planner
```

Planner `done_when` is plain language (no `[ID]`, no UIA). Act translates to `win+r`, `notepad`, `enter`, etc. Verify never calls `observe_screen()`.

---

## wiring.json

```
topology.nodes[]     id, type, prompt { role, user.blocks }
topology.edges[]     from, to, on (signal)
prompts.base         shared preamble
prompts.roles        planner | unified | verifier | reflector | self_modify
reasoning.*          LM Studio reasoning_content capture + parse rules
guards, act, limits, errors, runtime, verbs
instance.slot        port = 9077 + slot (default 9078)
runtime.http_bind    0.0.0.0 for LAN dashboard
```

Edit via dashboard sidebar (click chip → edit role + blocks → Apply → Save) or edit JSON directly → `POST /wiring`.

---

## Desktop (SCREEN)

`desktop.py` uses **hover-probe only**: sine-grid cursor over the focused window, `element_from_point` at each point. No UIA tree walk.

SCREEN lists `[ID]` actionable elements. Act targets must exist in SCREEN.

---

## HTTP API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | wiring-editor.html |
| GET | `/health` | status, port, slot |
| GET | `/wiring` | full wiring.json |
| POST | `/wiring` | save + hot-reload |
| POST | `/node/{type}` | run one handler |
| POST | `/run` | autonomous loop |
| GET | `/events` | SSE live node highlight |

Server uses `ThreadingHTTPServer` so phone SSE and desktop requests do not block each other.

---

## wiring-editor.html

Vanilla JS + **Cytoscape** + dagre layout. No React.

- Desktop: diagram left, full-height panel right
- Phone: diagram top, panel bottom (`100dvh`, responsive)
- Toolbar: Save, Layout, Step, Run, Stop, Auto
- Step highlights active chip; only act talks to desktop

---

## Change behavior

| What | Where |
|------|-------|
| Graph flow | `topology.edges`, `limits.*` |
| Subtask wording | `prompts.roles.planner` |
| Act translation rules | `prompts.roles.unified` |
| What act sees | `topology.nodes[act].prompt.user.blocks` |
| Verify criteria | `prompts.roles.verifier` |

---

## Handover (next session)

Paste to continue:

```
Repo: endgame-ai, branch experiment/endgame (never main).

VISION: One rod replaces a human for long desktop tasks.
SSOT: prompts/wiring.json — everything configurable goes there.
server.py = dumb graph runner. wiring-editor.html = frozen generic
viewer/editor that only reads/writes wiring JSON over HTTP.

DONE THIS SESSION:
- Cytoscape dashboard (not React), responsive phone/desktop
- Circuit split: planner abstract subtasks, ONLY act gets SCREEN,
  verify/reflect use descriptive step + LAST_OUTCOME (no SCREEN)
- ThreadingHTTPServer, LAN bind 0.0.0.0, runtime data gitignored
- 10 essential tracked files only

NEXT SESSION FOCUS: wiring-editor.html + wiring.json SCHEMA
1. Inventory wiring.json → formal JSON Schema
2. Validate POST /wiring against schema
3. Refactor editor to be schema-driven (no hardcoded node types in JS)
4. Eventually merge model.json into wiring.llm

HTML today: GET/POST /wiring, POST /node/{type}, POST /run, SSE /events.
Cytoscape chips from topology.nodes/edges; sidebar edits prompts.base,
roles, user.blocks.

DO NOT re-add: colony, personalities, separate .txt prompts, UIA tree walk,
React/Babel editor, extra markdown files, dev harness scripts.

Debug: state.json (gitignored) — step, plan, history, last_outcome, reasoning.*
```

---

## Limits

- ~90–120s per act+verify LLM round — budget minutes for real goals
- Web/video tasks unproven (UIA + latency)
- `model.json` not yet inside wiring
- Multi-rod deferred