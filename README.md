# endgame-ai

**A living Windows desktop organism — not an agent framework.**

One JSON file wires the brain. Python is just muscles. The browser is the window into the skull.

---

## Running

```powershell
# Autonomous (server drives itself, browser observes)
python server.py --run "open notepad and write hello"

# Passive (browser drives the graph step-by-step)
python server.py

# Resume after restart
python server.py --resume

# Colony (multiple rods, shared bus)
python reactor.py --goal "open chrome and search for cats"
```

Open `http://127.0.0.1:9077` for the visual editor + live observation dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  prompts/wiring.json              THE BRAIN (declarative)    │
│  10 nodes, 14 edges, guards, personas                       │
│  All control flow. No Python if/else for routing.           │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  server.py (521 LOC)           THE BODY (executable)        │
│  11 node handlers. Graph engine. HTTP + SSE.                │
│  Stateless per-node: receives state → returns signals+patch │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  bus.json                      THE NERVOUS SYSTEM (shared)   │
│  All rods read/write. Interrupts, telemetry, goals.         │
└─────────────────────────────────────────────────────────────┘
```

## Topology (signal flow)

```
goal_inbox → planner → scheduler → bus_check → observe → act → verify → scheduler
                ▲                                                          │
                │ replan                                           step_confirmed
                │                                                          │
             reflect ◄──────── step_denied ─────────────────── verify ─────┘
                │
                └── retry → scheduler (same step, +1 retries)

scheduler → plan_complete → bus_post → satisfied (terminal rest)
bus_check → interrupt → planner (new goal replaces current plan)
```

## Node Types

| Type | LLM? | Purpose |
|------|------|---------|
| entry | no | Start signal |
| planner | yes | Goal → `[{description, done_when}]` |
| scheduler | no | Track step index, emit step_ready or plan_complete |
| bus_check | no | Poll bus for interrupt goals |
| observe | no | Capture desktop UIA tree |
| act | yes | Build prompt + guards + execute verbs |
| verify | yes | Fresh screen + check done_when evidence |
| reflect | yes | Diagnose failure, retry or replan |
| satisfied | no | Terminal rest state |
| bus_post | no | Post telemetry to shared bus |
| moe_route | no | MoE gate: self or delegate (colony only) |

## Files

```
server.py              599 LOC — node handlers + graph engine + HTTP/SSE
reactor.py             153 LOC — colony supervisor (spawn/monitor/respawn rods)
actions.py             138 LOC — desktop verb executor (click/write/press/hotkey/scroll/focus)
desktop.py             824 LOC — Windows UIA wrapper (ctypes, no pip)
wiring-editor.html     738 LOC — React Flow editor + native UIA toolbar + mock panel

prompts/
  wiring.json          87 LOC — THE TOPOLOGY (11 nodes, 17 edges, guards, limits)
  unified.txt          — executor system prompt
  planner.txt          — planning system prompt
  verifier.txt         — verification system prompt
  reflector.txt        — diagnosis system prompt
  manager.txt          — peer orchestration prompt (swap)
  model.json           — LM Studio endpoint config (max_tokens: 2048)
  personalities/       — executor/reviewer/comms_operator personas
```














  model.json           — LM Studio endpoint config
  schema.json          — response format reference
  personalities/
    implementor.txt    — desktop executor persona
    reviewer.txt       — verification-only persona
    comms_operator.txt — MoE routing persona
```


## Testing

### UIA Self-Test (real Windows, Chrome with --force-renderer-accessibility)

The native HTML toolbar exposes all buttons to Windows UIA.
The system can observe its own dashboard and click UI elements autonomously:

```
observe_screen() → sees Button "Step", StatusBar "Connected: 11 nodes"
execute_verb("click", "Step") → Chrome prompt dialog appears
observe_screen() → sees Edit "Goal:" + Button "OK"
execute_verb("write", "Goal:", "open notepad") → types goal
execute_verb("click", "OK") → fires goal_inbox node
observe_screen() → reads "✓ goal_inbox → ready → planner"
```

### Mock Testing (no Windows required)

The sidebar has a 🧪 Mock Inject panel with screen presets (Desktop, Run, Chrome, Notepad).
Inject a fake screen → click Step → node executes with mock data + real LLM.
The 📝 State Editor lets you edit raw JSON state between steps.
The 📝 State Editor shows raw JSON state. Edit it directly to test
specific scenarios (set retries=5, inject history, force escalation, etc.).
## How to Extend (no code changes needed for most)

