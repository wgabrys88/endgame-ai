# endgame-ai

`endgame-ai` is a Windows 11 desktop automation organism written in pure Python. It observes the visible desktop, projects bounded role-specific context to an LLM backend, executes typed actions, verifies completion from evidence, and records runtime truth into append-only logs and blackboard snapshots.

The system is intentionally provider-agnostic. It can use ACP or LM Studio as the model backend, while the desktop control layer remains local Python and Win32/UI Automation.

## Platform

- Windows 11.
- Python 3.13.
- Zero third-party Python package dependency in the runtime code.
- Raw `ctypes` wrappers for Win32, UI Automation, keyboard, mouse, process, and console behavior.
- Strict Pyright target: `0 errors, 0 warnings, 0 informations`.
- Runtime files are ignored by git.

## Quick Start

Run a goal with ACP:

```powershell
python main.py "use the read_file verb on README.md" --backend acp --tui-mode json
```

Run a goal with LM Studio:

```powershell
python main.py "use the read_file verb on README.md" --backend lmstudio --tui-mode json
```

Resume a saved agent state:

```powershell
python main.py --resume --agent-id main --backend acp
```

Open a visual Windows Terminal session:

```powershell
python main.py "your goal" --backend acp --wt-launch
```

## Goal Wrapping

Human goals are allowed to be vague. `main.py` wraps every supplied goal with an operating envelope before the planner sees it.

The wrapper tells the system to:

- prefer GUI evidence when a human interface is involved;
- use its own verbs and backend tools without waiting for the human to explain mechanics;
- keep a checklist for multi-step work;
- replan when evidence changes, an action repeats, or a route is blocked;
- use child agents only for independent work;
- gather evidence from files, GUI, web/source tools, remote machines, and AI provider interfaces when available and allowed;
- steer other AI or coding providers with concrete subgoals and verify their outputs before trusting them;
- preserve full evidence in logs and use compact role context;
- learn reusable lessons through reflection;
- complete only when verifier evidence proves the human goal.

The raw human goal is still preserved in `original_goal`. Existing guards such as explicit `read_file` path detection use the raw goal so wrapping does not break forced file reads or coordination heuristics. Resumed snapshots are normalized too, so older unwrapped saved goals do not bypass the operating envelope.

## Runtime Pipeline

The main loop is:

1. Observe the desktop.
2. Build role context from `CONTEXT_POLICY`.
3. Ask the planner for mode, next action, checklist changes, or child decomposition.
4. Ask the actor to convert one instruction into typed actions.
5. Execute actions through `actions.py`.
6. Verify completion when done is claimed.
7. Reflect only when control signals justify it.
8. Save blackboard state and append runtime events.

The control laws in `state.py` are Lorenz, PID, and Jacobian. They update stagnation, attractor energy, and replan pressure from action history and screen semantics.

## Roles

Prompts live in `prompts/*.txt`; schemas live in `schemas/*.json`.

- `planner`: decides direct, parallel, or done; maintains checklist; gives one actor instruction.
- `actor`: maps one instruction to 0-3 typed actions.
- `verifier`: confirms or denies done claims from concrete evidence.
- `reflector`: extracts one reusable lesson and optional checklist repair.

Role prompts are short and schema-literal so smaller models can follow them. Each role prompt contains one mutable lesson line between:

```text
### MUTABLE_LESSONS_START
### MUTABLE_LESSONS_END
```

Python may replace exactly one line inside that block when prompt mutation is enabled.

## Reflection Evolution

Reflection is a three-tier pipeline.

Tier 1 stores lessons:

- always enabled;
- one reusable lesson per reflector result;
- persisted by `lessons.py`;
- deduplicated with metadata for role, issue key, source iteration, prompt application, and tier-3 escalation.

Tier 2 mutates prompts:

- disabled by default;
- enabled with `--enable-prompt-mutations`;
- applies only after enough unapplied lessons accumulate for a role;
- changes exactly one line inside the mutable block;
- never rewrites a full prompt.

Tier 3 switches to code evolution:

- triggers only after repeated same-issue lessons and prior prompt mutations show prompt-level repair was insufficient;
- rewrites the run into a code-evolution goal;
- first reads lessons and prompts;
- decides whether source reads and patches are worth time;
- validates justified patches through a focused subagent goal.

## Backends

ACP backend:

- implemented by `acp_client.py` and `llm.py`;
- runs through WSL and `kiro-cli`;
- retries WSL setup commands before surfacing a backend startup failure;
- polls `comms/stop.txt` while waiting for prompts;
- raises explicit ACP errors on setup or request failure.

LM Studio backend:

- expected at `http://localhost:1234`;
- used through the OpenAI-compatible local server API;
- useful as a comparison backend after ACP validation.

## Actions

Actor actions are typed verbs:

- `click`
- `write`
- `press`
- `hotkey`
- `scroll`
- `wait`
- `focus`
- `read_file`
- `write_file`
- `spawn_agent`
- `cmd`

`cmd` runs Bash through WSL:

```text
wsl.exe bash -lc <command>
```

The actor prompt instructs models to use Bash syntax for `cmd` and GUI actions for visible human interfaces.

## Observation

`observer.py` is probe-first.

It:

- enumerates visible windows;
- samples visible UI through hover/probe regions;
- falls back to UI Automation tree walk only when probe evidence is insufficient;
- merges and classifies nodes into a selector book;
- renders compact screen context for roles;
- records raw evidence, filtered counts, semantic text, content hash, semantic hash, and timing.

Exact content hashes can change on dynamic screens. Semantic hashes are used for stagnation so volatile clocks, counters, and similar text do not create false progress.

## Blackboard And Logs

The append-only runtime event stream is the durable truth source.

Generated runtime files:

- `blackboard_events.txt`
- `blackboard_state.json`
- `blackboard_state.lock`
- `log-<agent>-<timestamp>.txt`
- `lessons.json`
- `evolution_ledger.json`
- `runtime_artifacts/`
- `comms/`
- `validation-*`

Large values are externalized into `runtime_artifacts/` as content-addressed `.txt` chunks with SHA-256 metadata. Logs keep bounded `artifact_ref` records instead of duplicating large payloads.

`blackboard_state.json` is a projection. It is useful for resume and inspection, but runtime events and artifact chunks preserve fuller evidence.

## Git Policy

The repository ignores everything by default and explicitly unignores source and handoff files.

Trackable files include:

- root `*.py`;
- `prompts/*.txt`;
- `schemas/*.json`;
- `tests/*.py`;
- `README.md`;
- `AGENTS.md`;
- `CONTRIBUTING.md`;
- `ENDGAME-AI-META-CHECKLIST.md`;
- `LICENSE`;
- `.github/ISSUE_TEMPLATE/*.md`;
- `.gitattributes`;
- `.gitignore`;
- `pyrightconfig.json`.

Runtime reports such as `ENDGAME-AI-WHAT-IS-NOT-NEEDED.json` remain ignored unless the human explicitly asks to track them.

## Validation

Static gates:

```powershell
python -m compileall -q .
python -m pyright
```

Focused unit regressions live under `tests/`. They guard self-evolution invariants, but live ACP validation is the runtime proof path. Do not keep running unit tests if the current session or evidence says they hang.

Live ACP smoke validation:

```powershell
python main.py "ACP WRAPPED GOAL VALIDATION: use the read_file verb on README.md. Do not use cmd. Do not use write_file. Do not use spawn_agent. Claim done only after read_file succeeds for README.md." --backend acp --tui-mode json *> validation-acp.out
```

Expected live evidence:

- process exits `0`;
- at least one `action.result` has `verb=read_file`, `path=README.md`, and `success=true`;
- no `cmd`, `write_file`, or `spawn_agent` action;
- verifier verdict is `confirmed`;
- verifier `failure_type` is `null`;
- no role error, parse failure, refusal, or verifier inconsistency.

## Cleanup

Use PowerShell-native cleanup from the repository root:

```powershell
$root=(Resolve-Path -LiteralPath .).Path
$runtimeNames=@('blackboard_state.json','blackboard_state.lock','blackboard_state.tmp','blackboard_events.txt','blackboard_events.jsonl','evolution_ledger.json','lessons.json')
$targets=@()
$targets += Get-ChildItem -LiteralPath $root -Force -File | Where-Object { $_.Name -like 'log-*' -or $_.Name -like 'validation-*' -or $_.Name -like 'blackboard_state.json.*.tmp' -or $runtimeNames -contains $_.Name }
$targets += Get-ChildItem -LiteralPath $root -Force -Directory | Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq 'runtime_artifacts' }
$testsCache=Join-Path $root 'tests\__pycache__'
if (Test-Path -LiteralPath $testsCache) { $targets += Get-Item -LiteralPath $testsCache }
$commsPath=Join-Path $root 'comms'
$commsTargets=@()
if (Test-Path -LiteralPath $commsPath) { $commsTargets += Get-ChildItem -LiteralPath $commsPath -Force -ErrorAction SilentlyContinue }
foreach ($item in $targets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
foreach ($item in $commsTargets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
```

Do not delete source, prompts, schemas, docs, tests, or `.git`.

## File Map

- `acp_client.py`: ACP JSON-RPC client over WSL.
- `actions.py`: typed verb execution.
- `artifacts.py`: externalized runtime artifact chunks.
- `config.py`: constants and context policy.
- `dispatch.py`: prompt/schema loading and JSON extraction.
- `event_schema.py`: blackboard event records.
- `goal_wrapper.py`: deterministic goal prefix/suffix wrapping.
- `lessons.py`: lesson persistence and metadata.
- `llm.py`: backend selection and request logging.
- `log.py`: runtime log and event append.
- `main.py`: CLI entry point and lifecycle.
- `observer.py`: desktop observation.
- `orchestrator.py`: main control loop.
- `persistence.py`: locked state/event persistence.
- `self_evolution.py`: reflection tiers.
- `sixel.py`: terminal graphics helpers.
- `state.py`: blackboard and control laws.
- `stop_signal.py`: cooperative stop check.
- `tui.py`: live state projection.
- `win32.py`: Win32/UIA primitives.

## Handoff

Read `AGENTS.md` before assigning this repository to any AI coding provider. Read `ENDGAME-AI-META-CHECKLIST.md` for the current improvement backlog and evidence status.
