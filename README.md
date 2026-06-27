# Endgame-AI — Modular Browser-Brain Desktop Operator

A local, closed-loop desktop automation agent powered by interchangeable AI brains. Endgame-AI observes the Windows desktop, asks an LLM for a strict JSON decision, executes only contracted desktop verbs, verifies evidence, reflects on failure, and can patch its own wiring.

This package is the modular exec-node release with a graphical wiring workbench, strong role prompts, explicit verb contracts, and a hardened Grok/browser-AI handoff path.

## Endgame vision

```text
Traditional agents: Human → configures agent → agent calls APIs → limited to API surface
Endgame-AI:         Human → posts goal → system operates the desktop → any app, any AI
```

The local model, such as LM Studio, can be the normal control brain. It can also act as the desktop operator and fallback while a browser-hosted AI such as Grok becomes the larger planning/decision brain. That means the system can:

- open or recover the browser AI chat window,
- paste the exact role/runtime contract into the chat,
- wait for the response,
- extract the JSON decision from the observed screen,
- execute the resulting desktop actions locally,
- recover by reopening the browser AI if the tab/window is closed or UI state changes.

No Grok API key is required for the `browser_ai` path; it uses the same desktop verbs as any other task.

## What changed in this package

- Specialized prompts for planner, actor, verifier, reflector, and self-modifier.
- Explicit actor verb list and argument contracts.
- Runtime validation that rejects invented actor verbs before execution.
- Real `browser_ai` transport instead of a file-proxy alias.
- New `browser_ai_handoff` actor verb for explicit Grok handover goals.
- OpenAI-compatible `file_proxy` request/response JSON for outside agents that watch files on disk.
- Graphical wiring editor with draggable nodes and mouse-created edges.
- Deterministic simulation tests for Grok/browser handoff, file-proxy handoff, and act-node memory storage.

## Quick start

```bash
python engine.py
```

Open the workbench:

```text
http://127.0.0.1:9077/
```

Post a goal:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/run `
  -ContentType 'application/json' `
  -Body '{"goal":"open notepad and type hello world"}'
```

The workbench and API are served by the same engine. Slot 1 defaults to port `9077`; additional slots use the configured port offset.

## Brain transports

Edit `prompts/model.json`.

### 1. LM Studio / OpenAI-compatible local model

```json
{
  "transport": "openai",
  "host": "http://localhost:1234",
  "model": "nvidia-nemotron-3-nano-4b",
  "temperature": 0.3
}
```

This sends `/v1/chat/completions` requests to LM Studio or any compatible local endpoint.

### 2. Grok or another browser AI as the brain

```json
{
  "transport": "browser_ai",
  "browser_ai": {
    "browser": "opera",
    "url": "https://grok.com",
    "domain": "grok.com",
    "open_wait_ms": 5000,
    "response_wait_ms": 15000,
    "response_min_chars": 20,
    "retries": 2,
    "submit_key": "enter"
  }
}
```

On each LLM call, Endgame-AI:

1. observes the desktop,
2. opens/focuses `https://grok.com` when Grok is not visible,
3. finds the likely chat input from UIA screen text,
4. pastes the role contract plus runtime input,
5. submits with Enter,
6. waits,
7. observes the response,
8. extracts the JSON object for the current role.

This is the handover mode: Grok supplies decisions; Endgame-AI remains the hands, verifier, recovery loop, and local fallback.

### 3. File-proxy external agent

```json
{
  "transport": "file_proxy",
  "file_proxy": {
    "request_path": "comms/slot1_cognition/request.json",
    "response_path": "comms/slot1_cognition/response.json",
    "archive_dir": "comms/slot1_cognition/archive",
    "poll_interval_ms": 1000
  }
}
```

Request written by the engine:

```json
{
  "id": "llm-...",
  "status": "pending",
  "messages": [
    {"role": "system", "content": "ROLE: Planner/Act/Verifier/Reflector..."},
    {"role": "user", "content": "Runtime state and task..."}
  ]
}
```

Expected response from the outside agent:

```json
{
  "id": "same id as request",
  "status": "complete",
  "choices": [
    {"message": {"content": "{JSON record required by the role}"}}
  ]
}
```

A minimal watcher is included at `tools/file_proxy_agent_stub.py`.

## Graph architecture

