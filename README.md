# Endgame-AI Handover Bootstrap

This file is the current handover prompt and operating notebook for the Endgame-AI self-proxy and browser-relay work. It is written for the next Codex, Claude Code, Grok Build, OpenCode, or other coding agent that resumes this repository.

Do not treat the Grok review loop as complete. The loop was started, the desktop observer saw Grok in Chrome, Slot 1 was started, and one file-proxy planner reasoning request was serviced. The run was then stopped deliberately so this handover could be committed in a clean, resumable state.

## Bootstrap Prompt For Next Agent

Copy this into a fresh coding-agent session:

```text
You are resuming Endgame-AI in C:\Users\px-wjt\Downloads\endgame-ai on branch codex/self-referential-relay.

First read README.md fully, then read C:\Users\px-wjt\.codex\attachments\b7ca812f-a89a-443b-835d-afbe6f104d0b\goal-objective.md if accessible. Treat the current worktree and runtime state as authoritative.

User intent:
- Endgame-AI should become a local Windows desktop agent that can use browser AIs such as Grok, ChatGPT, Claude, Gemini, or Hugging Face models as external intelligence through the GUI.
- The user explicitly approved sharing repository files, including server.py, with Grok for review.
- The user explicitly approved using the computer. Actual browser/desktop control must happen through Endgame-AI observe/act/runtime paths, not manual browser automation by the coding agent.
- Shell and file edits are allowed for repository development, local server operation, validation, commits, and writing file-proxy responses.

Current objective:
1. Finish the Endgame-AI driven multi-message Grok review conversation about Endgame-AI itself.
2. Share server.py or the relevant server.py implementation with Grok and ask for review of self-proxy, slot management, desktop actions, and wiring audit behavior.
3. Ask Grok a follow-up about whether observed behavior proves the system is correct, or what must be fixed before claiming it works.
4. Use Grok's review plus local evidence to identify correctness gaps and fix the system.
5. Stop the system when done.
6. Rewrite README.md from zero as the final real-life capabilities and operating guide.
7. Validate and commit.

Important status:
- Two foundation commits already exist:
  - 397ff54 Add relay slot foundation
  - fe25061 Add self proxy transport and unified panel
- A later handover commit may contain this README and the desktop long-text paste fix.
- The Grok review loop is not complete.
- The most important suspected architecture gap is that there are currently two file handoff mechanisms:
  - llm() file_proxy uses comms/llm_proxy/request.json and comms/llm_proxy/response.json.
  - Slot 2 relay wiring uses runtime.llm_request_path comms/llm_request.json and comms/llm_response.json.
  Verify whether they should be unified. Do not claim Slot 2 services llm() file_proxy requests until this is proven or fixed.

Start by running:
git status --short --branch
git log --oneline -5
Get-Content -Raw prompts\model.json
Get-Content -Raw prompts\wiring.json | ConvertFrom-Json | Out-Null
Get-Content -Raw prompts\wiring_relay.json | ConvertFrom-Json | Out-Null
python -m compileall -q .
python -m pyright server.py colony.py desktop.py

Then inspect live runtime:
try { (Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:9077/system -TimeoutSec 5).Content } catch { $_.Exception.Message }
Get-NetTCPConnection -LocalPort 9077,9078,9079 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess

If no root server is running, start it from the repo:
$env:ENDGAME_SLOT='0'
$env:PYTHONIOENCODING='utf-8'
python server.py

Open the panel at http://127.0.0.1:9077/.
For coding-agent-as-LLM mode, set transport to file_proxy with POST /system/transport or the UI.
For LM Studio mode, set transport to openai and make sure LM Studio is serving prompts/model.json host.

To resume the Grok test:
1. Ensure Grok is open in Chrome and Endgame-AI can observe it.
2. Start Slot 1 from the panel or POST /slots/start with {"slots":[1]}.
3. Post a Slot 1 goal that asks Endgame-AI to use the already-open Grok chat for a two-message review conversation.
4. Service comms/llm_proxy/request.json as the model by writing matching comms/llm_proxy/response.json files. Always preserve the request id.
5. Let Endgame-AI perform the desktop write/press/remember actions itself.
6. Capture evidence from /system, /health, /state, archived proxy files, and the Grok chat.

Do not mark the goal complete until every explicit requirement is proven by current evidence.
```

## Current Architecture

Endgame-AI is a local Windows desktop ROD loop:

- `server.py` hosts the HTTP API, graph runner, LLM transport, slot process manager, file-proxy transport, wiring audit, and panel endpoints.
- `desktop.py` observes Windows UIA and executes low-level click, write, press, hotkey, focus, scroll, and wait operations.
- `actions.py` maps declarative verbs from wiring into desktop operations and memory writes.
- `prompts/wiring.json` defines the main worker graph.
- `prompts/wiring_relay.json` defines the Slot 2 browser relay graph.
- `wiring-editor.html` is the canonical control panel.
- `prompts/model.json` controls runtime LLM transport.

