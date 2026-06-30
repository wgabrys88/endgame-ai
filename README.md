# endgame-ai fixed source package

This archive is a clean, source-only build of `endgame-ai` prepared as `endgame-ai-fixed.zip`.

## What the system is

`endgame-ai` is a small Windows desktop organism:

- Python is the mechanical body.
- `wiring.json` is the mutable brain/topology configuration.
- `seed_nodes/` templates are copied to `live_nodes/` at runtime.
- `seed_brains/` transport templates are copied to `live_brains/` at runtime.
- The topology is wiring-defined.
- Nodes are hot-swappable modules that emit exactly one signal and one patch.
- Brain transports are also hot-swappable node-like modules selected only by `model.transport`.
- ROD remains a two-call brain pattern: Reason → Observe/commit → Decide.

This is not a LangChain/MCP/CCA replacement. The core uses only the Python standard library.

## Fail-hard rule

There are no hidden transport fallbacks. If `model.transport` is `openai`, the organism calls only `live_brains/openai.py`. If LM Studio is not listening, the selected transport raises a clear error and the organism stops. It does not auto-switch to OpenCode, xAI, Grok, or file proxy.

## Validate

From PowerShell in the repository root:

```powershell
python validate_repo.py
python -m py_compile brain.py nodes.py organism.py workbench.py actions.py desktop.py
python - <<'PY'
import py_compile, pathlib
for d in ["seed_nodes", "seed_brains"]:
    for p in pathlib.Path(d).glob("*.py"):
        print("compile", p)
        py_compile.compile(str(p), doraise=True)
PY
```

## Run the organism

```powershell
python organism.py --reset --max-ticks 1 --max-brain-calls 2 "open notepad"
```

With the default wiring, `model.transport` is `openai`, which targets LM Studio at `http://localhost:1234/v1/chat/completions`. Start LM Studio's local server first, or expect a hard failure.

To test `file_proxy` without cloud/local model calls, edit `wiring.json`:

```json
"model": { "transport": "file_proxy" }
```

Then run the organism. It will write `comms/request.json` and wait for a matching `comms/response.json` with this shape:

```json
{
  "content": "{\"record_type\":\"plan\",\"data\":{\"next_signal\":\"observe\",\"intent\":\"open notepad\"}}",
  "reasoning": "human/file proxy response"
}
```

## Workbench

Start the optional workbench:

```powershell
python workbench.py
```

Open:

- `http://127.0.0.1:8800/`
- `http://127.0.0.1:8800/workbench.html`
- `http://127.0.0.1:8800/api/status`

The workbench is optional. The organism does not require it. The server catches expected browser disconnects such as Windows `WinError 10053`/connection aborts and keeps running quietly, while real internal handler errors still return a visible `500` response.

### API controls

```powershell
Invoke-WebRequest http://127.0.0.1:8800/api/status
Invoke-WebRequest -Method OPTIONS http://127.0.0.1:8800/api/control
Invoke-WebRequest -Method POST http://127.0.0.1:8800/api/control -ContentType "application/json" -Body '{"mode":"pause"}'
Invoke-WebRequest -Method POST http://127.0.0.1:8800/api/control -ContentType "application/json" -Body '{"mode":"step"}'
Invoke-WebRequest -Method POST http://127.0.0.1:8800/api/control -ContentType "application/json" -Body '{"mode":"run"}'
```

## STEP mode

STEP mode is centralized in `organism.py` immediately before node execution. Nodes do not contain step logic.

Control file: `comms/control.json`

```json
{
  "mode": "run",
  "step_token": 0,
  "updated_at": 0
}
```

Modes:

- `run`: execute normally.
- `pause`: pause before executing the next topology node.
- `step`: execute exactly one node per new `step_token`, then pause again before the following node.

Missing `comms/control.json` is documented as `run` and will be created automatically. Malformed JSON or an invalid mode is a hard error.

When paused, `state.json` uses `_phase: "paused_before_node"`. When a step token is consumed, `comms/runtime.ndjson` records the node that was allowed.

## Brain transports

Transport selection is only through `wiring.json` → `model.transport`. Implementations live in `seed_brains/` and are copied to `live_brains/`.

Every brain transport exports:

```python
def call(messages, cfg):
    return {"content": "...", "reasoning": "..."}  # or raise
```

Supported seed transports:

- `openai`: OpenAI-compatible chat completions, defaulting to LM Studio at `localhost:1234`.
- `file_proxy`: writes a request JSON and waits for a response JSON.
- `opencode`: calls an explicitly configured OpenCode executable.
- `xai_responses`: calls xAI Responses only when `XAI_API_KEY` is present.
- `grok_build`: calls a configured `grok` CLI.
- `browser_ai`: documented fail-hard stub, not a silent fallback.

## Common errors

- `WinError 10061` / connection refused for `openai`: LM Studio's local server is not running or is not listening on `http://localhost:1234`. Start LM Studio Local Server or intentionally change `model.transport`.
- `WinError 10053` from workbench/browser: a browser disconnected while a response was being written. This package suppresses expected disconnect stack traces.
- OpenCode executable missing: the configured `model.opencode.executable` does not exist and is not on `PATH`. Install OpenCode or intentionally change wiring.
- xAI API key missing: `XAI_API_KEY` is not set. Set it only when you intend to use paid xAI calls.

## Tested in this packaging session

- `python validate_repo.py` passed in the unpacked archive.
- `python -m py_compile brain.py nodes.py organism.py workbench.py actions.py desktop.py` passed.
- Every `seed_nodes/*.py` and `seed_brains/*.py` compiled.
- `file_proxy` path was exercised with `--max-ticks 1 --max-brain-calls 2` and a synthetic file response.
- The source zip excludes `.git/`, `__pycache__/`, `.pytest_cache/`, `live_nodes/`, `live_brains/`, `comms/`, raw `*.txt` logs, `state.json`, and `goal.json`.

## Experiment pending

- Windows 11 GUI/body execution was not performed in this Linux packaging environment.
- Real LM Studio success is pending until a server is listening on `localhost:1234`.
- OpenCode and xAI/Grok real provider success are pending until executables/API keys are available.

Research organism, not a product. Run only where full desktop control is acceptable.