```text
Goal Inbox → MoE Route → Planner → Scheduler → Bus Check → Observe → Act → Verify
                                                                  ↘ failure → Reflect
Reflect → retry Scheduler | replan Planner | escalate Self-Modify | give_up Bus Post
Self-Modify → Planner
Scheduler plan_complete → Bus Post → Satisfied
```

The engine reloads wiring and node scripts live. You can edit `prompts/wiring.json`, edit `nodes/*.py`, or use the graphical workbench while the engine is running.

## Graphical wiring editor

`wiring-editor.html` is served by `engine.py`.

Features:

- SVG node graph with typed node coloring.
- Drag nodes to rearrange topology.
- Drag from an amber output handle to a blue input handle to create an edge.
- Select edge labels to inspect or edit `from`, `on`, and `to`.
- Select nodes to edit id, type, label, and circuit.
- Save with **Save Wiring** or `Ctrl+S`.
- Edit raw wiring JSON in the JSON tab.
- Edit `nodes/<type>.py` in the Node Code tab.
- Double-click a node to step it.
- Copy the full codebase snapshot from the toolbar.

Graph positions are stored under `topology.layout.positions`; the runtime ignores layout metadata.

## LLM role contracts

Every model call uses the same global output rule: exactly one JSON object, no markdown, no invented verbs, no invented fields.

### Planner

```json
{"record_type":"task","data":{"steps":[{"description":"...","done_when":"..."}]}}
```

The planner decomposes the human goal into observable desktop steps. It cannot execute actions or verify completion.

### Actor

```json
{"record_type":"action","data":{"conclusion":"EXECUTE","actions":[{"verb":"click","target":"[12]","value":""}]}}
```

or:

```json
{"record_type":"action","data":{"conclusion":"CANNOT","actions":[]}}
```

Allowed verbs:

| Verb | Target | Value | Meaning |
|---|---|---|---|
| `click` | visible element id/token/name | empty | Click a resolved UI element. |
| `write` | writable element id/name, or empty for focus | text | Type exact text after selecting existing text. |
| `press` | empty | key name | Press `enter`, `tab`, `esc`, etc. |
| `hotkey` | empty | chord | Press `ctrl+l`, `ctrl+s`, `win+r`, etc. |
| `focus` | window token/title | empty | Bring a window forward. |
| `open_url` | optional browser/app | URL/domain | Open a web location. |
| `scroll` | scrollable element | signed integer | Scroll the element. |
| `wait` | empty | milliseconds | Wait from 100 to 30000 ms. |
| `launch` | app name or command | optional app name | Launch an app. |
| `remember` | memory key | value | Store data for later steps. |
| `llm_request` | request label | prompt text | Write an external AI handoff request file. |
| `llm_wait_response` | empty | empty | Wait for relay response and store it in memory. |
| `browser_ai_handoff` | optional label | request text | Open/focus Grok or configured browser AI, submit request, wait, and store response. |
| `copy_codebase` | empty | empty | Write and copy a full repository snapshot. |

The actor must never output `DONE`; verification owns completion.

### Verifier

```json
{"record_type":"verdict","data":{"confirmed":true,"evidence":"...","reason":"..."}}
```

The verifier judges `done_when` against fresh screen state, outcome text, history, and memory.

### Reflector

```json
{"record_type":"diagnosis","data":{"diagnosis":"...","suggestion":"...","should_replan":false}}
```

The reflector diagnoses a failed action/verification and decides retry vs. replan.

### Self-modifier

```json
{"record_type":"wiring_patch","data":{"op":"add_edge","payload":{"from":"node_id","to":"node_id","on":"signal"}}}
```

Supported patch ops include `add_node`, `create_node_file`, `update_node`, `remove_node`, `add_edge`, `remove_edge`, `add_rule`, `update_rule`, `remove_rule`, `set_limit`, `set_guard`, `set_observe`, `set_prompt_base`, `set_role`, and `append_role_rule`.

## Handover scenarios

Scenario files live in `scenarios/`:

- `scenarios/grok_browser_handoff.json` — configure Grok/browser AI as the cognition source.
- `scenarios/file_proxy_agent_handoff.json` — configure a disk-based external agent protocol.

For an explicit one-off handover while LM Studio remains the active brain, the actor can use:

```json
{
  "record_type": "action",
  "data": {
    "conclusion": "EXECUTE",
    "actions": [
      {"verb": "browser_ai_handoff", "target": "grok", "value": "Take over planning for this goal and return the next concrete instruction."}
    ]
  }
}
```

