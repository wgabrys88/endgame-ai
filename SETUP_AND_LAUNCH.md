# Setup And Launch

## Browser Preparation

1. Open Opera, Chrome, or Edge.
2. Open one chat tab for the high-intelligence model: ChatGPT, Claude, Gemini, Perplexity, or Poe.
3. Sign in, select the desired strong model, and leave the chat composer visible.
4. Do not leave the browser address bar focused. Click inside the chat page or composer once.

## Launch Both Slots

```powershell
cd C:\Users\px-wjt\Downloads\endgame-ai
python colony.py 1 2
```

`colony.py` now starts:

- Slot 1 on `prompts/wiring.json` at `http://127.0.0.1:9078`
- Slot 2 on `prompts/wiring_relay.json` at `http://127.0.0.1:9079`
- shared bus at `bus.json`
- shared relay files under `comms/`

Slot 2 auto-starts and polls `comms/llm_request.json`. Slot 1 starts when you post a project goal.

## Recommended `prompts/model.json`

Use a deterministic local model for both slots:

```json
{
  "host": "http://localhost:1234",
  "model": "nvidia-nemotron-3-nano-4b",
  "temperature": 0.3,
  "temperature_bump": 0.15,
  "top_p": 0.9,
  "top_k": 20,
  "max_tokens": 2048,
  "timeout": 900,
  "stream": false
}
```

The browser tab can run GPT-5.5, Claude, or another stronger web model. The local model only needs to drive the ROD wiring safely.

## Start The Main Project Goal On Slot 1

Open the Slot 1 workbench:

```text
http://127.0.0.1:9078
```

Post a goal through the UI, or use PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/run -ContentType 'application/json' -Body '{"goal":"Use the browser relay when you need high-level reasoning. Then implement the requested project change and verify it."}'
```

When Slot 1 needs help, it emits:

```json
{
  "id": "slot1-...",
  "status": "pending",
  "from_slot": 1,
  "prompt": "..."
}
```

Slot 2 claims it, submits it to the browser chat, captures the latest assistant response, writes `comms/llm_response.json`, and archives the request under `comms/archive/`.

## Workbench Monitoring

- Slot 1 workbench: `http://127.0.0.1:9078`
- Slot 2 workbench: `http://127.0.0.1:9079`
- Bus: `http://127.0.0.1:9078/bus`
- Slot 1 state: `state.slot1.json`
- Slot 2 state: `state.slot2.json`
- Relay handoff: `comms/llm_request.json`, `comms/llm_response.json`

## Example Initial Goal

```text
Build a concise DESIGN.md for this repository. First ask the browser relay to analyze the architecture and identify the three highest-leverage improvements. Then use MEMORY.llm_response to write DESIGN.md, keeping it specific to Endgame-AI, and verify the file exists.
```
