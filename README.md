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

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "your goal" --backend lmstudio
```

The ACP backend remains present:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "your goal" --backend acp
```

For this workspace, validation has been performed with LM Studio mode. LM Studio is expected at:

```text
http://localhost:1234
```

LM Studio server logs are outside the workspace at:

```text
C:\Users\%USERPROFILE%\.lmstudio\server-logs\2026-06\
```

Windows may report that server log as zero length while readable content is still available through a shared read handle. Do not trust metadata length alone.

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

If an isolated LM Studio validation is needed, truncate the active server log with a shared handle:

```powershell
$p='C:\Users\%USERPROFILE%\.lmstudio\server-logs\2026-06\'
$fs=[System.IO.File]::Open($p,[System.IO.FileMode]::OpenOrCreate,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::ReadWrite)
try { $fs.SetLength(0) } finally { $fs.Close() }
```

## File Map

- `main.py`: CLI entry point, backend selection, log lifecycle, snapshot save, evolution ledger append, child termination on exit.
- `orchestrator.py`: control loop, observe/plan/act/verify/reflect phases, child spawning, distillation spawning, explicit `read_file` path guard, role used-field telemetry.
- `state.py`: blackboard state, context projection, compact action evidence, PID/Lorenz/Jacobian state, child process termination hook.
- `log.py`: JSONL log writer, sequence numbers, TUI hook isolation, append to blackboard event stream.
- `persistence.py`: locked JSON persistence, per-agent snapshots, append-only blackboard events, inbox and child event mechanics.
- `observer.py`: desktop observation, foreground/window enumeration, probe sampling, UI Automation tree sampling, node merge/classification, rendered screen context.
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

- `observe.raw`: screen metrics, focused window, windows, z-order, probe regions, probe samples, probe raw nodes, UI Automation tree samples, tree raw nodes.
- `observe.filtered`: merged nodes, classified nodes, and the selector book.
- `observe.rendered`: content hash, focused title, window titles, rendered screen text.

These phases are intentionally verbose because the organism must be able to diagnose bad UI filtering, mapping, and element selection from its own runtime logs.

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

## Prompt Mutation

Prompts are runtime-mutable by the reflector. Prompt rewrites are accepted only after length, poison-string, and role-shape checks. Actor, planner, and verifier rewrites must preserve their JSON skeleton and `used_fields` telemetry contract. The rewrite mechanism remains auditable through `prompt.rewrite` and `prompt.rewrite.rejected` events.

## Child Agents

Parallel child agents and distillation agents are tracked through `AgentHandle`. Distillation spawning is restricted to the main agent so distillation children do not recursively spawn more distillation children. Main process shutdown calls `terminate_running_children()` and logs `child.terminate` when child processes are killed.

## Validation Shape

A compact validation goal used during this logging rewrite was:

```powershell
& "C:\Users\%USERPROFILE%\AppData\Local\Python\bin\python.exe" main.py "SCIENTIST FINAL PIPELINE VALIDATION: use the read_file verb on README.md. Do not use cmd. Do not use write_file. Do not use spawn_agent. Do not claim done until action.result contains read_file success for path README.md and verifier confirmed verdict has failure_type null." --backend lmstudio *> validation-final-pipeline.out
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
- no lingering Python or curl process after exit

## Known Platform Quirks

- PowerShell redirection with `*> file.out` can produce UTF-16 text.
- LM Studio server log metadata length can report zero while direct shared-handle reads return content.
- Direct `python.exe -c` may be blocked by local policy even when `python.exe -m compileall` works.
- Use native PowerShell file operations for cleanup on Windows. Avoid shell-mixing for deletes.

## Current Clean Workspace Expectation

After runtime cleanup, the workspace should contain source, prompts, schemas, docs, and `comms/` as a directory, but no `log-*.jsonl`, no `validation-*.out`, no `blackboard_events.jsonl`, no `blackboard_state.json`, no `lessons.json`, no `evolution_ledger.json`, no `screen_snapshot.json`, and no `screen_lock.json`.
