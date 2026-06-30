# endgame-ai corrected runtime package

A living Windows desktop organism driven by hot-swappable Python nodes and hot-swappable brain nodes.

This package keeps the ROD topology and fail-hard philosophy. It does **not** add fallback transport switching. If the selected brain is unavailable, the organism fails loudly and writes the evidence to `state.json`, `comms/runtime.ndjson`, and the raw `*.txt` brain log.

## What changed in this correction

- Default `model.transport` is now `opencode`, matching the runtime evidence where OpenCode completed the two-call ROD workbench test on this machine.
- `openai` still exists as a brain node for LM Studio/OpenAI-compatible servers, but it now reports a direct hint when `localhost:1234` refuses the connection.
- The workbench UI is split into a standalone `workbench.html` file. You may open it from the server or directly as a local HTML file.
- `workbench.py` is now a small CORS-enabled JSON API + static file server. The API is still required for filesystem and process access; a browser-only HTML file cannot safely write `wiring.json`, `goal.json`, or `comms/control.json` without a local API.
- Added a single chokepoint stepper in `organism.py`: `_step_gate()` runs before every topology node. No node file knows about stepping.
- Workbench buttons now control the organism through `comms/control.json`:
  - **Run**: free-running loop.
  - **Pause**: wait before the next node.
  - **Step one node**: execute exactly one topology node, then wait again.
- Workbench polling no longer aborts in-flight fetches every second, and the API silently ignores disconnected-browser write errors.
- `validate_repo.py` validates the new `workbench.html` file and the existing topology/brain-node structure.

## Runtime files

| File | Role |
|---|---|
| `wiring.json` | Topology, prompts, verbs, brain config |
| `seed_nodes/` | Source templates copied to `live_nodes/` on first run |
| `seed_brains/` | Source templates copied to `live_brains/` on first run |
| `state.json` | Current organism snapshot |
| `comms/runtime.ndjson` | Compact lifecycle events |
| `*.txt` | Raw brain request/response forensic logs |
| `comms/control.json` | Human debugger control: run/pause/step |
| `workbench.html` | Standalone UI file |
| `workbench.py` | Local CORS API for the UI |

## Run

```powershell
python validate_repo.py
python workbench.py
python organism.py --reset --max-ticks 1 --max-brain-calls 2 "open notepad"
```

Workbench:

```text
http://127.0.0.1:8800/
```

Or open `workbench.html` directly in Chrome/Opera. Keep `python workbench.py` running, because the HTML talks to the API at `http://127.0.0.1:8800`.

## Brain nodes

Selected by `wiring.json -> model.transport`.

| Transport | Node | Notes |
|---|---|---|
| `opencode` | `seed_brains/opencode.py` | Default in this package; stateless CLI call |
| `openai` | `seed_brains/openai.py` | LM Studio/OpenAI-compatible `/v1/chat/completions`; requires a server listening on `localhost:1234` unless rewired |
| `xai_responses` | `seed_brains/xai_responses.py` | xAI Responses API; requires `XAI_API_KEY` |
| `grok_build_api` | `seed_brains/grok_build_api.py` | Alias/copy for Grok Build through xAI Responses |
| `grok_build` | `seed_brains/grok_build.py` | Headless Grok CLI |
| `file_proxy` | `seed_brains/file_proxy.py` | Human/agent handoff via JSON files |
| `browser_ai` | `seed_brains/browser_ai.py` | Stub; fail-hard |

## Evidence discipline

Claims are measured by artifacts:

- `state.json`: current truth.
- `comms/runtime.ndjson`: lifecycle events.
- Raw `*.txt`: exact brain transport requests/responses.
- `validate_repo.py`: structural/syntax check only; it does not prove Windows UI control or remote brain availability.

## Important diagnosis from the supplied run

The `openai` failure was a refused TCP connection to `http://localhost:1234/v1/chat/completions`. That means the selected OpenAI-compatible brain was not listening. This package does not hide that behind fallback logic; it defaults to `opencode` for this machine and leaves `openai` available when LM Studio is explicitly running.

The workbench `WinError 10053` was a disconnected-browser write. It is not evidence that the organism crashed. The corrected API catches that class of socket close and the frontend avoids unnecessary request aborts.
