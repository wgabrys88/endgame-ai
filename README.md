# endgame-ai

Endgame-ai is a Windows 11 desktop automation organism written in pure Python. It observes the desktop through raw Win32 and UI Automation calls, projects the blackboard into role-specific contexts, asks an LLM backend for planner/actor/verifier/reflector decisions, executes typed verbs, and records every runtime phase as JSONL.

The current architecture treats the append-only blackboard event stream as the source of truth. Snapshot files are projections. Role contexts are projections. TUI output is a projection. Runtime logs are designed for the organism itself to read during self-diagnosis and future adaptation.

## Platform Contract

- Windows 11.
- Python 3.13.
- Zero third-party Python dependencies.
- Raw `ctypes` for Win32, UI Automation, process, keyboard, mouse, and console interaction.
- Pyright strict target: 0 errors, 0 warnings, 0 informations.
- Numeric constants live in `config.py`.
- The Lorenz, PID, and Jacobian mechanisms are core control laws and should not be removed.

## Runtime Command

ACP is the primary validation backend for this workspace. Run ACP first:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "your goal" --backend acp
```

Then compare with LM Studio:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "your goal" --backend lmstudio
```

Prompt mutation is disabled by default. Lessons are still extracted during reflection. To allow guarded one-line prompt mutation after enough same-role lessons accumulate, pass:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "your goal" --backend acp --enable-prompt-mutations
```

LM Studio is expected at:

```text
http://localhost:1234
```

LM Studio server logs are outside the workspace at:

```text
C:\Users\%USERPROFILE%\.cache\lm-studio\server-logs\2026-06\
```

Windows may report misleading server log metadata while readable content is still available through a shared read handle. LM Studio can rotate logs during a run, so read every touched file for the validation window.

## Static Gates

Use the local Python executable:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" -m compileall -q .
```

Pyright requires the bundled Node path in this environment:

```powershell
$env:PATH='C:\Users\%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH; & 'C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe' -m pyright
```

Useful source audits:

```powershell
rg -n "FALLBACK|fallback|cmd start|field_usage|log_screen|format_exc\(\)\[:" -S -g "*.py" -g "prompts/*.txt" -g "schemas/*.json"
rg -n "#" -g "*.py" -g "!config.py" -g "!__pycache__/**"
rg -n '"""' -g "*.py" -g "!__pycache__/**"
rg -n "'''" -g "*.py" -g "!__pycache__/**"
rg -n "(?<![A-Za-z_])-?\d+(?:\.\d+)?" -P -g "*.py" -g "!config.py" -g "!__pycache__/**"
```

## Runtime Cleanup

Runtime files are generated in the workspace root and `comms`.

```powershell
$root=(Resolve-Path .).Path
$runtimeNames=@('blackboard_state.json','blackboard_state.lock','blackboard_state.tmp','blackboard_events.jsonl','evolution_ledger.json','lessons.json')
Get-ChildItem -LiteralPath $root -Force -File | Where-Object { $_.Name -like 'log-*.jsonl' -or $_.Name -like 'validation-*.out' -or $runtimeNames -contains $_.Name } | Remove-Item -Force
Remove-Item -LiteralPath (Join-Path $root 'comms\screen_lock.json'),(Join-Path $root 'comms\screen_snapshot.json') -Force -ErrorAction SilentlyContinue
```

Create `comms\stop.txt` to request cooperative shutdown from every running agent loop. The main loop checks it before each iteration and before actions. ACP prompt waits also poll it, so ACP-backed agents can stop during model waits instead of sitting until the full request timeout.

If an isolated LM Studio validation is needed, truncate the active server log with a shared handle:

```powershell
$dir='C:\Users\%USERPROFILE%\.cache\lm-studio\server-logs\2026-06\'
$p=(Get-ChildItem -LiteralPath $dir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
$fs=[System.IO.File]::Open($p,[System.IO.FileMode]::OpenOrCreate,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::ReadWrite)
try { $fs.SetLength(0) } finally { $fs.Close() }
```