The intended control flow is:

1. Start root server.
2. Use the web panel at `http://127.0.0.1:9077/`.
3. Choose `openai` for LM Studio or `file_proxy` for coding-agent self-proxy.
4. Start Slot 1 and Slot 2 from the panel when needed.
5. Run goals from the panel or `/slots/run`.
6. Inspect `/system`, `/llm-proxy/status`, `/wiring/audit`, `/state`, and `/bus`.

## Implemented Work

Already committed:

- Relay slot foundation in `prompts/wiring_relay.json`.
- Compatibility `colony.py` wrapper around panel-managed slots.
- File-backed LLM transport inside `llm(system, user, temperature)`.
- Runtime model transport toggle through `POST /system/transport`.
- Panel-managed slot start, stop, status, and goal posting.
- `/system`, `/llm-proxy/status`, `/llm-proxy/clear`, `/wiring/audit`, `/slots/start`, `/slots/stop`, `/slots/run`.
- Modernized panel surfaces for transport, slots, proxy queue, diagnostics, graph, and run state.
- Wiring audit diagnostics for missing handlers, invalid edges, missing prompt roles, unknown rule match keys, prompt verbs, reachability, and MoE status.

Current uncommitted or handover-stage work:

- `desktop.py` has a long-text paste path in `Desktop.type_text()`. It uses the clipboard for text longer than 80 characters or containing newlines, then restores the previous clipboard text. This is needed because sending `server.py` to Grok character by character is too slow and brittle.
- `prompts/model.json` may be set to `"transport": "file_proxy"` because the runtime test used coding-agent self-proxy mode.
- `README.md` has been rewritten into this handover document.

## Runtime Evidence From This Session

Observed desktop state through Endgame-AI:

```text
FOCUSED: Grok - Google Chrome
ELEMENTS: 5
[1] Edit "Address and search bar" = "grok.com"
[2] Edit "Ask Grok anything" = "Ask Grok"
WINDOWS:
  * Grok - Google Chrome
  - Codex
```

Runtime actions completed:

- Root server was running at `http://127.0.0.1:9077/`.
- Transport was switched to `file_proxy`.
- Slot 1 was started through `/slots/start`.
- Slot 1 received the Grok review goal through `/slots/run`.
- Slot 1 created `comms/llm_proxy/request.json`.
- The first planner reasoning response was written and consumed.
- The next planner content request was created.
- The run was intentionally stopped and the stale request was cleared after the handover request.

Last known clean state after stopping:

- Slot 1 stopped.
- Slot 2 not running.
- No active `comms/llm_proxy/request.json`.
- No active `comms/llm_proxy/response.json`.
- Archive exists for the first file-proxy exchange under `comms/llm_proxy/archive`.
- Root server may still be running on port `9077`; inspect before starting another copy.

## Known Correctness Gap To Investigate

There are two related but not yet proven-equivalent handoff systems:

1. `llm()` file-proxy transport:
   - Request: `comms/llm_proxy/request.json`
   - Response: `comms/llm_proxy/response.json`
   - Shape: OpenAI-like request with `messages`, `model`, `temperature`, `max_tokens`, plus `id`.
   - Response accepts simplified `{id, content, reasoning_content}` or OpenAI-compatible `choices`.

2. Slot 2 browser relay:
   - Request: `comms/llm_request.json`
   - Response: `comms/llm_response.json`
   - Shape: relay-specific request and response memory.
   - Implemented by `llm_request_check` and `llm_response_write` nodes.

The user wants a self-referential loop where the agent can use the browser AI it controls as its own brain. To prove that, one of these must be true:

- Slot 2 is updated to service `llm()` file-proxy requests directly, including OpenAI-style `messages`.
- Or Slot 1 uses the legacy `llm_request` and `llm_wait_response` verbs deliberately for browser-AI handoff, while `llm()` file_proxy remains the coding-agent self-proxy transport.
- Or a bridge/adapter converts between the two protocols.

Do not claim the browser relay is the transparent replacement for LM Studio until this is verified with a live run.

## File-Proxy Contract

Model config:

```json
{
  "transport": "file_proxy",
  "file_proxy": {
    "request_path": "comms/llm_proxy/request.json",
    "response_path": "comms/llm_proxy/response.json",
    "archive_dir": "comms/llm_proxy/archive",
    "poll_interval_ms": 1000
  }
}
```

Request shape:

```json
{
  "id": "llm-...",
  "status": "pending",
  "transport": "file_proxy",
  "created_at": 0,
  "model": "nvidia-nemotron-3-nano-4b",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.3,
  "max_tokens": 2048
}
```

