# endgame-ai

Endgame-AI is a local Windows desktop agent built around a runtime wiring graph. The server observes the desktop, asks an LLM circuit what to do next, executes constrained actions, verifies progress, and can update its wiring when the graph itself is the blocker.

The intended control surface is the web panel served by `server.py`. CLI helpers remain for compatibility, but normal operation should start from the panel.

## Current Architecture Checklist

- [x] Runtime wiring graph in `prompts/wiring.json`
- [x] Optional Slot 2 browser relay wiring in `prompts/wiring_relay.json`
- [x] Atomic state, bus, and relay file writes
- [x] Server-served HTML workbench
- [x] Runtime LLM transport toggle: LM Studio or agent file self-proxy
- [x] File-backed self-proxy request/response contract
- [x] Panel-managed slots 1 and 2
- [x] Panel-visible file-proxy queue/status
- [x] Panel-visible wiring audit diagnostics
- [x] README validation checklist completed after implementation

## Run Flow

1. Start the root server:

   ```powershell
   python server.py
   ```

2. Open the panel:

   ```text
   http://127.0.0.1:9077/
   ```

3. Choose the LLM transport in the panel:

   - `LM Studio`: send OpenAI-compatible chat completions to `prompts/model.json` `host`.
   - `Agent file self-proxy`: write the model request to disk and wait for a response file.

4. Start slots from the panel when needed:

   - Slot 1 runs the main desktop agent.
   - Slot 2 runs the optional browser relay wiring for high-intelligence browser chat handoff.

5. Run goals from the panel. The backend `/run` and slot endpoints are the canonical execution path.

## LLM Transports

### LM Studio

`openai` transport keeps the original behavior:

```json
{
  "transport": "openai",
  "host": "http://localhost:1234",
  "model": "nvidia-nemotron-3-nano-4b"
}
```

The server sends `POST /v1/chat/completions` and reads `choices[0].message.content` plus optional `reasoning_content`.

### Agent File Self-Proxy

`file_proxy` transport lets Codex, Claude Code, OpenCode, Grok Build, or another coding agent act as the model without Endgame-AI knowing it is not talking to LM Studio.

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

Request file shape:

```json
{
  "id": "llm-...",
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

Response may be simplified:

```json
{
  "id": "llm-...",
  "content": "{\"record_type\":\"task\",\"data\":{\"steps\":[]}}",
  "reasoning_content": "short reasoning trace"
}
```

or OpenAI-compatible:

```json
{
  "id": "llm-...",
  "choices": [
    {
      "message": {
        "content": "{\"record_type\":\"task\",\"data\":{\"steps\":[]}}",
        "reasoning_content": "short reasoning trace"
      }
    }
  ]
}
```

The server writes one active request atomically, polls every second for a matching response, consumes the response, deletes the active request, and archives request/response copies.

## HTTP Interfaces

- `GET /system`: transport, slot status, file-proxy status, ports, and run status.
- `POST /system/transport`: set and persist `openai` or `file_proxy`.
- `POST /slots/start`: start slots, default `[1, 2]`.
- `POST /slots/stop`: stop panel-managed slots.
- `POST /slots/run`: post a goal to a selected slot, default slot `1`.
- `GET /llm-proxy/status`: pending request, response presence, paths, and archive status.
- `POST /llm-proxy/clear`: clear stale active proxy files after explicit confirmation.
- `GET /wiring/audit`: cross-reference diagnostics for topology, prompts, verbs, rules, and MoE.

## Wiring Audit Targets

The audit should report:

- unreachable graph nodes
- edges pointing at missing nodes
- nodes with missing Python handlers
- node circuits without prompt roles
- prompt-mentioned verbs absent from `verbs`
- rules using unknown match keys
- MoE route configuration status

Experimental systems such as MoE are not deleted. They are made visible, diagnosable, and easier to activate safely.

## Validation Checklist

Run before the final commit:

```powershell
Get-Content -Raw prompts\wiring.json | ConvertFrom-Json | Out-Null
Get-Content -Raw prompts\wiring_relay.json | ConvertFrom-Json | Out-Null
python -m compileall -q .
python -m pyright server.py colony.py
```

Manual UI validation:

- [x] Root panel loads at `http://127.0.0.1:9077/`
- [x] Transport toggle persists to `prompts/model.json`
- [x] File proxy shows request and response status
- [x] Slot 1 and Slot 2 can be started/stopped from the panel
- [x] Slot goal posting works from the panel
- [x] Wiring audit renders actionable diagnostics
- [x] Graph remains usable on desktop and narrow screens
