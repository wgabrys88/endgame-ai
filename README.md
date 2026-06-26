# Endgame-AI

Local Windows desktop **Reason–Observe–Decide (ROD)** operator. Python stdlib only (no pip). `server.py` runs a fixed graph; `prompts/wiring.json` is the brain.

| | |
|---|---|
| **Branch** | `codex/self-referential-relay` |
| **Workspace** | `C:\Users\ewojgab\Downloads\endgame-ai` |
| **Platform** | Windows 10/11 |
| **Entry** | `server.py` (stdlib `http.server`, not FastAPI) |
| **Goal status** | **Paused** — mechanical fixes landed; live foreground + strict rule-evidence gaps remain |

> **Truth order:** `prompts/wiring.json` + `server.py` + `desktop.py` + `actions.py` beat this README. Re-count rules/edges after every wiring edit.

This file is the **only** handoff and documentation for humans and AI agents. There is no `SETUP_AND_LAUNCH.md`, `HANDOVER_FAULTS.md`, or other doc set.

---

## What it does

Endgame-AI pursues user goals through a declarative graph:

```
goal_inbox → moe_route → planner → scheduler ↔ (bus_check → observe → act → verify | reflect | self_modify) → bus_post → satisfied
```

| Slot | Wiring | Role |
|------|--------|------|
| **1** | `prompts/wiring.json` | Primary desktop operator (Notepad, Chrome, YouTube, chat) |
| **2** | `prompts/wiring_relay.json` | Browser-chat relay; captures answers into `MEMORY.llm_response` |

**Cognition** is pluggable: OpenAI-compatible (LM Studio) or **file_proxy** (any coding agent writes JSON to `comms/`). The runtime always owns observe, act, verify, and reflect — cognition only supplies planner/act/verifier/reflector JSON.

**Proof rule:** A benchmark passes only when Endgame-AI **action history** and final **`GET /state`** show it. Shell shortcuts and manual Chrome/Notepad control outside the runtime are not valid proof.

---

## Authoritative wiring counts (Slot 1)

Inspect `prompts/wiring.json` directly.

| Item | Value |
|------|-------|
| Rules | **32** |
| Topology | **12 nodes**, **22 edges** |
| `verb_normalize` | **5** |
| `SELF_MODIFY_OPS` | **15** (`server.py`) |
| `limits` | `max_attempts` **7**, `max_replans` **3**, `max_self_modify` **3** |
| `observe.desktop_tree_enabled` | **false** (Slot 1) |

Slot 2 relay: **13 rules** (`confirm_relay_wait` removed).

---

## Repository layout

| Path | Role |
|------|------|
| `server.py` | HTTP API, ROD loop, rule engine, two-pass LLM, self-modify |
| `desktop.py` | UIA observation, `[W#]` window tokens, `resolve_window_target`, `focus_window`, `open_url` |
| `actions.py` | Verb dispatch (`execute_verb`) |
| `colony.py` | Multi-slot wrapper |
| `prompts/wiring.json` | Slot 1 brain |
| `prompts/wiring_relay.json` | Slot 2 relay brain |
| `prompts/wiring-schema.json` | Wiring validation |
| `prompts/model.json` | Slot 1 cognition config |
| `prompts/model_relay.json` | Slot 2 cognition config |
| `wiring-editor.html` | Operator panel |
| `test_mechanical_fixes.py` | Focus resolver + wait-deny regression tests |
| `run_verification.py` | Writes verification artifacts to scratch dir |
| `harness_common.py` | Shared server/proxy helpers (gitignored) |
| `p0_file_proxy_runner.py` | Optional canned proxy driver — **not** valid proof |

Runtime artifacts (not source): `state.json`, `state.slot*.json`, `bus.json`, `comms/**`.

---

## Quick start (humans)

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
$env:PYTHONIOENCODING = 'utf-8'
$env:ENDGAME_SLOT = '1'
$env:ENDGAME_STATE = "$PWD\state.slot1.json"
$env:ENDGAME_WIRING = "$PWD\prompts\wiring.json"
python server.py
```

Panel: `http://127.0.0.1:9078/` (Slot 1).

Post a goal:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/run `
  -ContentType 'application/json' -Body '{"goal":"open notepad and type hello"}'
```

Poll:

```powershell
Invoke-RestMethod http://127.0.0.1:9078/state
Invoke-RestMethod http://127.0.0.1:9078/health
```

Clear stale cognition queues before a new run:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/llm-proxy/clear `
  -ContentType 'application/json' -Body '{"confirm":true}'
```

---

## Ports

`http_port = http_port_base + slot` when `http_port_slot_offset` is true (default).

| Instance | Port | Config |
|----------|------|--------|
| Root / slot 0 | 9077 | `runtime.http_port_base` |
| Slot 1 | **9078** | `instance.slot: 1` in `wiring.json` |
| Slot 2 | 9079 | `instance.slot: 2` in `wiring_relay.json` |

**There is no `/slots/status`.** Use `GET /system`, `GET /health`, `GET /state` per instance; `POST /slots/start|stop|run` on root.

---

