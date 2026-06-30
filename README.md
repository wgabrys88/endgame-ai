# endgame-ai

A living Windows-desktop organism: observe → act → verify → reflect → self-modify. Python is the mechanical body, `wiring.json` is the mutable cognitive map, and all executable cognition paths are hot-swappable node files.

This package is a rewired replacement repository. It keeps the ROD architecture and fail-hard behavior, but removes the largest boundary leak in the previous branch: brain transports are now brain nodes.

## What changed in this package

### 1. Brain transports became nodes

Concrete brains now live in:

```text
seed_brains/      immutable templates committed with the repo
live_brains/      mutable runtime copies created on first run
```

`brain.py` still owns the ROD loop, typed-record parsing, raw logging, call budgets, and helper functions. It no longer contains a long transport dispatch chain. Instead, `model.transport` selects one brain node:

| Transport | Brain node | Purpose |
|---|---|---|
| `openai` | `openai.py` | LM Studio or any OpenAI-compatible `/v1/chat/completions` endpoint |
| `xai_responses` | `xai_responses.py` | xAI `/v1/responses` for general Grok models |
| `grok_build_api` | `grok_build_api.py` | Grok Build 0.1 through xAI Responses API with `XAI_API_KEY` |
| `opencode` | `opencode.py` | OpenCode `opencode run` stateless CLI mode |
| `grok_build` | `grok_build.py` | Grok Build CLI headless `grok -p ... --output-format ...` |
| `file_proxy` | `file_proxy.py` | File/human/other-agent handoff through `comms/request.json` and `comms/response.json` |
| `browser_ai` | `browser_ai.py` | Intentional fail-hard stub until a real browser handoff exists |

Alias examples are in `model.brain_nodes.aliases`: `lm_studio → openai`, `file_brain → file_proxy`, `grok_build_cli → grok_build`.

### 2. Seed nodes are restored as first-class source

Runtime topology nodes now live where `nodes.py` already expected them:

```text
seed_nodes/       planner, scheduler, observe, act, verify, reflect, self_modify, satisfied
live_nodes/       mutable runtime copies created on first run
```

The old root-level node files were a packaging leak. The source of truth is now `seed_nodes/`.

### 3. xAI non-blocking socket crash fixed

The previous `wiring.json` had:

```json
"xai_responses": { "timeout": 0 }
```

On Windows, `urllib` treats timeout `0` as a non-blocking socket. That matches the observed crash:

```text
WinError 10035: A non-blocking socket operation could not be completed immediately
```

This package sets xAI/Grok API brain timeouts to `900` seconds and clamps any non-positive timeout inside `Brain._timeout()`. This is not a fallback. It is rejecting an invalid I/O parameter.

### 4. xAI Responses payload corrected

`xai_responses.py` and `grok_build_api.py` now send:

```json
"input": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."}
]
```

This preserves statelessness while matching the Responses API message-array form.

### 5. OpenCode and Grok Build CLI are narrower and documented in wiring

`opencode.py` uses `opencode run` with `--model`, `--agent`, `--file`, `--format`, `--attach`, and `--dir`. The default `prompt_mode` remains `file` to avoid Windows command-length failures.

`grok_build.py` uses `grok -p <prompt> --output-format streaming-json` by default. Optional switches such as `--always-approve`, `--no-auto-update`, and `--no-alt-screen` are wiring-controlled and off by default.

### 6. Workbench reflects brain nodes

`workbench.py` now lists `grok_build_api` separately, labels the panel as “Brain node + parameters,” and probes the selected provider without silently substituting another one.

### 7. Self-modification can retry its own patch

`self_modify.py` now records `self_modify_failures`. Invalid patch output can route through `modify_retry` back to `self_modify` until `limits.max_self_modify` is reached. After exhaustion, it emits `modify_failed` and rests through the explicit topology edge.

### 8. Terminal state is no longer overwritten

`organism.py` no longer overwrites `rest`, `max_ticks`, or `interrupted` with a final `stopped` phase. The terminal phase remains visible in `state.json`.

### 9. Structural validation added

Run this before real desktop/brain tests:

```powershell
python validate_repo.py
```

It checks Python syntax, required seed nodes, required seed brain nodes, topology duplicate edges, topology reachability, and selected-brain presence. It does not call providers or touch desktop I/O.

## Architecture