## File Map

- `main.py`: CLI entry point, backend selection, log lifecycle, snapshot save, evolution ledger append, child termination on exit.
- `orchestrator.py`: control loop, observe/plan/act/verify/reflect phases, child spawning, distillation spawning, explicit `read_file` path guard, role used-field telemetry.
- `state.py`: blackboard state, context projection, compact action evidence, PID/Lorenz/Jacobian state, child process termination hook.
- `log.py`: JSONL log writer, sequence numbers, TUI hook isolation, append to blackboard event stream.
- `persistence.py`: locked JSON persistence, per-agent snapshots, append-only blackboard events, inbox and child event mechanics.
- `observer.py`: desktop observation, foreground/window enumeration, probe sampling, UI Automation tree sampling, node merge/classification, rendered screen context, semantic screen signatures.
- `win32.py`: raw ctypes wrappers for Win32, UI Automation, process termination, input, window, and console primitives.
- `actions.py`: verb execution for click, write, press, hotkey, scroll, wait, focus, read_file, write_file, cmd, spawn_agent.
- `dispatch.py`: prompt/schema loading, role calls, response extraction.
- `llm.py`: LM Studio and ACP backend calls, request/response logging.
- `tui.py`: live state projection through the same JSONL event records.
- `sixel.py`: sixel rendering helpers.
- `lessons.py`: persisted lessons store.
- `event_schema.py`: runtime event schema helper.
- `config.py`: constants and context policy.
- `prompts/*.txt`: mutable role prompts.
- `schemas/*.json`: strict role response schemas.

## Logging Architecture

Every call to `log.log()` writes one JSON object to the agent log file and appends the same record to `blackboard_events.jsonl`.

Runtime record fields:

```json
{
  "version": 1,
  "sequence": 1,
  "timestamp_utc": "ISO-8601",
  "agent_id": "main",
  "iteration": 0,
  "phase": "run.start",
  "message": "run started",
  "data": {}
}
```

The blackboard event file is append-only. It is the durable event stream. `blackboard_state.json` is a projection with this shape:

```json
{
  "states": {
    "main": {}
  },
  "events": [],
  "agents": {},
  "meta": {}
}
```

Child agents write under their own `agent_id` inside `states` and write their own `log-<agent_id>-<timestamp>.jsonl` files. The shared `blackboard_events.jsonl` receives events from every agent.

The logger writes the file record and blackboard event before invoking the TUI hook. If the TUI hook raises, the logger records `tui.error` to the file and blackboard streams, detaches the TUI hook, and keeps the event source alive.

The TUI receives the same serialized log line as the file logger. Redirected PowerShell output can be UTF-16 with a BOM; strip the BOM and normalize CR line endings before JSON parsing.

## Observation Pipeline

Observation has three logged phases:

- `observe.raw`: screen metrics, focused window, windows, z-order, probe regions, probe decision, probe samples, probe raw nodes, tree decision, UI Automation tree windows, tree samples, tree raw nodes, and timing. Raw UI text is preserved as `raw_value` when the rendered value is filtered for role context.
- `observe.filtered`: merged nodes, classified nodes, and the selector book.
- `observe.rendered`: exact rendered `content_hash`, normalized `semantic_hash`, semantic text, focused title, window titles, rendered screen text.

These phases are intentionally verbose because the organism must be able to diagnose bad UI filtering, mapping, and element selection from its own runtime logs.

The observer is probe-first. It runs the mouse hover probe as the primary source of visible UI evidence, then runs UI Automation tree walk only when the probe produces too few actionable elements. This keeps webpage and canvas-like visible text discoverable while avoiding routine tree-walk cost when the probe already provides usable context.