| Want to... | Do this |
|------------|---------|
| Change behavior | Edit edges in wiring.json |
| Add a guard | Add to `guards.advance_hints` in wiring.json |
| New capability | Add node to wiring.json + one function in NODES dict |
| New rod type | New file in `prompts/personalities/` + reactor config |
| Change LLM | Edit `prompts/model.json` |
| Different prompt | Edit `.txt` files |

## Key Features

- **Autonomous loop** — runs without browser, `--run "goal"`
- **Multi-step planning** — LLM decomposes goal into concrete steps
- **Verification** — LLM checks screen evidence after each action
- **Retry + replan** — diagnoses failures, retries up to max_attempts, then replans
- **Multi-task interrupt** — bus_check polls for new goals mid-execution
- **Guards** — repeat_block, premature_done, advance_hints prevent loops
- **Reasoning feedback** — history injected into prompts so LLM learns from prior attempts
- **State persistence** — survives restart via state.json + `--resume`
- **Persona system** — different personality = different rod behavior
- **Shared bus** — inter-rod communication via bus.json
- **MoE routing** — comms_operator delegates by competence
- **Colony** — reactor.py spawns N rods, monitors health, auto-respawns
- **SSE observation** — browser connects to /events for live node highlighting
- **Rod reproduction** — copy folder + change slot/persona/port

## Constraints

- Python stdlib only — zero pip install
- Wiring-first — JSON topology, not Python if/else
- Browser is dashboard, not brain — system runs without it
- Single HTML file — CDN imports only, no build step
- LM Studio local — no cloud API keys
- CRLF line endings — Windows workspace

---

## Appendix A: AI Handover Prompt

Use this prompt when starting a new AI session to continue work on this project:

```
You are continuing work on endgame-ai — a living Windows desktop organism.
Location: C:\Users\<USER>\Downloads\endgame-ai (or equivalent path)
Branch: codex-unify-bus

Architecture:
- server.py (599 LOC): 12 node handlers, graph engine, HTTP/SSE server on :9077
- wiring.json: 11 nodes, 17 edges — THIS is the program (no Python if/else routing)
- wiring-editor.html (738 LOC): React Flow dashboard + native UIA toolbar
- actions.py: bridge to desktop.py — observe_screen() + execute_verb(verb, target, value)
- desktop.py: Windows UIA via ctypes (no pip)

Key patterns:
- Node handler signature: def node_X(state, config) -> {"signals": [...], "patch": {...}}
- HTTP: POST /node/{type} with {"state":{...}} → {"signals":[], "state_patch":{}}
- Graph engine: fires node → reads signals → follows edges (field: "on") → fires next
- LLM: localhost:1234, model.json has host/timeout/temperature, ~45-90s per call
- Guards: repeat_block, premature_done, advance_hints (all in wiring.json)
- Self-modify: reflect→escalate→self_modify→modified→planner (LLM rewrites wiring)

For real Windows interaction, MUST use Windows Python:
  "/mnt/c/Program Files/Python313/python.exe" (from WSL)
  or just `python` (from Windows terminal)

Chrome UIA visibility requires: --force-renderer-accessibility
Only NATIVE HTML elements (outside React root) are visible to UIA.

To test without Windows desktop: set state.no_desktop=true + state.screen="(fake screen)"
To test with real desktop: use Windows Python, observe_screen() returns real UIA tree

Endpoints: GET /health /wiring /state /bus /events / | POST /node/{type} /run /resume /interrupt /bus/post /wiring

Read NAVIGATION.md for patterns, TEST_RESULTS.md for proven capabilities.
```

## Appendix B: Running Examples

