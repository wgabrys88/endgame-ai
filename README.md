# Endgame-AI

Local Windows desktop **Reason–Observe–Decide (ROD)** graph operator. Python stdlib only (no pip). The runtime observes UIA, executes declarative verbs, evaluates wiring rules, and hot-reloads `prompts/wiring.json`.

**Branch:** `codex/self-referential-relay`  
**Platform:** Windows 10/11  
**Entry point:** `server.py` (stdlib `http.server`, not FastAPI)

> Treat **code + wiring JSON** as truth. This README is the single handover document for human operators and external AI agents.

---

## What it does

Endgame-AI pursues user goals through a fixed graph loop:

```
goal_inbox → moe_route → planner → scheduler ↔ (bus_check → observe → act → verify | reflect | self_modify) → bus_post → satisfied
```

- **Slot 1** (`prompts/wiring.json`): primary desktop operator (Notepad, Chrome navigation, YouTube, chat flows).
- **Slot 2** (`prompts/wiring_relay.json`): browser-chat relay worker (captures high-intelligence answers into `MEMORY.llm_response`).
- **Cognition** is pluggable: LM Studio (`transport: openai`) or **file-proxy** (any coding agent writes JSON response files).

Shell access is for **server control, validation, and file-proxy responses** — not valid proof of desktop/browser control. Proofs require Endgame-AI **action history** and final **`/state`**.

---

## Repository layout

| Path | Role |
|------|------|
| `server.py` | HTTP API, ROD loop, rule engine, LLM calls, self-modify |
| `desktop.py` | UIA observation, window tokens `[W#]`, `focus_window`, `open_url` |
| `actions.py` | Verb dispatch (`execute_verb`) |
| `colony.py` | Multi-slot compatibility wrapper |
| `prompts/wiring.json` | Slot 1 brain: rules, topology, roles, limits, observe |
| `prompts/wiring_relay.json` | Slot 2 relay wiring |
| `prompts/wiring-schema.json` | Wiring validation schema |
| `prompts/model.json` | Slot 1 cognition config |
| `prompts/model_relay.json` | Slot 2 cognition config |
| `wiring-editor.html` | Operator panel (graph + wiring audit) |
| `test_mechanical_fixes.py` | Focus + wait-deny regression tests |
| `run_verification.py` | Captures verification artifacts to scratch dir |
| `p0_file_proxy_runner.py` | P0 benchmarks with scripted file-proxy cognition |

Runtime artifacts (not source): `state.json`, `state.slot*.json`, `bus.json`, `comms/**`.

---

## Authoritative wiring facts (Slot 1)

Inspect `prompts/wiring.json` directly — counts drift when rules/topology change.

| Item | Current value |
|------|----------------|
| Declarative rules | **32** |
| Topology nodes | **12** |
| Topology edges | **22** (includes `reflect → bus_post` on `give_up`) |
| `verb_normalize` entries | **5** |
| `SELF_MODIFY_OPS` | **15** (`server.py`) |
| `limits.max_attempts` / `max_replans` | **7** / **3** |
| `limits.max_self_modify` | **3** |
| `observe.desktop_tree_enabled` (Slot 1) | **false** |

Slot 2 relay: **13 rules** (`confirm_relay_wait` removed — wait is recovery only, not confirmation).

---

## Quick start

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
$env:PYTHONIOENCODING = 'utf-8'
python server.py
```

Open the panel: `http://127.0.0.1:9078/` (Slot 1 instance; see **Ports** below).

### Run a goal (Slot 1)

```powershell
# Ensure Slot 1 server is running (python server.py with wiring instance.slot=1)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/run `
  -ContentType 'application/json' -Body '{"goal":"open notepad and type hello"}'
```

Poll progress:

```powershell
Invoke-RestMethod http://127.0.0.1:9078/state
Invoke-RestMethod http://127.0.0.1:9078/health
```

### Root workbench (multi-slot)

Start root on base port, then manage slots from the panel or API:

```powershell
# Root uses instance.slot=0 → port 9077 when wired that way; spawn workers via panel
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/slots/start `
  -ContentType 'application/json' -Body '{"slots":[1,2]}'
```

---

## Ports

`http_port = http_port_base + slot` when `http_port_slot_offset` is true (default).