Response shape:

```json
{
  "id": "llm-...",
  "content": "{\"record_type\":\"task\",\"data\":{\"steps\":[]}}",
  "reasoning_content": "optional reasoning"
}
```

PowerShell helper for future agents:

```powershell
$req = Get-Content -Raw 'comms\llm_proxy\request.json' | ConvertFrom-Json
$obj = [ordered]@{
  id = $req.id
  content = '{"record_type":"verdict","data":{"confirmed":true,"evidence":"...","reason":"..."}}'
  reasoning_content = 'short reasoning'
}
$json = $obj | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText((Resolve-Path 'comms\llm_proxy\response.json'), $json, [System.Text.UTF8Encoding]::new($false))
```

Use UTF-8 without BOM. The earlier UTF-16 PowerShell default response was not consumed by Python.

## Grok Review Resume Plan

Recommended bounded goal:

```text
Use the already-open Grok chat in Google Chrome to have a two-message review conversation about Endgame-AI. First send Grok the current server.py code or focused server.py excerpts for the LLM transport, file proxy, slot management, desktop action, and wiring audit paths. Ask for a focused architecture and behavior review. Wait for and remember Grok's response. Then send a follow-up asking whether the observed behavior proves the system is correct, or what must be fixed before claiming it works. Wait for and remember Grok's follow-up response. Use Endgame-AI desktop observe/act only for browser control.
```

For planner content, a valid response can be:

```json
{"record_type":"task","data":{"steps":[{"description":"Send Grok a focused Endgame-AI server.py review prompt with the relevant code paths","done_when":"The review prompt is submitted in the Grok chat"},{"description":"Remember Grok's first review response","done_when":"MEMORY contains Grok's first review response"},{"description":"Send Grok a follow-up asking whether observed behavior proves correctness or what must be fixed","done_when":"The follow-up message is submitted in the Grok chat"},{"description":"Remember Grok's follow-up response","done_when":"MEMORY contains Grok's follow-up response"}]}}
```

For act content when the screen shows `Ask Grok anything`, use the visible composer target. The long-text paste path should make this feasible:

```json
{"record_type":"action","data":{"conclusion":"EXECUTE","actions":[{"verb":"write","target":"Ask Grok anything","value":"<full review prompt and code>"},{"verb":"press","target":"enter","value":""}]}}
```

If Grok rejects the full `server.py` payload or the UI cannot accept it reliably, send a focused code packet containing:

- `llm()` and `llm_via_file_proxy`
- file-proxy helpers
- slot process manager endpoints
- `wiring_audit`
- desktop `type_text` and clipboard paste path
- `llm_request_check` and `llm_response_write`
- `prompts/model.json`
- relevant relay wiring paths from `prompts/wiring_relay.json`

Record this limitation honestly. The user's permission allows sharing files, but the browser UI may still impose size limits.

## Commands

Start root server:

```powershell
$env:ENDGAME_SLOT='0'
$env:PYTHONIOENCODING='utf-8'
python server.py
```

Inspect root:

```powershell
(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9077/system' -TimeoutSec 5).Content
```

Set file-proxy transport:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9077/system/transport' -Method Post -ContentType 'application/json' -Body '{"transport":"file_proxy"}'
```

Start Slot 1:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9077/slots/start' -Method Post -ContentType 'application/json' -Body '{"slots":[1]}'
```

Stop slots:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9077/slots/stop' -Method Post -ContentType 'application/json' -Body '{"slots":[1,2]}'
```

Clear stale proxy files:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9077/llm-proxy/clear' -Method Post -ContentType 'application/json' -Body '{"confirm":true}'
```

Validate:

```powershell
Get-Content -Raw prompts\wiring.json | ConvertFrom-Json | Out-Null
Get-Content -Raw prompts\wiring_relay.json | ConvertFrom-Json | Out-Null
Get-Content -Raw prompts\model.json | ConvertFrom-Json | Out-Null
python -m compileall -q .
python -m pyright server.py colony.py desktop.py
```

## Final README Still Needed

This README is a handover artifact, not the final product README. After the Grok review and correctness fixes are complete, rewrite it again from zero as a user-facing operating guide with:

- What Endgame-AI does in real work.
- How it uses local models, browser AIs, and coding agents.
- What "self-proxy" means.
- How to run with LM Studio.
- How to run with coding-agent file proxy.
- How to run with browser relay.
- What desktop navigation can and cannot safely do.
- How to monitor, debug, and recover.
- Clear proof-oriented validation steps.

Do not overclaim unlimited capability. The accurate claim is that Endgame-AI can route work across available local models, browser AIs, coding agents, and desktop tools, subject to accounts, rate limits, UI reliability, filesystem access, and explicit operator permissions.
