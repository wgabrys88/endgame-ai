# endgame-ai

A living Windows desktop organism: Python drives real mouse/keyboard/screen I/O, `wiring.json` controls topology and brain config, and hot-swappable nodes in `live_nodes/` implement circuits (planner, act, verify, …).

**Branch:** `brains-integration` — multi-transport brain swap, unified raw logging, workbench panel.

Stdlib only in the organism core. Fail-hard on transport errors; no silent fallbacks.

---

## Architecture

| Piece | Role |
|-------|------|
| `organism.py` | Living loop; atomic `state.json` |
| `brain.py` | Stateless transports + ROD two-call `think()` |
| `nodes.py` + `live_nodes/` | Node graph (seed templates in `seed_nodes/`) |
| `wiring.json` | Topology, prompts, verbs, brain transport |
| `workbench.py` | Control panel at http://localhost:8800 |
| `actions.py`, `desktop.py` | Windows desktop body |

### ROD (two-call cognition)

Every decision = **two stateless brain calls**:

1. **Call 1** — model reasons (thinking / `reasoning_content` / stream `thought` chunks).
2. **Call 2** — same context + `ROD_REASONING_CONTENT:` echo → model commits one typed JSON record.

---

## Brain transports

Selected by `wiring.json` → `model.transport`:

| Transport | Kind | Notes |
|-----------|------|-------|
| `openai` | HTTP `/v1/chat/completions` | LM Studio default (`localhost:1234`) |
| `xai_responses` | HTTP `/v1/responses` | Needs `XAI_API_KEY` |
| `opencode` | CLI `opencode run` | `prompt_mode=file` on Windows |
| `grok_build` | CLI `grok -p` | `streaming-json` output |
| `file_proxy` | `comms/request.json` → `comms/response.json` | Human/agent fills response |
| `browser_ai` | Stub | Not implemented |

Swap transport in workbench or edit `wiring.json`; organism rebinds on next loop.

---

## Logging contract

| Tier | Path | Purpose |
|------|------|---------|
| **Live snapshot** | `state.json` | Current truth (node, goal, plan, screen summary) |
| **Live events** | `comms/runtime.ndjson` | Slim organism lifecycle only (`node_start`, `narration`, …) |
| **Forensic raw** | `<timestamp>.txt` (workspace root) | Single append-only brain log — one JSON line per entry |

### Raw brain log (`*.txt`)

- Created once per process at first brain call (e.g. `20260630T075055.txt`).
- Each entry: `ts`, `iso`, `seq`, `phase` (`request`|`response`), `transport`, `model`, `raw` (wire bytes), optional `rod_feedback`, `elapsed_s`.
- Captured at **transport boundaries** (HTTP body, CLI argv/stdout, file_proxy JSON).
- Usage, Grok metadata, and future provider fields are derived from `raw` at read time — not separate ledgers.

**Do not poll forensic logs as live state.** Workbench reads `state.json` + tails `*.txt` for debugging.

Removed: `session-*.log`, `brain_usage.ndjson`, `brain_io.ndjson`, duplicate brain events in runtime.

---

## Workbench

```powershell
python workbench.py          # http://localhost:8800
```

| Feature | API / UI |
|---------|----------|
| Live state | `/api/status` |
| Edit brain | Save brain → `wiring.json` |
| Probe transport | Probe selected |
| ROD falsification | **Test ROD (2-call)** → `POST /api/brain_test` |
| File proxy handoff | Shows `request.json`; write `response.json` |
| Forensic tail | Raw brain log / runtime.ndjson viewer |
| Usage tables | Derived from raw log response entries |

**ROD test limits:** `brain_test_timeout_s` = **45** (wiring + workbench). One `think()` only (`parse_retries=0`). Client aborts fetch after 45s.

### File proxy — you are the brain

`file_proxy` writes `comms/request.json` and polls `comms/response.json`. The workbench shows pending prompts; any agent (or you) writes the response file. For ROD tests, answer call 1 with reasoning text, call 2 with the required JSON record.

---

## Run

```powershell
python workbench.py
python organism.py --reset "observe the screen"
python organism.py --reset --max-ticks 1 "observe the screen"
```

---

## Repo hygiene

`.gitignore` is allowlist-only: core source + `seed_nodes/` tracked; `comms/`, `live_nodes/`, `state.json`, `*.txt` run logs, terminals ignored.

---

## Invariants

- ROD is always two stateless calls per `think()`.
- Wiring controls topology; nodes are hot-swappable.
- Fail-hard on transport errors; no fallback providers.
- Forensic `*.txt` is append-only truth for brain wire I/O.