```text
organism.py      topology loop, state snapshots, wiring reloads
nodes.py         hot-swappable topology-node loader + ROD prompt assembly
brain.py         ROD two-call loop, typed JSON extraction, logging, brain-node loader
actions.py       wiring-driven desktop verb executor
desktop.py       Windows UIA observation and keyboard/mouse body
workbench.py     local HTML control/debug panel
wiring.json      topology, prompts, verbs, brain node configs, limits
seed_nodes/      default topology node source
seed_brains/     default brain node source
```

The core still uses only the Python standard library.

## ROD contract

Every LLM-backed circuit uses exactly one ROD decision:

1. Call 1: gather reasoning.
2. Call 2: resend the same context plus `ROD_REASONING_CONTENT` and commit a typed JSON record.

Expected record types are declared in `wiring.reasoning.expected_record_type`:

| Circuit | Record type |
|---|---|
| `planner` | `task` |
| `unified` | `action` |
| `verifier` | `verdict` |
| `reflector` | `diagnosis` |
| `self_modify` | `wiring_patch` |

Wrong type means the node emits a failure signal. No hidden fallback path is introduced.

## Running

From a clean unpacked repository:

```powershell
python validate_repo.py
python organism.py --reset --max-ticks 1 --max-brain-calls 2 "observe the screen"
python workbench.py
```

Workbench listens on:

```text
http://localhost:8800
```

## Switching brains

Edit `wiring.json` or use the workbench panel:

```json
"model": {
  "transport": "openai"
}
```

Valid values in this package:

```text
openai
xai_responses
grok_build_api
opencode
grok_build
file_proxy
browser_ai
```

`browser_ai` intentionally raises until implemented.

## Provider setup

### LM Studio / OpenAI-compatible

Default:

```json
"transport": "openai",
"openai": {
  "host": "http://localhost:1234",
  "endpoint_path": "/v1/chat/completions",
  "model": "nvidia-nemotron-3-nano-4b"
}
```

LM Studio must be listening before the organism starts. If it is down, the call raises.

### xAI Responses

```powershell
$env:XAI_API_KEY="..."
```

Use `xai_responses` for general Grok models and `grok_build_api` for `grok-build-0.1`.

### OpenCode

Set `model.opencode.exe` if the default path is wrong. Default command shape:

```powershell
opencode run --model opencode/nemotron-3-ultra-free --format json "Follow the attached prompt." --file <prompt-file>
```

### Grok Build CLI

Install/sign in to Grok Build, then select `grok_build`. Default command shape:

```powershell
grok -p <prompt> -m grok-build --output-format streaming-json
```

### File proxy / human brain

Select `file_proxy`. The organism writes `comms/request.json`. A human or external agent writes `comms/response.json` with one of:

```json
{"content":"..."}
```

or:

```json
{"choices":[{"message":{"content":"..."}}]}
```

The response is archived under `comms/archive/` after consumption.

## Logging

| File | Meaning |
|---|---|
| `state.json` | Current live truth snapshot |
| `comms/runtime.ndjson` | Compact lifecycle events |
| `<timestamp>.txt` | Raw brain request/response forensic log |
| `comms/cli_prompts/*.prompt.txt` | Temporary CLI prompt attachments, only kept when configured |

Raw logs are evidence, not live state.

## Tested in this package

Tested here:

```text
python validate_repo.py
→ OK: structural validation passed
```

Not tested here because this sandbox has no Windows UI session and no provider credentials/listeners:

```text
real desktop observe/click/type loop
LM Studio call
xAI Responses call
Grok Build CLI call
OpenCode CLI call
file_proxy two-call handoff
```

Minimal falsification experiments:

```powershell
# structural only
python validate_repo.py

# one ROD planner decision through current model.transport
python organism.py --reset --max-ticks 1 --max-brain-calls 2 "observe the screen"

# workbench ROD test for a selected brain node
python workbench.py
# click: Test ROD (2-call)
```

## File tree expected in this package

```text
.gitattributes
.gitignore
LICENSE
README.md
actions.py
brain.py
desktop.py
nodes.py
organism.py
workbench.py
wiring.json
state.json
validate_repo.py
seed_nodes/
  act.py
  observe.py
  planner.py
  reflect.py
  satisfied.py
  scheduler.py
  self_modify.py
  verify.py
seed_brains/
  browser_ai.py
  file_proxy.py
  grok_build.py
  grok_build_api.py
  openai.py
  opencode.py
  xai_responses.py
```
