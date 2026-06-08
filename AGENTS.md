# AGENTS.md

Provider-agnostic handoff for AI coding agents working on `endgame-ai`.

## Operating Contract

- Work from the current files and git state first. Treat prior chat history as a locator, not proof.
- Do not push to GitHub unless the human explicitly asks.
- Keep changes small enough to audit.
- Windows 11, Python 3.13, zero third-party Python dependencies, raw ctypes.
- Numeric constants belong in `config.py`.
- Runtime data must not be committed.

## Architecture

`endgame-ai` is an event-driven desktop automation organism:

- `main.py`: CLI, backend selection, lifecycle.
- `orchestrator.py`: event scheduler — chooses cheapest useful handler per iteration.
- `state.py`: blackboard state, Lorenz/PID/Jacobian control laws, context builders.
- `config.py`: all constants, schema limits, context policy.
- `observer.py`: probe-first desktop observation via UIA COM.
- `actions.py`: typed verb execution (click, write, hotkey, focus, etc.).
- `dispatch.py`: loads role prompts/schemas, extracts JSON from LLM responses.
- `llm.py` + `acp_client.py`: LM Studio and ACP backends.
- `lessons.py` + `self_evolution.py`: lesson persistence and optional prompt mutation.
- `prompts/*.txt` + `schemas/*.json`: role contracts.

## Event-Driven Scheduler

The orchestrator does NOT run a static pipeline. Each iteration:

1. Check stop signal.
2. Observe desktop.
3. If children are running and parent is coordinating, wait.
4. If actor has an active subtask producing evidence, continue actor (skip planner).
5. If Lorenz wing crosses zero under stagnation, clear instruction to force replan.
6. Otherwise call planner for next decision.
7. Verify only on done claims at the LAST checklist step.
8. Reflect only when PID + failure evidence justify it.

Actor continuation is the key efficiency mechanism: when a multi-step subtask is in progress and the screen is changing, the actor keeps executing without burning a planner LLM call.

Math pipeline:
- Lorenz attractor drives `attractor_energy` — when x crosses zero (wing switch) under stagnation, forces replan.
- PID accumulates only on actual failures (not screen latency), output gates reflection.
- Jacobian weights checklist steps by position × stagnation × energy × failure gain.

## Schemas and Limits

Schema field limits in `schemas/*.json` control response length. Key limits:
- Actor: observe 800 chars, action.value 2000 chars, up to 5 actions per call.
- Planner: next_action 1500 chars, because 800 chars, up to 12 sequence steps.

No `used_fields` in schemas — removed as dead telemetry with no behavioral impact.

## Child Agents

- Planner `parallel` mode spawns children via `orchestrator._spawn_child`.
- Actor `spawn_agent` verb spawns children via `actions.spawn_agent_verb`.
- Both use unique agent_ids, register with persistence, report via child_done/child_failed events.
- Parent claims completion from child results only after verifier confirms.

## Reflection

Single-tier by default:
1. Reflector extracts one reusable lesson from failure/repetition evidence.
2. Lesson is stored in `lessons.json` with metadata.
3. Optional prompt mutation (`--enable-prompt-mutations`) may replace one line in the mutable block.

## Git Policy

```gitignore
*
```

Tracked source must be explicitly unignored. Runtime artifacts (blackboard_state*, log-*, lessons.json, etc.) are always ignored.

## Validation

```powershell
python -m compileall -q .
python -m pyright
```

Live 60-second regression:
```powershell
python main.py "Open Notepad via Win+R, replace all text with exactly: SCIENCE EVENT DRIVEN SAMPLE. Use GUI actions only. Do not use cmd. Claim done only when that exact text is visible in Notepad." --backend acp --tui-mode json
```

## Runtime Cleanup

```powershell
$root=(Resolve-Path .).Path
$runtimeNames=@('blackboard_state.json','blackboard_state.lock','blackboard_state.tmp','blackboard_events.txt','blackboard_events.jsonl','evolution_ledger.json','lessons.json')
$targets=@()
$targets += Get-ChildItem -LiteralPath $root -Force -File | Where-Object { $_.Name -like 'log-*' -or $_.Name -like 'validation-*' -or $runtimeNames -contains $_.Name }
$targets += Get-ChildItem -LiteralPath $root -Force -Directory | Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq 'runtime_artifacts' }
$commsPath=Join-Path $root 'comms'
if (Test-Path $commsPath) { Get-ChildItem $commsPath -Force | Remove-Item -Recurse -Force }
foreach ($item in $targets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
```

## Provider Handoff

For any AI coding agent (Claude Code, Kiro, Codex, Grok, OpenCode):

1. Read this file and `README.md`.
2. Run `git status --short --ignored`.
3. Inspect source files before claiming behavior.
4. Validate with ACP when runtime behavior is the claim.
5. Clean runtime artifacts before committing.
6. Do not push unless explicitly instructed.