| Instance | Default port | Wiring |
|----------|--------------|--------|
| Root / slot 0 | 9077 | `runtime.http_port_base` |
| Slot 1 | 9078 | `instance.slot: 1` in `wiring.json` |
| Slot 2 | 9079 | `instance.slot: 2` in `wiring_relay.json` |

**There is no `/slots/status` endpoint.** Use:

- `GET /system` — root system snapshot
- `GET /health` — per-instance health (`model_transport`, `port`, nodes)
- `GET /state` — per-instance run state (goal, step, history, screen, memory)
- `POST /slots/start` / `/slots/stop` — root slot manager responses

---

## Cognition backends

### File-proxy (default in repo)

`prompts/model.json` → `transport: file_proxy`

| Queue | Request | Response |
|-------|---------|----------|
| Slot 1 cognition | `comms/slot1_cognition/request.json` | `comms/slot1_cognition/response.json` |
| Slot 2 cognition | `comms/relay_cognition/request.json` | `comms/relay_cognition/response.json` |
| Browser relay handoff | `comms/llm_proxy/request.json` | `comms/llm_proxy/response.json` |

Clear stale queues before a new benchmark:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/llm-proxy/clear `
  -ContentType 'application/json' -Body '{"confirm":true}'
```

### OpenAI-compatible (LM Studio)

Set `transport: openai` in the slot's `model.json` and point `host` at `/v1/chat/completions`.

---

## Handover: external AI agent as file-proxy LLM

When Endgame-AI uses `file_proxy`, a stronger coding agent (Codex, Claude Code, Grok, etc.) **is** the cognition backend. Endgame-AI still owns the state machine, observe/act, verify, and reflect.

### Contract

1. Read `GET /health` and `GET /state` on the correct slot port.
2. Poll the active `comms/.../request.json`.
3. Write `comms/.../response.json` with the **same `id`** as the request.
4. Two-pass LLM: first pass may be reasoning; when user content contains **`DECIDE NOW`**, `content` must be exactly one role JSON object.

### Response shape

```json
{
  "id": "<same request id>",
  "choices": [{
    "message": {
      "content": "<JSON string for the circuit>",
      "reasoning_content": "<short reasoning>"
    }
  }]
}
```

### Circuit outputs

| Circuit | `record_type` | Notes |
|---------|---------------|-------|
| planner | `task` | `data.steps[]` with `description` + `done_when` |
| act | `action` | `data.conclusion`: `EXECUTE` \| `CANNOT`; `data.actions[]` |
| verifier | `verdict` | `data.confirmed` boolean |
| reflector | `diagnosis` | `data.should_replan` boolean |
| self_modify | `wiring_patch` | bounded wiring mutation |

### Act verbs

`click`, `write`, `press`, `hotkey`, `focus`, **`open_url`**, `scroll`, `wait`, `remember`, `llm_request`, `llm_wait_response`

### Focus and navigation (mechanical layer)

- **WINDOWS** lines in SCREEN include stable tokens: `- [W1] YouTube - Google Chrome`
- **focus** target: `[W1]`, full title, or `hwnd:<id>` — resolver prefers observed HWND over fuzzy scan
- **open_url**: `target=chrome|edge`, `value=<url>` — launches browser without prior focus (`start chrome <url>`)
- **click/write/scroll**: only observed `[ID]` targets from SCREEN
- Chat prompts must **not** go to address bars; URL navigation **may** use address bar or `open_url`

### Proof rules for agents

- Do **not** manually drive Chrome/Notepad outside Endgame-AI when claiming a desktop proof.
- A benchmark passes only when **`history` + `last_outcome` + `satisfied`** show it — not when a plan was written.
- Wait-only steps must **not** confirm response receipt; memory/`llm_response` evidence required.
- Clear stale file-proxy requests before starting a new goal (stale pending request blocks the planner).

---

## Mechanical layer (recent fixes)

### Observation–action focus contract

- `desktop.resolve_window_target()` shared by SCREEN render and `actions.execute_verb("focus", ...)`
- Snapshot `windows[]` carries `token`, `hwnd`, `title`
- `focus_window(title, window_infos)` uses observed HWND first, then title fallback

### Browser navigation primitive

- `open_url` verb in `actions.py` / `desktop.open_url()`
- Verify rule `confirm_browser_open_url` when domain needle appears in screen/title after `open_url`