## HTTP API (per instance)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Nodes, port, model transport, run status |
| GET | `/system` | Root system snapshot |
| GET | `/state` | Full run state (goal, step, history, screen, memory) |
| POST | `/run` | Enqueue goal |
| POST | `/resume` | Resume saved state |
| POST | `/pause` | Pause loop |
| POST | `/llm-proxy/clear` | Clear cognition file-proxy (`confirm: true`) |
| POST | `/relay/clear` | Clear browser relay handoff |
| POST | `/slots/start` / `/slots/stop` | Root slot manager |
| GET | `/wiring/audit` | Wiring validation report |
| POST | `/wiring` | Hot-reload wiring |

---

## Cognition backends

### File-proxy (default)

`prompts/model.json` → `transport: file_proxy`

| Queue | Request | Response |
|-------|---------|----------|
| Slot 1 | `comms/slot1_cognition/request.json` | `comms/slot1_cognition/response.json` |
| Slot 2 | `comms/relay_cognition/request.json` | `comms/relay_cognition/response.json` |
| Browser relay | `comms/llm_proxy/request.json` | `comms/llm_proxy/response.json` |

### OpenAI-compatible

Set `transport: openai` in the slot's `model.json`; point `host` at `/v1/chat/completions`.

---

## AI agent handoff: you are the file-proxy LLM

When `file_proxy` is active, **you** (Codex, Claude Code, Cursor, Grok, etc.) are the cognition backend. Endgame-AI runs the state machine and desktop layer.

### How to operate

1. Start Slot 1 server (port **9078**).
2. `POST /run` with a goal (or read existing `/state`).
3. Poll `comms/slot1_cognition/request.json`.
4. Write `comms/slot1_cognition/response.json` with the **same `id`** as the request.
5. Repeat until `/state` shows terminal (`satisfied`, `plan_failed`, or idle at `satisfied` node).
6. Capture `/state` + `history` as proof.

**Do not use canned scripts** (`p0_file_proxy_runner.py`) for proofs. Read each request's actual `SUBTASK`, `SCREEN`, `STEP`, `LAST_OUTCOME` and decide from observed state.

### Two-pass LLM (`server.py` ~1160)

Each circuit call does **two** file-proxy round-trips:

| Pass | User message contains | Your `content` |
|------|----------------------|----------------|
| 1 | No `DECIDE NOW` | Prose/reasoning only (not role JSON) |
| 2 | `DECIDE NOW` | Exactly **one** role JSON object |

Detect circuit from system `ROLE:` header:

| Circuit | Header | `record_type` |
|---------|--------|---------------|
| planner | `ROLE: Planner` | `task` |
| act | `ROLE: Act` | `action` |
| verifier | `ROLE: Verifier` | `verdict` |
| reflector | `ROLE: Reflector` | `diagnosis` |
| self_modify | `ROLE: Self_modify` | `wiring_patch` |

### Response shape

```json
{
  "id": "<same as request>",
  "choices": [{
    "message": {
      "content": "<reasoning text OR JSON string on DECIDE NOW pass>",
      "reasoning_content": "<optional>"
    }
  }]
}
```

### Act verbs

`click`, `write`, `press`, `hotkey`, `focus`, `open_url`, `scroll`, `wait`, `remember`, `llm_request`, `llm_wait_response`

### Focus contract

- SCREEN `WINDOWS` lines include stable tokens: `- [W3] YouTube - Google Chrome`
- **focus** target: `[W3]`, `W3`, full title, or `hwnd:<id>`
- `resolve_window_target()` in `desktop.py` is shared by SCREEN render and `actions.execute_verb("focus", ...)`
- Observed HWND is preferred over fuzzy title scan
- `execute_verb` may short-circuit with `(already focused)` before calling `focus_window` when the observation snapshot marks the target focused

### Navigation

- **`open_url`**: `target=chrome|edge`, `value=<url>` — launches via `start chrome <url>` without prior focus
- Chat/prompt text must **not** go to address bars; URL navigation may use address bar or `open_url`
- Prefer `open_url` when browser is absent or unfocused

### Wait / response semantics

- Wait-only steps must **not** confirm response receipt without `MEMORY.llm_response` or equivalent evidence
- Relay: `confirm_relay_wait` **removed** — wait is recovery pause only

### Stale request blocker

If `request.json` already exists, planner fails with `LLM file proxy request already pending`. Clear via `/llm-proxy/clear` before a new goal.

---

## Copy-paste prompt (next AI agent)

