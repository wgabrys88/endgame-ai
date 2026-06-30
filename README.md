# endgame-ai

A living, unconstrained organism that operates a real Windows desktop. Not a traditional agent framework: Python is the body (mouse, keyboard, screen), `wiring.json` is the mind's configuration, and a swappable **brain** provides stateless cognition.

**Branch:** `brains-integration` — multi-transport brain swap, unified logging, live workbench panel.

Standard library only. No LangChain, no MCP in the organism core, no silent fallbacks.

---

## What it is

| Piece | File | Role |
|-------|------|------|
| Living loop | `organism.py` | Drives the topology graph; writes `state.json` atomically |
| Brain | `brain.py` | Stateless LLM transports + ROD two-call pattern |
| Nodes | `nodes.py` + `live_nodes/` | Hot-swappable Python circuits (planner, act, verify, …) |
| Body | `actions.py`, `desktop.py` | Windows UI Automation + input |
| Config | `wiring.json` | Topology, prompts, verbs, brain transport — single source of truth |
| Panel | `workbench.py` | Debug/control UI at http://localhost:8800 |

### ROD (Reason → Observe → Decide)

Every brain decision is **two stateless calls**:

1. **Call 1:** Model reasons (thinking / `reasoning_content` / NDJSON `thought` chunks).
2. **Call 2:** Same context + `ROD_REASONING_CONTENT:` echo → model commits one typed JSON record.

This is load-bearing even for small local models (e.g. Nemotron 4B).

### Topology (default)

```
planner → scheduler → observe → act → verify → reflect → self_modify → satisfied
```

Signals and edges live in `wiring.json` → `topology`. Change wiring, not code, to experiment.

---

## Quick start

**Terminal 1 — panel:**

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
python workbench.py
```

Open http://localhost:8800

**Terminal 2 — organism:**

```powershell
python organism.py --reset "observe the screen"
```

Optional: `--max-ticks N` to stop after N node transitions.

---

## Brain transports

Set `model.transport` in `wiring.json` or use the workbench **Brain provider** dropdown.

| Transport | Kind | How it calls (stateless) |
|-----------|------|--------------------------|
| `openai` | API | `POST /v1/chat/completions` — LM Studio default `localhost:1234` |
| `opencode` | CLI | `opencode-cli run -m <model> --format json "<short msg>" --file <prompt.txt>` |
| `grok_build` | CLI | `grok -p "<prompt>" -m grok-build --output-format streaming-json` |
| `xai_responses` | API | `POST /v1/responses` with `XAI_API_KEY` |
| `file_proxy` | Handoff | Writes `comms/request.json`, waits for `comms/response.json` (human/other agent) |
| `browser_ai` | Desktop | **Not implemented** — raises; use `file_proxy` + workbench |

**OpenCode exe** is set in wiring (`model.opencode.exe`). Use the full path to `opencode-cli.exe`.

**OpenCode prompt delivery:** `prompt_mode: file` writes the full system+user prompt to `comms/cli_prompts/*.prompt.txt`, then passes a **short positional message** plus `--file` attachment. A long string after `--file` is misread as another file path.

Organism hot-reloads brain when `wiring.json` mtime changes (no restart needed).

---

## Logging

Three tiers — panel uses only the first two for live truth:

| Tier | Path | Purpose |
|------|------|---------|
| Live | `comms/runtime.ndjson` | Compact events: `node_start`, `brain_request`, `cli_exit`, `usage`, … |
| Snapshot | `state.json` | Current organism state (written before/after every node) |
| Forensic | `comms/session-*.log` | Full prompt/response journal per process |
| Usage | `comms/brain_usage.ndjson` | Token/cost ledger |
| Optional | `comms/brain_io.ndjson` | Raw transport I/O (`log_brain_io: false` by default) |

---

## Workbench panel

Stdlib HTTP server on port **8800** (`ENDGAME_WORKBENCH_PORT` to override).

### Controls (tested on `brains-integration`)

| Control | Works | Notes |
|---------|-------|-------|
| Header health / node / brain / goal / age / seq | Yes | Polls `/api/status` every 1s |
| Pause / Resume | Yes | Stops polling when paused |
| Live event stream | Yes | Last 80 `runtime.ndjson` events, reversed |
| Narration | Yes | From `state._narration` |
| State truth / plan / history / reasoning | Yes | Compact projection from `state.json` |
| Files / last run | Yes | Mtimes, session log list, inventory |
| Brain dropdown + Save brain | Yes | POST `/api/wiring`; organism picks up on next tick |
| Provider parameter controls | Yes | Driven by `controls` schema in wiring per transport |
| Probe selected | Yes | CLI: opencode `stats`, grok `models`; API: openai `/v1/models`, xai env key, file_proxy paths |
| File proxy handoff | Yes | Shows pending `request.json`; POST writes `response.json` |
| Goal set / clear | Yes | Writes `goal.json` for next organism run |
| Usage ledger | Yes | 24h / 30d / month / all buckets |
| Usage budget bars | Yes | When `usage_limits.*.monthly_*` set in wiring |
| Prior run logs viewer | Yes | Session logs, runtime, usage, brain_io, cli prompts via `/api/logs/tail` |

**Stale detection:** Panel marks state stale when `state.json` age > 8s and organism is not active (not in a brain call).

---

## Falsification tests

### OpenCode (single stateless call)

```powershell
python -c "import json; from brain import Brain; b=Brain(json.load(open('wiring.json'))['model']); print(b._call('test','Return {\"ok\":true} only',0.3))"
```

Pass: prints content with `ok` true, no `File not found` on trailing argv.

### Grok Build CLI

Switch transport to `grok_build` in workbench, then:

```powershell
python organism.py --reset --max-ticks 1 "observe the screen"
```

Pass: `runtime.ndjson` has `cli_start`/`cli_exit`, planner `plan_ready` in state.

### LM Studio

Start LM Studio server, set transport `openai`, run same organism command.

Pass: `brain_request`/`brain_response` in runtime; no HTTP errors.

### Workbench APIs

With `python workbench.py` running:

```powershell
curl http://localhost:8800/api/status
curl http://localhost:8800/api/logs/tail?kind=session&tail=20
curl "http://localhost:8800/api/provider_stats?provider=opencode"
```

---

## Project layout

```
organism.py          # main entry
brain.py             # cognition transports
nodes.py             # node loader + call_node (ROD contract)
workbench.py         # debug panel
wiring.json          # topology + prompts + brain config
seed_nodes/          # immutable node templates → copied to live_nodes/
live_nodes/          # runtime nodes (gitignored, hot-swapped)
actions.py desktop.py
comms/               # runtime logs (gitignored)
state.json goal.json # runtime artifacts (gitignored)
```

---

## Philosophy

- **Wiring is the brain** — topology and prompts are data, not hardcoded flow.
- **Fail hard** — transport errors raise; no fallback provider.
- **Self-modify** — `self_modify` node can patch `wiring.json` including `model.transport`.
- **Unconstrained** — the organism can install software, explore, and reinterpret goals across a run.

Do not recreate deleted legacy entrypoints (`server.py`, `colony.py`, `reactor.py`).

---

## License

See `LICENSE`.