### Wait / response semantics

- `deny_response_no_evidence` broadened (streaming, assistant, chatbot, …)
- `deny_wait_only_content_receipt` — wait + content-implying `done_when` → deny
- `confirm_llm_response_received` requires `memory.llm_response` ≥ 20 chars
- Relay: `confirm_relay_wait` **removed**

### Self-modify bounds

- `max_self_modify: 3` — exhaustion → `give_up` → `satisfied: false`

### Observe alignment

- `desktop.OBSERVE_DEFAULTS.desktop_tree_enabled` matches wiring; `configure_observation()` is the runtime source of truth after wiring load.

---

## Benchmarks

Run from **clean state**: clear file-proxy queues, remove stale `state.slot1.json`, start server, then post goal.

| Priority | Goal | Proves |
|----------|------|--------|
| P0 | `open notepad and type hello` | Run dialog, write, `confirm_launch_chain` |
| P0 | `navigate to google.com in chrome` | `open_url` or ctrl+l nav, `confirm_browser_navigation` / domain needle |
| P0 | `play Shakira Waka Waka on YouTube` | Browser stack, video page, `confirm_youtube_playback` |
| P1 | `have a conversation with an AI chatbot` | Chat submit rules, wait deny, memory capture |
| P2 | Self-modify after focus failures | Bounded `max_self_modify`, wiring_patch recovery |

```powershell
python test_mechanical_fixes.py
python run_verification.py
python p0_file_proxy_runner.py   # scripted file-proxy; requires Slot 1 server stopped/started clean
```

---

## HTTP API (per instance)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Nodes, port, model transport |
| GET | `/system` | Root system snapshot (root instance) |
| GET | `/state` | Full run state |
| POST | `/run` | Enqueue goal |
| POST | `/resume` | Resume saved state |
| POST | `/pause` | Pause loop |
| POST | `/llm-proxy/clear` | Clear cognition file-proxy (`confirm: true`) |
| POST | `/relay/clear` | Clear browser relay handoff |
| POST | `/slots/start` | Start managed slot workers (root) |
| POST | `/slots/stop` | Stop managed slot workers (root) |
| POST | `/slots/run` | Post goal to a slot via root |
| GET | `/wiring/audit` | Wiring validation report |
| POST | `/wiring` | Hot-reload wiring (validated) |

---

## Observation behavior (why the mouse sweeps repeatedly)

Each trip through the **observe** node calls `desktop.observe()`, which runs one **full-screen hover scan** when `observe.hover_scan_enabled` is true (~400+ probe points; visible cursor movement).

That is **expected once per step** before act. You see **multiple sweeps back-to-back** when the graph **retries**:

```
scheduler → bus_check → observe (hover scan) → act → verify
  → reflect (deny/fail) → retry → scheduler → bus_check → observe (again) …
```

Wiring also allows up to `observe.wait_retries` (default **6**) extra observe passes inside a single observe node if fewer than `min_elements` actionable `[ID]` targets are found (750 ms apart).

If verify keeps denying (e.g. file-proxy returns `confirmed: false` while actions were structurally OK), retries stack and the hover scan repeats — even though act may have partially succeeded (e.g. hello typed on a retry while still on step 0). Check `history`, `step`, `retries`, and `last_error` in `/state`.

---

## Known limitations (honest status)

- **MoE delegation** on Slot 1 is inert when `desktop_exec` permission is present (browser goals stay on Slot 1).
- **`plan_failed`** exits to `bus_post` without reflect/replan recovery.
- **YouTube playback** has structural verify rules but no audio/OCR proof; ads/login/cookie paths are partial.
- **File-proxy benchmarks** fail if a stale `request.json` is left pending — always clear before a new run.
- **P0 E2E** requires a live Windows session with Chrome available for navigation goals.

---

## Development

```powershell
python test_mechanical_fixes.py
```

Wiring changes: update `RULE_CONDITIONS` / `RULE_CHECKERS` in `server.py` when adding rule `match` keys. Prefer declarative rules in `wiring.json` over Python policy.

Self-modify creates timestamped backups: `prompts/wiring.backup.<stamp>.json`.

---

## License / status

Research/operator tooling. Not production-hardened. Update this README when wiring counts, ports, or handover contracts change.