`observe.raw.data.timing` records per-phase wall and process CPU milliseconds for setup, window enumeration, z-order, probe, tree walk, merge/classify, and render/hash. Direct desktop timing on June 7, 2026 measured the old full observe path around 11-13 seconds. After the probe-first conditional tree policy, the same focused Chrome desktop measured 1.376-1.574 seconds when the probe produced actionable context. A later focused Program Manager measurement showed the 70px, 3ms probe profile took 3.92 seconds; tuning the probe to 90px and 1ms measured 1.741-2.026 seconds while preserving 36 book entries and 17-18 actionable probe elements. When Program Manager is the focused desktop but real app windows are visible above it, the observer now probes the top visible non-desktop window instead of the whole desktop; a forced Program Manager validation selected the YouTube Chrome region and measured 1.05 seconds with 15 book entries and 13 actionable elements. When the probe is empty on a non-desktop target, UIA tree walk is narrowed to the target window plus Taskbar instead of spending time on non-rendered windows; a focused YouTube Chrome empty-probe validation measured 1.389-1.766 seconds with 530 tree nodes and 126 book entries. Desktop and popup regions still keep the all-window tree path.

Stagnation uses the semantic hash. Exact rendered text is still logged, but volatile numbers such as clocks, throughput, percentages, and other changing metrics are normalized before the semantic signature is computed. Tested on the same focused Task Manager window, exact content hashes changed across one-second observations while the semantic hash stayed stable.

## Runtime Artifacts

Large runtime values are stored as content-addressed `.txt` artifact chunks under `runtime_artifacts/`. JSONL events keep bounded `artifact_ref` objects containing kind, SHA-256, character count, line count, and the chunk file list. This keeps logs and blackboard events bounded without truncating data. Reconstructing the referenced chunks must hash to the recorded SHA-256.

## Context Projection

`CONTEXT_POLICY` in `config.py` controls which fields each role receives.

Full action observations are preserved in `action.result` events. Blackboard history stores compact evidence:

```text
chars=<count>; lines=<count>; sha256=<hash>; evidence_lines=<first lines>
```

This prevents large file contents from being repeated through `LAST_RESULT`, `RECENT_HISTORY`, and `FULL_HISTORY`, while preserving full data in the event stream.

## Role Used-Field Telemetry

When a role returns `used_fields`, `orchestrator._log_used_fields()` logs:

- raw `used_fields`
- `accepted_fields`
- `unknown_fields`
- `missing_policy_fields`
- `policy_fields`

This does not assume the model uses valid field names. Invalid declarations are preserved and measured.

Prompt examples use the same field names as `CONTEXT_POLICY`, so `screen_elements`, `full_history`, and `done_claimed` declarations are accepted instead of being recorded as unknown aliases.

## ACP Backend

ACP runs through WSL and `kiro-cli`. Cold WSL startup can exceed short setup windows, so ACP setup timeouts are long enough for a cold start. Setup commands are checked for nonzero exit codes and raise explicit ACP errors instead of silently continuing.

## Explicit Read-File Guard

For goals or instructions that explicitly say to use `read_file` on a path, the orchestrator extracts the requested path and forces the actor instruction:

```text
Use read_file with path exactly: <path>. One action only.
```

If the actor proposes another verb or path for that forced instruction, the orchestrator logs `action.override` and executes the forced `read_file` action. The guard remains active for the whole explicit read-file goal, so retries can repeat the requested file but cannot drift to another path.

## Verifier Consistency

Verifier responses must keep verdict and failure type aligned:

- `verdict="confirmed"` requires `failure_type=null`.
- `verdict="denied"` requires a non-null `failure_type`.

Inconsistent verifier responses are logged as `verifier.inconsistent` and do not complete the goal.

## Command Runner

The `cmd` verb executes Bash through WSL:

```text
wsl.exe bash -lc <command>
```

This keeps command syntax stable for LLM-generated shell actions. The workspace is passed as the Windows current working directory; in the tested environment WSL maps it to `/mnt/c/Users/%USERPROFILE%/Downloads/endgame-ai`.

## Reflection Evolution

Reflection is linearized into three tiers:

- Tier 1 extracts and stores one reusable lesson per reflector call. This runs even when prompt mutation is disabled.
- Tier 2 is opt-in through `--enable-prompt-mutations`. Python waits for enough unapplied lessons for a role, then replaces exactly one line inside the role prompt's `### MUTABLE_LESSONS_START` / `### MUTABLE_LESSONS_END` block. Text outside that block, including the first sentence that defines the role, is immutable.
- Tier 3 switches the main run to a code-evolution goal only after repeated same-issue lessons and prior prompt mutations indicate prompt-level repair was insufficient. The tier-3 checklist reads `lessons.json` and role prompts first, then decides whether source reading and patches are worth the time, and validates justified changes through a subagent test goal.

The reflector schema intentionally does not include full prompt rewrites, PID tuning, or goal rewrites. Those operations are controlled by deterministic Python rather than by a single model response.

## Child Agents

Parallel child agents and distillation agents are tracked through `AgentHandle`. Distillation spawning is restricted to the main agent so distillation children do not recursively spawn more distillation children. Main process shutdown calls `terminate_running_children()` and logs `child.terminate` when child processes are killed.

## Validation Shape

Run validation in ACP-first order:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "SCIENTIST FINAL ACP PIPELINE VALIDATION: use the read_file verb on README.md. Do not use cmd. Do not use write_file. Do not use spawn_agent. Do not claim done until action.result contains read_file success for path README.md and verifier confirmed verdict has failure_type null." --backend acp *> validation-final-acp.out
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "SCIENTIST FINAL LMSTUDIO COMPARISON VALIDATION: use the read_file verb on README.md. Do not use cmd. Do not use write_file. Do not use spawn_agent. Do not claim done until action.result contains read_file success for path README.md and verifier confirmed verdict has failure_type null." --backend lmstudio *> validation-final-lmstudio.out
```

Expected runtime evidence:

- one or more `read_file` actions on `README.md`
- every `read_file` success path is `README.md`
- no `cmd` action
- no `write_file` action
- no `spawn_agent` action
- full README content in `action.result`
- compact evidence in `blackboard_state.json`
- `blackboard_events.jsonl` line-for-line equal to main log when no child is spawned
- redirected TUI stream equal to the JSONL log after BOM and CR handling
- verifier confirmation has `failure_type=null`
- `role.used_fields` is logged for planner, actor, verifier, and any reflector response that occurs
- `role.used_fields.unknown_fields` is empty for planner, actor, and verifier
- exact `content_hash` may change on dynamic screens while `semantic_hash` remains stable when semantic UI identity is unchanged
- no lingering Python or curl process after exit

Measured post-change validation on June 7, 2026:

- ACP first: exited 0 after 2 iterations, one `read_file` action on `README.md`, no prohibited verbs, no role errors, no lessons pollution, verifier confirmed with `failure_type=null`, blackboard events equaled the main log, redirected TUI equaled the same JSONL.
- LM Studio second: exited 0 after 2 iterations, one `read_file` action on `README.md`, no prohibited verbs, no role errors, no lessons pollution, verifier confirmed with `failure_type=null`, blackboard events equaled the main log, redirected TUI equaled the same JSONL. LM Studio rotated logs across `2026-06-07.4.log` and `2026-06-07.5.log`; combined logs showed 5 received requests, 4 chat completion POSTs, 4 generated predictions, 0 disconnects, and 0 truncation flags.

## Known Platform Quirks

- PowerShell redirection with `*> file.out` can produce UTF-16 text.
- LM Studio server log metadata length can report zero while direct shared-handle reads return content.
- Direct `python.exe -c` may be blocked by local policy even when `python.exe -m compileall` works.
- Use native PowerShell file operations for cleanup on Windows. Avoid shell-mixing for deletes.

## Current Clean Workspace Expectation

After runtime cleanup, the workspace should contain source, prompts, schemas, docs, and `comms/` as a directory, but no `log-*.jsonl`, no `validation-*.out`, no `blackboard_events.jsonl`, no `blackboard_state.json`, no `lessons.json`, no `evolution_ledger.json`, no `screen_snapshot.json`, and no `screen_lock.json`.
