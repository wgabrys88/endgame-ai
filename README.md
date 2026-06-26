# Endgame-AI

Local Windows desktop **Reason–Observe–Decide (ROD)** graph operator. Python stdlib only (no pip). The runtime observes UIA, executes declarative verbs, evaluates wiring rules, and hot-reloads `prompts/wiring.json`.

**Branch:** `codex/self-referential-relay`  
**Platform:** Windows 10/11  
**Entry point:** `server.py` (stdlib `http.server`, not FastAPI)  
**Workspace:** `C:\Users\ewojgab\Downloads\endgame-ai`

> Treat **code + wiring JSON** as truth. This README is the single handover document for human operators and external AI agents.

---

## Copy-paste handover prompt (for any AI coding agent)

Paste the block below into Codex, Claude Code, Cursor, Grok, or any coding agent to continue this work without chat history.

````
You are continuing work on Endgame-AI — a local Windows desktop ROD (Reason–Observe–Decide) graph operator.

## What Endgame-AI is

- Python stdlib HTTP server (`server.py`) that runs a fixed wiring graph per goal.
- Loop: goal_inbox → moe_route → planner → scheduler ↔ (bus_check → observe → act → verify | reflect | self_modify) → bus_post → satisfied
- Slot 1 (`prompts/wiring.json`): primary desktop operator (Notepad, Chrome, YouTube, chat).
- Slot 2 (`prompts/wiring_relay.json`): browser-chat relay worker.
- Mechanical layer: `desktop.py` (UIA observe, window tokens, focus) + `actions.py` (verb dispatch).
- Cognition is pluggable: `file_proxy` (agent writes JSON to comms/) or OpenAI-compatible LM Studio.
- Shell/file-proxy is for server control and cognition only — NOT valid proof of desktop control. Proofs require Endgame-AI action history + final GET /state.

Branch: codex/self-referential-relay
Workspace: C:\Users\ewojgab\Downloads\endgame-ai
Slot 1 port: 9078 (instance.slot=1, http_port_base=9077 + offset)

Authoritative counts (inspect wiring.json — do not trust stale docs):
- Slot 1 rules: 32 | topology: 12 nodes, 22 edges | verb_normalize: 5 | SELF_MODIFY_OPS: 15
- limits: max_attempts 7, max_replans 3, max_self_modify 3
- Slot 2 relay: 13 rules (confirm_relay_wait removed)

## Primary goal

Make Endgame-AI complete real multi-step desktop goals autonomously via its own observe/act — not merely plan them or pass unit tests while file-proxy masks runtime failures.

### P0 benchmarks (must pass with action history + /state evidence)

| Goal | Proves |
|------|--------|
| open notepad and type hello | Run dialog, write, confirm_launch_chain |
| navigate to google.com in chrome | open_url or nav, confirm_browser_navigation / domain needle |
| play Shakira Waka Waka on YouTube | Browser stack, video page, confirm_youtube_playback |

### P1 benchmark

| Goal | Proves |
|------|--------|
| have a conversation with an AI chatbot | Chat submit rules, wait deny, memory.llm_response capture |

## Already implemented (commits 9715fe9, 51322b0, 61280bc)