```powershell
# === BASIC USAGE ===

# Start server (passive mode — browser or API drives execution)
python server.py

# Start server + autonomous execution
python server.py --run "open notepad and write hello world"

# Resume after crash/restart
python server.py --resume

# Colony mode (multiple rods, shared bus)
python reactor.py --goal "open chrome and search for cats"

# === BROWSER DASHBOARD ===

# Open dashboard (server must be running)
start http://127.0.0.1:9077

# Chrome with UIA accessibility (for self-testing)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --force-renderer-accessibility

# === API USAGE ===

# Step manually via HTTP
curl -X POST http://127.0.0.1:9077/node/entry -H "Content-Type: application/json" -d "{\"state\":{\"goal\":\"open notepad\",\"step\":0,\"retries\":0,\"history\":[]}}"

# Inject interrupt (new goal mid-execution)
curl -X POST http://127.0.0.1:9077/interrupt -H "Content-Type: application/json" -d "{\"goal\":\"close everything and open chrome\"}"

# Hot-reload topology
curl -X POST http://127.0.0.1:9077/wiring -H "Content-Type: application/json" -d @prompts/wiring.json

# Autonomous run via API
curl -X POST http://127.0.0.1:9077/run -H "Content-Type: application/json" -d "{\"goal\":\"navigate chrome to github.com\"}"

# === MOCK TESTING (no Windows desktop needed) ===

# Step with mock screen (observe node uses injected screen instead of real UIA)
curl -X POST http://127.0.0.1:9077/node/observe -H "Content-Type: application/json" -d "{\"state\":{\"goal\":\"test\",\"no_desktop\":true,\"screen\":\"(Windows: [1] Notepad - Untitled. [2] Edit area.)\"}}"

# Full mock cycle: entry → planner → scheduler → observe → act
curl -X POST http://127.0.0.1:9077/node/planner -H "Content-Type: application/json" -d "{\"state\":{\"goal\":\"type hello in notepad\",\"screen\":\"(Windows: [1] Notepad - Untitled. [2] Edit area empty.)\",\"step\":0,\"retries\":0,\"history\":[]}}"
```

## Appendix C: Two-Instance Setup (Observer + Worker)

Run two separate endgame-ai instances: one doing real work, another observing and correcting the first.

```
Directory layout:
  C:\endgame-ai\worker\    ← Instance 1: does the actual desktop work
  C:\endgame-ai\observer\  ← Instance 2: watches Instance 1 and corrects it
```

### Instance 1 — Worker (port 9077)

```powershell
cd C:\endgame-ai\worker
python server.py --run "open notepad and write hello world"
```

This instance:
- Runs autonomously on port 9077
- observe_screen() captures real desktop
- execute_verb() performs real keystrokes/clicks
- Follows plan → act → verify loop

### Instance 2 — Observer/Corrector (port 9078)

```powershell
cd C:\endgame-ai\observer
# Edit prompts/model.json: change nothing (same LLM)
# Edit prompts/wiring.json: add custom observer topology (see below)
python server.py --port 9078 --run "monitor worker at 127.0.0.1:9077 and correct if stuck"
```

This instance:
- Runs on port 9078
- observe_screen() sees the same desktop (including worker's Chrome/Notepad)
- Can POST to worker's /interrupt endpoint to inject corrections
- Can POST to worker's /wiring endpoint to modify worker's topology
- Can read worker's /state to see what it's doing

### Observer's goal prompt example:

```
Monitor the endgame-ai worker at http://127.0.0.1:9077.
Every 30 seconds:
1. GET /state from worker — check if stuck (retries > 3 or same node for > 2 min)
2. If stuck: POST /interrupt with a corrective goal
3. If topology seems wrong: POST /wiring with fixed topology
4. observe_screen() — verify worker's actions are producing results
5. If worker finished: report success via bus
```

### How the Observer corrects the Worker:

```powershell
# Observer reads worker state
curl http://127.0.0.1:9077/state

# Observer sees worker is stuck — injects interrupt
curl -X POST http://127.0.0.1:9077/interrupt -H "Content-Type: application/json" -d "{\"goal\":\"try using keyboard shortcut ctrl+n instead of clicking File menu\"}"

# Observer patches worker's wiring (adds a hint guard)
curl -X POST http://127.0.0.1:9077/wiring -H "Content-Type: application/json" -d @fixed-wiring.json
```

### Setup for second instance:

```powershell
# Copy the project
xcopy /E /I C:\endgame-ai\worker C:\endgame-ai\observer

# Edit observer's config to use different port and bus
# In observer/server.py line 1 or via env var:
set ENDGAME_PORT=9078
set ENDGAME_BUS=C:\endgame-ai\shared-bus.json

# Both instances can share bus.json for inter-communication
# Worker posts telemetry → Observer reads it
# Observer posts corrections → Worker's bus_check picks them up
```

### Shared bus communication:

The bus is the nervous system between instances. Both read/write the same `bus.json`:

```json
[
  {"from": "worker", "type": "telemetry", "node": "verify", "outcome": "step_denied", "ts": 1718834400},
  {"from": "observer", "type": "interrupt", "goal": "use ctrl+s instead of File>Save", "ts": 1718834410}
]
```

Worker's `bus_check` node picks up observer's interrupt and replans automatically.
