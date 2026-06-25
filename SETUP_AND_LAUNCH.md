# Setup And Launch

## Browser Preparation

1. Open Chrome, Edge, Opera, or another supported browser.
2. Open a chat provider such as Grok, ChatGPT, Claude, Gemini, Perplexity, or Poe.
3. Sign in, select the model you want, and leave the chat composer visible.
4. Do not leave the browser address bar focused. Click inside the chat page or composer once.

Browser relay depends on provider accounts, rate limits, UI state, and Windows focus behavior.

## Start The Root Workbench

```powershell
cd C:\Users\px-wjt\Downloads\endgame-ai
$env:PYTHONIOENCODING='utf-8'
python server.py
```

If `python` is not on `PATH`, use the local interpreter path:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" server.py
```

Open:

```text
http://127.0.0.1:9077/
```

The root panel can start and stop managed slots:

- Slot 1 worker: `http://127.0.0.1:9078/`
- Slot 2 browser relay: `http://127.0.0.1:9079/`

`colony.py` remains a compatibility wrapper, but the root panel is the preferred launcher.

## Queue Layout

Endgame-AI uses separate file paths for cognition and browser relay:

- Slot 1/root cognition: `comms/slot1_cognition/request.json`, `comms/slot1_cognition/response.json`
- Slot 2 cognition: `comms/relay_cognition/request.json`, `comms/relay_cognition/response.json`
- Browser relay handoff: `comms/llm_proxy/request.json`, `comms/llm_proxy/response.json`

Slot 2 auto-starts with `prompts/wiring_relay.json` and polls the browser relay handoff. It answers that handoff by controlling the already-open browser chat through Endgame-AI observe/act paths.

## Model Configs

Default checked-in configs use file-proxy cognition:

```text
prompts/model.json        Slot 1/root cognition
prompts/model_relay.json  Slot 2 cognition
```

To use LM Studio for a slot, set that slot's model config transport to `openai` and confirm the configured `host` serves `/v1/chat/completions`.

## Start A Goal

From the panel, choose Slot 1 and click Run. Or use PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/slots/start -ContentType 'application/json' -Body '{"slots":[1,2]}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/slots/run -ContentType 'application/json' -Body '{"slot":1,"goal":"Use the browser relay when high-level reasoning is needed, then complete the requested project change and verify it."}'
```

Monitor:

```text
GET http://127.0.0.1:9077/system
GET http://127.0.0.1:9077/wiring/audit
GET http://127.0.0.1:9077/llm-proxy/status
GET http://127.0.0.1:9077/relay/status
```

Use `/llm-proxy/clear` for active cognition proxy files and `/relay/clear` for browser-relay handoff files.