Mechanical + wiring:
- Focus contract: [W#] tokens in SCREEN, shared resolve_window_target(), HWND-first focus_window()
- open_url verb: start chrome <url> without prior focus
- Wait semantics: deny_response_no_evidence broadened, deny_wait_only_content_receipt, confirm_llm_response_received requires memory; relay confirm_relay_wait removed
- max_self_modify: 3 with give_up edge
- observe.desktop_tree_enabled aligned (false for Slot 1; configure_observation() is source of truth)
- node_reflect fallbacks match wiring 7/3

Tests + harness (partial):
- test_mechanical_fixes.py — 10 tests (focus resolver, live foreground focus, wait-deny rules) — PASSING
- harness_common.py — shared kill_port, clear_comms, server lifecycle (started, not fully wired)
- p0_file_proxy_runner.py — scripted P0 driver (needs fixes below)
- run_verification.py — scratch captures (needs README-only doc-drift check; SETUP_AND_LAUNCH.md deleted)

## Remaining work (priority order)

1. Fix file-proxy two-pass LLM in p0_file_proxy_runner.py (and any proxy responder):
   - call_node (server.py ~1160) does TWO llm() calls per circuit: first pass = reasoning; second pass user contains "DECIDE NOW" = role JSON only.
   - Proxy must answer pass 1 with prose/reasoning (not JSON); pass 2 with exact circuit JSON.
   - Detect circuit via ROLE: headers in system message (Planner, Act, Verifier, Reflector).

2. Fix act script indexing on retries:
   - Do NOT increment act_i on every act request — use SUBTASK:/step text to pick acts[step].
   - Bug seen: step 0 retried with acts[1] (write hello) while planner still on step 0 → verify deny loop + repeated hover scans.

3. Fix harness cleanup:
   - kill_port(9078) before server start; clear comms via POST /llm-proxy/clear + unlink stale request.json.
   - Do not delete state mid-run on live server.
   - Poll until run.running == false or terminal satisfied/plan_failed.

4. Re-run P0 benchmarks; capture to scratch:
   C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer
   - p0-*-run*.json, p0-summary.json, server-health.json with started:true and non-empty history

5. Fix run_verification.py: use harness_common, real focus capture (no mock), doc-drift check README-only.

6. Optional P1/P2: chatbot benchmark, self_modify recovery proof, MoE delegation doc, plan_failed recovery.

## Definition of done

- [ ] focus succeeds for every window title listed in SCREEN WINDOWS
- [ ] Google.com navigation completes with confirm_browser_navigation or domain needle evidence
- [ ] YouTube Shakira benchmark reaches video page with playback evidence (or honest structured failure)
- [ ] Wait-only steps never step_confirmed without response/memory evidence
- [ ] max_self_modify enforced; desktop_tree_enabled consistent
- [ ] Regression tests pass; P0 scratch captures show real history (not planner: file proxy pending)
- [ ] No new doc/code drift (use /system /health /state — no /slots/status)

## Key files

| File | Role |
|------|------|
| server.py | call_node two-pass LLM, RULE_CHECKERS, node_reflect, node_self_modify |
| desktop.py | resolve_window_target, focus_window, open_url, observe |
| actions.py | execute_verb focus/open_url dispatch |
| prompts/wiring.json | Slot 1 brain (32 rules, 22 edges) |
| prompts/wiring_relay.json | Slot 2 relay (13 rules) |
| test_mechanical_fixes.py | Unit + live focus tests |
| p0_file_proxy_runner.py | P0 benchmark driver — FIX FIRST |
| harness_common.py | Shared harness — finish wiring into runners |

## Commands

cd C:\Users\ewojgab\Downloads\endgame-ai
$env:PYTHONIOENCODING = 'utf-8'
python test_mechanical_fixes.py
python server.py   # Slot 1 on 9078 when ENDGAME_SLOT=1
python p0_file_proxy_runner.py   # after proxy fixes

Invoke-RestMethod http://127.0.0.1:9078/state
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/llm-proxy/clear -ContentType 'application/json' -Body '{"confirm":true}'

## Constraints

- Minimal diff; prefer wiring.json rules over Python policy.
- Do not manually drive Chrome/Notepad outside runtime for proofs.
- New rule match keys need RULE_CONDITIONS + RULE_CHECKERS in server.py.
- Preserve working paths: confirm_launch_chain, navigation rejects, chat write denies.
````

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

**Goal paused** — mechanical layer fixes are in; P0 E2E proofs are not yet captured. Use the copy-paste handover prompt above to resume.

| Benchmark | Status |
|-----------|--------|
| `open notepad and type hello` | Partial — hello typed in live runs; graph stuck on step 0 retries (file-proxy act indexing bug) |
| `navigate to google.com in chrome` | Not proven in scratch captures |
| `play Shakira Waka Waka on YouTube` | Not proven in scratch captures |
| `have a conversation with an AI chatbot` | Not run |

- **MoE delegation** on Slot 1 is inert when `desktop_exec` permission is present (browser goals stay on Slot 1).
- **`plan_failed`** exits to `bus_post` without reflect/replan recovery.
- **YouTube playback** has structural verify rules but no audio/OCR proof; ads/login/cookie paths are partial.
- **File-proxy benchmarks** fail if a stale `request.json` is left pending or two-pass DECIDE NOW is not honored — always clear before a new run.
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