```
You are continuing Endgame-AI on branch codex/self-referential-relay.

Workspace: C:\Users\ewojgab\Downloads\endgame-ai
Slot 1 port: 9078
Cognition: file_proxy (you read comms/slot1_cognition/request.json, write response.json)

WHAT IT IS: Windows ROD graph operator. Loop: goal_inbox → moe_route → planner → scheduler ↔ (observe → act → verify | reflect | self_modify) → satisfied. Mechanical layer: desktop.py + actions.py. Wiring: prompts/wiring.json (32 rules, 12 nodes, 22 edges).

GOAL (paused): Complete real multi-step desktop goals autonomously via observe/act — not scripted proxy proofs.

DONE mechanically:
- [W#] focus tokens + resolve_window_target + HWND-first focus
- open_url verb (start chrome <url>)
- Wait-deny rules broadened; confirm_relay_wait removed; max_self_modify=3
- desktop_tree_enabled aligned via configure_observation()

REMAINING (priority):
1. focus_window robustness — Windows foreground lock causes real observed focus to fail; consider AttachThreadInput/retry in desktop.py:_set_foreground_verified
2. Prove confirm_browser_open_url / confirm_youtube_playback fire in history (not just satisfied via proxy verdict)
3. P1 chatbot benchmark — wait deny + memory.llm_response capture
4. P2 self_modify recovery proof
5. MoE delegation inert on Slot 1 (document or fix)
6. plan_failed has no reflect recovery

VERIFY BY: python test_mechanical_fixes.py; live file-proxy on real goals; scratch captures under C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer

CONSTRAINTS: Minimal diff; wiring.json for policy; no manual desktop control for proofs; two-pass DECIDE NOW honored.
```

---

## Mechanical layer (shipped)

| Fix | Location | Behavior |
|-----|----------|----------|
| Focus contract | `desktop.py`, `actions.py` | `[W#]` tokens, shared resolver, HWND-first `focus_window` |
| Browser navigate | `desktop.open_url`, `actions.py` | `start chrome <url>` without prior focus |
| Wait semantics | `wiring.json`, `wiring_relay.json` | `deny_wait_only_content_receipt`, strengthened `confirm_llm_response_received` |
| Self-modify cap | `wiring.json`, `server.py` | `max_self_modify: 3`, `give_up` edge |
| Observe alignment | `desktop.py`, wiring | `configure_observation()` is source of truth after load |
| Reflect limits | `server.py` | Fallbacks defer to `wiring_limit()` (7/3) |

Key code:

| Concern | Location |
|---------|----------|
| Two-pass LLM | `server.py:1160-1181` |
| Rule evaluation | `server.py` `evaluate_rules`, `RULE_CHECKERS` |
| Reflect / escalate | `server.py` `node_reflect` |
| Self-modify | `server.py` `node_self_modify`, ops `343-359` |
| Focus | `desktop.py` `focus_window`, `resolve_window_target` |
| Verbs | `actions.py` `execute_verb` |

---

## Observation: why the mouse sweeps

Each **observe** node runs a full-screen hover scan when `hover_scan_enabled` is true (~400+ probe points; visible cursor movement). That is expected **once per step**.

Multiple sweeps back-to-back mean **retries**:

```
scheduler → bus_check → observe → act → verify → reflect → retry → observe …
```

Up to `observe.wait_retries` (default **6**) extra observe passes run inside one observe node if fewer than `min_elements` actionable `[ID]` targets are found.

If verify keeps denying, retries stack even when act partially succeeded. Check `history`, `step`, `retries`, `last_error` in `/state`.

---

## Benchmarks (honest status)

Cognition for live runs: **file_proxy** with coding agent reading/writing `comms/slot1_cognition/`.

| Priority | Goal | Status | Notes |
|----------|------|--------|-------|
| P0 | `open notepad and type hello` | Partial pass | `satisfied=true`; focus W3 reported `(already focused)` — no proof of `_set_foreground_verified` on unfocused token |
| P0 | `navigate to google.com in chrome` | Partial pass | `open_url` OK, `satisfied=true`; confirm rule IDs not always in history |
| P0 | `play Shakira Waka Waka on YouTube` | Partial pass | Reached watch URL via `open_url`, not click-play; playback rule evidence thin |
| P1 | `have a conversation with an AI chatbot` | Not run | |
| P2 | Self-modify after focus failures | Not run | |

Scratch captures (when present): `C:\Users\ewojgab\AppData\Local\Temp\grok-goal-6eaf4693378c\implementer\`

```powershell
python test_mechanical_fixes.py
python run_verification.py
```

Unit tests: **9 pass, 1 skip** — live foreground test skips when Windows blocks `SetForegroundWindow` in automated sessions.

---

## Known gaps

- **`focus_window`** can return false under Windows foreground restrictions; no `AttachThreadInput` / robust retry yet (`desktop.py:_set_foreground_verified`).
- **Structural confirm rules** (`confirm_browser_open_url`, `confirm_youtube_playback`) may not appear in `history` even when `satisfied=true` (verifier LLM or preflight path).
- **MoE delegation** on Slot 1 is inert when `desktop_exec` is present.
- **`plan_failed`** exits to `bus_post` without reflect/replan.
- **YouTube playback** has structural rules but no player-state/audio proof; ads/login/cookie paths partial.
- **Stale `request.json`** blocks planner until `/llm-proxy/clear`.

---

## Development

```powershell
python test_mechanical_fixes.py
```

Wiring changes: update `RULE_CONDITIONS` / `RULE_CHECKERS` in `server.py` when adding rule `match` keys. Prefer declarative rules in `wiring.json` over Python policy.

Self-modify creates backups: `prompts/wiring.backup.<stamp>.json`.

---

## License / status

Research/operator tooling. Not production-hardened. Update this README when wiring counts, ports, or handoff contracts change.