# 5. File Proxy Transport: The Universal Bridge

## How It Works

```json
"transport_file_proxy": {
  "request_path": "runtime_request.json",
  "response_path": "runtime_response.json",
  "poll_interval": 0.25,
  "timeout": 86400
}
```

1. Organism writes `runtime_request.json` (system prompt + user payload + fresh observation)
2. **Anything** reads it: human, another AI, another endgame-ai instance, a script
3. That thing writes `runtime_response.json` (valid JSON with `record_type`, `data`, `reasoning`)
4. Organism polls, reads, validates, continues

## Why This Changes Everything

```
┌─────────────────────────────────────────────────────────────┐
│                    FILE PROXY TRANSPORT                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐  │
│   │  Human   │    │  GPT-4   │    │  Claude  │    │ Grok │  │
│   │  (you)   │    │  (API)   │    │  (API)   │    │ (API)│  │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    └──┬────┘  │
│        │               │               │               │      │
│        ▼               ▼               ▼               ▼      │
│   ┌─────────────────────────────────────────────────────┐    │
│   │              runtime_request.json                    │    │
│   │  {system_prompt, goal, state, fresh_observation}     │    │
│   └─────────────────────────────────────────────────────┘    │
│                        │                                     │
│                        ▼                                     │
│   ┌─────────────────────────────────────────────────────┐    │
│   │              runtime_response.json                   │    │
│   │  {record_type, data:{next_signal, ...}, reasoning}   │    │
│   └─────────────────────────────────────────────────────┘    │
│                        │                                     │
│                        ▼                                     │
│              ┌─────────────────┐                             │
│              │  endgame-ai     │                             │
│              │  organism body  │                             │
│              └─────────────────┘                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**No MCP servers. No skills. No pip install.** The protocol is: *write JSON, read JSON*. Any agent that can read/write files participates.

## Multi-Agent / Multi-Instance

Two endgame-ai instances can talk via a shared directory:
- Instance A writes request → Instance B reads, writes response → Instance A continues
- A human can step in at any tick, inspect the request, write a response
- CI/CD can inject responses for testing

## ROD (Reasoning on Demand) Injection

```json
"reasoning": {
  "enabled": true,
  "pattern": "two_pass",
  "injection_template": "ROD_REASONING_CONTENT:\n{reasoning}",
  "extractor": "think_tags"
}
```

The organism can request reasoning from *any* brain, then inject it back for a second pass — regardless of which transport produced it.