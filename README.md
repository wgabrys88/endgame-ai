# endgame-ai unified runtime patch

This zip is a replacement-files patch for the branch that already contains the main project files. Copy these files over the project root and replace the existing versions.

## What changed

This patch keeps the ROD organism architecture intact: wiring controls topology, nodes remain hot-swappable Python modules, the brain is stateless, and failures raise instead of silently falling back. The changes are focused on the two failures shown in the attached run logs.

### 1. OpenCode transport repair

Observed failure from your run:

```text
RuntimeError: opencode transport: [WinError 2] The system cannot find the file specified
```

This means the selected executable could not be resolved by the Python process. The new `brain.py` now resolves Windows executables more explicitly, including `.exe`, `.cmd`, `.bat`, and `.ps1` candidates, and raises a precise hard failure that names the candidates if OpenCode is not installed or not on the Python PATH.

OpenCode now defaults to:

```json
"format": "json",
"prompt_mode": "file",
"skip_permissions": false
```

`prompt_mode=file` writes the full stateless system/user prompt to `comms/cli_prompts/*.prompt.txt` and calls `opencode run --file <prompt-file> ...` with a short instruction. This avoids long Windows command lines and avoids leaking the entire prompt into raw argv logs. Temporary prompt files are deleted after the call unless `keep_prompt_files` is enabled.

Why `skip_permissions=false`: OpenCode is being used here as a brain transport, not as the desktop actor. The organism already has the body and acts through `actions.py`. The brain should return text records, not mutate the repository during cognition calls. You can still turn the permission flag on from the workbench when you intentionally want that experiment.

### 2. Grok Build NDJSON repair

Observed failure from your run:

```text
Error: Couldn't set model 'grok-build-0.1': Invalid params: "unknown model id". Run 'grok models' to see available models.
```

The CLI model default is now `grok-build`, because that is the model id shown working in your later run. The direct xAI Responses API path still keeps `grok-build-0.1`, because that is a separate API transport.

Observed behavior after the model was corrected: Grok Build emitted streaming NDJSON chunks like:

```json
{"type":"thought","data":"..."}
{"type":"text","data":"..."}
```

The old parser treated that stream as raw text. The new parser reconstructs final content from `type=text` chunks and separate reasoning from `type=thought` chunks, then applies the same typed-record JSON extraction as every other transport.

### 3. Reliable workbench rewrite

`workbench.py` has been rewritten around a compact live truth surface:

| File | Purpose | Used by panel |
|---|---|---|
| `state.json` | Latest organism snapshot, atomically written before and after each node | Yes |
| `comms/runtime.ndjson` | Compact append-only event stream: organism lifecycle, node start/signal, brain request/response, CLI start/exit, usage | Yes |
| `comms/brain_usage.ndjson` | Structured usage ledger with exact provider usage when returned | Yes |
| `comms/session-*.log` | Raw forensic prompt/response journal | Listed, not polled as state |
| `comms/brain_io.ndjson` | Optional raw transport JSON | Disabled by default |

The panel no longer treats bulky debug logs as current state. It shows state age, runtime event age, phase, node, transport, compact screen summary, current step, history, reasoning snippets, usage, and file purposes. If `state.json` is old, the panel says stale instead of pretending the data is live.

### 4. Atomic state writes

`organism.py` now writes `state.json` atomically. It saves before every node starts and after the node emits a signal, so the panel can display a real active node during long brain calls instead of waiting for the call to finish.

## Files in this zip

```text
README.md
brain.py
organism.py
wiring.json
workbench.py
```

No node topology has been changed. No prompts have been weakened. No fallback brain has been added.

## How to install

1. Stop `organism.py` and `workbench.py`.
2. Unzip this archive.
3. Copy the files into the project root, replacing existing files.
4. Optional but recommended for a clean run:

```powershell
Remove-Item .\state.json -ErrorAction SilentlyContinue
Remove-Item .\comms\runtime.ndjson -ErrorAction SilentlyContinue
```

5. Start the workbench:

```powershell
python .\workbench.py
```

6. Start the organism:

```powershell
python .\organism.py --reset "write in notepad what do you see and then it will be task completed"
```

## Minimal falsification tests

### LM Studio / OpenAI-compatible core

Start LM Studio server, then run:

```powershell
python .\organism.py --reset --max-ticks 1 "observe the screen"
```

Pass condition: `state.json` updates, `comms/runtime.ndjson` contains `brain_request` and `brain_response`, and the workbench shows fresh state.

### OpenCode transport

From the same PowerShell that runs Python:

```powershell
opencode --help
opencode run --format json "Return {\"ok\":true} and nothing else"
```

If PowerShell can run `opencode` but Python still cannot, set `model.opencode.exe` in the workbench to the full path, usually one of:

```text
C:\Users\<you>\AppData\Roaming\npm\opencode.cmd
C:\ProgramData\chocolatey\bin\opencode.exe
```

Then switch brain to OpenCode and run:

```powershell
python .\organism.py --reset --max-ticks 1 "observe the screen"
```

Pass condition: runtime events show `cli_start`, `cli_exit`, `brain_response`; no `WinError 2`; parsed planner record appears in `state.json`.

### Grok Build CLI

Run:

```powershell
grok models
```

Confirm `grok-build` appears. Then switch brain to Grok Build in the workbench.

Pass condition: streaming JSON is reconstructed into a final typed record instead of being stored as raw NDJSON lines.

### Workbench truthfulness

With the organism stopped, wait 10 seconds and refresh the panel.

Pass condition: health shows stale/current honestly based on file age. It must not claim live execution when no state/runtime events are changing.

With the organism running, the panel should show a current active node and recent runtime events even during long brain calls.

## Tested in this patch build

Tested-in-session in the sandbox:

```text
python3 -m compileall -q .
import brain, nodes, organism, workbench, actions in a full main-project copy
parse attached Grok Build NDJSON stream into final content + reasoning
extract typed JSON record from reconstructed Grok Build content
fake OpenCode executable with --format json + prompt_mode=file
fake Grok executable with streaming-json text chunks
workbench compact status generation against attached state/runtime/usage files
```

Experiment pending on your machine:

```text
real Windows OpenCode executable resolution
real OpenCode account/model invocation
real Grok Build CLI model list and live invocation
real desktop UI action loop with Windows accessibility APIs
```

Those require your Windows environment and installed providers. The code now fails with concrete reasons and the panel exposes the live evidence needed to diagnose the next run.
