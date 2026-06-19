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
server.py              521 LOC — node handlers + graph engine + HTTP/SSE
reactor.py             153 LOC — colony supervisor (spawn/monitor/respawn rods)
actions.py             138 LOC — desktop verb executor (click/write/press/hotkey/scroll/focus)
desktop.py             824 LOC — Windows UIA wrapper (ctypes, no pip)
wiring-editor.html     626 LOC — React Flow visual editor + SSE live observation

prompts/
  wiring.json          87 LOC — THE TOPOLOGY (10 nodes, 14 edges, guards, limits)
  unified.txt          — executor system prompt
  planner.txt          — planning system prompt
  verifier.txt         — verification system prompt
  reflector.txt        — diagnosis system prompt
  manager.txt          — peer orchestration prompt (swap)
  model.json           — LM Studio endpoint config
  schema.json          — response format reference
  personalities/
    implementor.txt    — desktop executor persona
    reviewer.txt       — verification-only persona
    comms_operator.txt — MoE routing persona
```


## Mock Testing (no Windows required)

The browser dashboard includes a built-in mock testing panel:

1. Open http://127.0.0.1:9077
2. Click ⏩ Step → enter a goal
3. In the sidebar: 🧪 Mock Inject section appears
4. Click a Screen Preset (Desktop, Run, Chrome, Notepad, etc.)
5. Click 💉 Inject Screen → state gets the mock screen + no_desktop flag
6. Click ⏩ Step again → the node executes with your mock screen
7. After each step, inject a NEW preset simulating what changed

This lets you test the full plan→act→verify loop with real LLM decisions
but fake desktop observations — proving the logic works without Windows.

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