The response is stored in `MEMORY.grok_response` and `MEMORY.llm_response`.

## Validation and simulation

Run deterministic simulations without Windows desktop access or LM Studio:

```bash
python tests/simulate_handoff.py
```

The simulation proves:

- `browser_ai` opens Grok when absent, writes the role/runtime prompt, submits it, and extracts JSON from the observed response.
- browser recovery/multiturn behavior reopens Grok if the chat window disappears before the next cognition call.
- `file_proxy` writes OpenAI-like `request.json`, preserves request id, reads `choices[0].message.content`, and archives responses.
- the act node accepts `browser_ai_handoff`, executes it, and stores Grok output in memory.

Compile and wiring checks:

```bash
python -m py_compile runtime.py engine.py actions.py nodes/*.py
python - <<'PY'
import json, runtime
from pathlib import Path
for f in ['prompts/wiring.json', 'prompts/wiring_relay.json']:
    print(f, runtime.validate_wiring(json.loads(Path(f).read_text())))
PY
```

## Project structure

```text
endgame-ai/
├── engine.py                    HTTP server, graph walker, SSE stream
├── runtime.py                   LLM transports, prompts, wiring helpers, browser/file handoff
├── actions.py                   Data-driven verb dispatch into desktop automation
├── desktop.py                   Windows UI Automation and observation plumbing
├── colony.py                    Multi-slot support helpers
├── nodes/                       Exec-node scripts loaded fresh on every execution
├── prompts/                     Model config, wiring, schema
├── scenarios/                   Ready handover scenarios
├── tests/simulate_handoff.py    Local deterministic handoff tests
├── tools/file_proxy_agent_stub.py
└── wiring-editor.html           Graphical workbench
```

## Exec-node contract

Every node is a plain Python script. No class or function wrapper is required.

Injected names include:

```python
state, config, wiring, llm(), observe_screen(), execute_verb(), evaluate_rules(),
load_system_prompt(), build_user_message(), call_node(), save_state(), load_state(),
load_wiring(), save_wiring(), wiring_limit(), wiring_error(), fresh_state(),
normalize_actions_from_wiring(), apply_memory_action(), write_llm_request(),
wait_llm_response(), bus_read(), bus_write(), append_trace(), recent_traces(),
apply_wiring_patch(), validate_wiring(), atomic_write_json(), atomic_write_text(),
copy_codebase_to_clipboard(), collect_codebase_text(), scaffold_node_file(), runtime
```

A node returns by assigning:

```python
patch = {"some_key": "some_value"}
signals = ["done"]
```

`engine.py` applies `patch` to state, then routes by the first edge whose `on` signal matches.

## HTTP API

| Endpoint | Method | Purpose |
|---|---:|---|
| `/` | GET | Workbench UI |
| `/health` | GET | Runtime status and wiring summary |
| `/wiring` | GET/POST | Load or replace wiring JSON |
| `/state` | GET/POST | Load or replace runtime state |
| `/inspect` | GET | Debug prompt/node context |
| `/events` | GET | Server-sent events |
| `/node/types` | GET | Available node script types |
| `/node/<type>` | GET/POST | Read or overwrite `nodes/<type>.py` |
| `/node/create` | POST | Scaffold node file and add topology node |
| `/run` | POST | Start loop |
| `/step` | POST | Execute one node/cycle |
| `/pause`, `/resume`, `/stop` | POST | Control active run |
| `/clipboard/codebase` | POST | Write/copy full codebase snapshot |
| `/codebase?format=text` | GET | Read snapshot text on demand |
| `/bus` | GET/POST | Read/write lightweight bus messages |
| `/slots` | GET | Show slot port mapping |

## Safety and correctness notes

- The actor only gets a finite verb contract; invented verbs are rejected before execution.
- `actions.py` uses default field names even if a verb config is partially missing.
- The verifier owns completion, preventing the actor from short-circuiting success.
- Browser-AI handoff always uses desktop verbs; if Grok is not visible, the next call opens it again.
- File-proxy requests preserve role contracts and request ids for outside agents.
- Wiring is validated before save.
- Node scripts and wiring are hot-loaded, so bad experiments can be fixed without restarting the engine.

## License

MIT. See `LICENSE`.
