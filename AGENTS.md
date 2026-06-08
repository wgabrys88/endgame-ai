# AGENTS.md

Provider-agnostic handoff for AI coding agents working on `endgame-ai`.

## Operating Contract

- Work from the current files and git state first. Treat prior chat history as a locator, not proof.
- Scientist Mode is active: label behavior as `[TESTED]`, `[FILE-EVIDENCE]`, `[INFERENCE]`, or `[UNVERIFIED]` when the distinction matters.
- Do not invent runtime results. If a behavior was not tested in the current session, say so and define the smallest falsification experiment.
- Do not push to GitHub unless the human explicitly asks. Local git branches, staging, commits, and cleanup are expected.
- Keep changes small enough to audit, but do not preserve duplicated or dead architecture just because it is easier.
- This project is Windows 11, Python 3.13, zero third-party Python dependencies, raw `ctypes` for Win32/UI Automation.
- Pyright strict target is `0 errors, 0 warnings, 0 informations`.
- Numeric constants belong in `config.py`.
- Runtime data must not be committed.

## Current Architecture

`endgame-ai` is a desktop automation organism:

- `main.py` owns CLI setup, backend selection, lifecycle logging, snapshot save, and exit code.
- `goal_wrapper.py` owns deterministic goal prefix/suffix wrapping; `state.py`, `main.py`, and `orchestrator.py` normalize goals before resume, save, and run.
- `orchestrator.py` owns the event scheduler, child agents, actor continuation, verifier-gated completion, reflection, and explicit read-file guards.
- `observer.py` reads the Windows desktop through probe-first hover sampling plus conditional UI Automation tree walk.
- `state.py` owns the blackboard state and context projection through `CONTEXT_POLICY`.
- `dispatch.py` loads role prompts/schemas and extracts role JSON.
- `llm.py`, `acp_client.py` provide LM Studio and ACP backends.
- `lessons.py` persists learned lessons and self-evolution metadata.
- `self_evolution.py` owns the linearized reflection self-evolution pipeline.
- `prompts/*.txt` and `schemas/*.json` are role contracts.

## Reflection Pipeline

Current reflection design:

1. Tier 1 stores one reusable lesson from each reflector result.
2. Tier 2 is opt-in with `--enable-prompt-mutations`; default is disabled. Lesson extraction still runs when prompt mutation is disabled.
3. Tier 2 prompt mutation is deterministic Python, not a full LLM rewrite. It may replace exactly one line inside `### MUTABLE_LESSONS_START` / `### MUTABLE_LESSONS_END`.
4. Prompt first lines are immutable by guard because they define who the role is and what job it performs.
5. Tier 3 switches the main run to a code-evolution goal only after repeated same-issue lessons and prior prompt mutations show prompt-level repair was insufficient.
6. Tier 3 must inspect `lessons.json` and role prompts before deciding whether source reads and patches are worth time.
7. Online distillation children are not part of the main task loop; use explicit distillation/evolution goals only when runtime evidence justifies them.

Do not reintroduce reflector fields for full prompt rewrites, PID tuning, or goal rewrite unless there is fresh runtime evidence that deterministic Python cannot own that step.

## Child Agents

- Planner `parallel` mode spawns children through `orchestrator._spawn_child`.
- Actor `spawn_agent` spawns children through `actions.spawn_agent_verb`.
- Both paths must use unique non-main `agent_id` values, register with `persistence.register_agent`, preserve the parent/child event channel, and report completion through `child_done` / `child_failed`.
- A parent may claim completion from child results only after the verifier confirms the child evidence satisfies the original goal.

## Event-Driven Runtime

- Goals that explicitly await a human/user response should idle on unchanged screen evidence instead of spending another planner/actor LLM turn.
- Actor continuation is valid for real subtasks, but primitive actions with unchanged screen semantics must return control to the planner instead of repeating.
- Planner checklists should contain actionable work only. Do not preserve verify/confirm/claim-done steps because verifier owns completion checks.
- Actor `DONE` may trigger verifier directly near the end of actionable work; planner is not required to claim done first.
- The planner should resume once screen evidence changes, a primitive route stalls, or a failure/recovery signal appears.
- Visual TUI should favor live progress and risk signals over static wall-of-text state.

## Git And Ignore Contract

The repository uses a default-ignore policy:

```gitignore
*
```

Tracked source/docs must be explicitly unignored. Current intentionally trackable categories are:

- root Python files
- `prompts/*.txt`
- `schemas/*.json`
- `README.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `ENDGAME-AI-META-CHECKLIST.md`
- `LICENSE`
- `.github/ISSUE_TEMPLATE/*.md`
- `tests/*.py`
- `pyrightconfig.json`
- `.gitattributes`
- `.gitignore`

Ignored runtime/session artifacts include `blackboard_state.json`, `blackboard_events.*`, `lessons.json`, `evolution_ledger.json`, `runtime_artifacts/`, `comms/`, `log-*`, `validation-*`, `__pycache__/`, and copied session reports such as `ENDGAME-AI-WHAT-IS-NOT-NEEDED.json`.

Before committing, run:

```powershell
git status --short --ignored
git check-ignore -v AGENTS.md ENDGAME-AI-META-CHECKLIST.md tests\test_self_evolution.py ENDGAME-AI-WHAT-IS-NOT-NEEDED.json
```

Expected: the docs and tests are not ignored; runtime reports remain ignored.

## Validation

Use ACP for real end-to-end validation when the goal asks to prove the organism works:

```powershell
python main.py "ACP WRAPPED GOAL VALIDATION: use the read_file verb on README.md. Do not use cmd. Do not use write_file. Do not use spawn_agent. Claim done only after read_file succeeds for README.md." --backend acp --tui-mode json
```

Static gates:

```powershell
python -m compileall -q .
python -m pyright
```

Focused deterministic regression tests exist under `tests/`. They guard self-evolution invariants and should be kept in git. Do not substitute unit tests for requested live ACP validation, and stop or skip them when current session evidence says they hang.

## Runtime Cleanup

Use PowerShell-native cleanup from the workspace root:

```powershell
$root=(Resolve-Path .).Path
$runtimeNames=@('blackboard_state.json','blackboard_state.lock','blackboard_state.tmp','blackboard_events.txt','blackboard_events.jsonl','evolution_ledger.json','lessons.json')
$targets=@()
$targets += Get-ChildItem -LiteralPath $root -Force -File | Where-Object { $_.Name -like 'log-*' -or $_.Name -like 'validation-*' -or $_.Name -like 'blackboard_state.json.*.tmp' -or $runtimeNames -contains $_.Name }
$targets += Get-ChildItem -LiteralPath $root -Force -Directory | Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq 'runtime_artifacts' }
$commsPath=Join-Path $root 'comms'
$commsTargets=@()
if (Test-Path -LiteralPath $commsPath) { $commsTargets += Get-ChildItem -LiteralPath $commsPath -Force -ErrorAction SilentlyContinue }
foreach ($item in $targets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
foreach ($item in $commsTargets) { Remove-Item -LiteralPath $item.FullName -Recurse -Force }
```

Do not delete source, prompts, schemas, docs, or `.git`.

## Provider Handoff

For Claude Code, Grok, OpenCode, Codex, or any other coding agent:

1. Read `AGENTS.md`, `README.md`, and `ENDGAME-AI-META-CHECKLIST.md`.
2. Run `git status --short --ignored` and identify ignored runtime files before editing.
3. Inspect the relevant source files before claiming behavior.
4. Make patches with normal file-editing tools; avoid broad rewrites unless the execution path proves they are needed.
5. Validate with ACP when runtime behavior is the claim.
6. Clean runtime artifacts.
7. Commit locally with a concise message.
8. Do not push unless explicitly instructed.

## One-Minute Scientist Prompt

Copy this prompt when handing `endgame-ai` to OpenCode, Kiro CLI, Grok Code, Claude Code, Codex, or another provider:

```text
You are working in the Windows workspace C:\Users\ewojgab\Downloads\endgame-ai.

Scientist Mode is active. Do not trust chat history as proof. Read the current files and git state first. Label claims as [TESTED], [FILE-EVIDENCE], [INFERENCE], or [UNVERIFIED] when it matters.

The current meta-goal is to make endgame-ai behave like an event-driven desktop automation organism, not a hardcoded planner -> actor -> verifier -> reflector pipeline. The scheduler should choose the cheapest useful event handler:
- observe the desktop;
- continue the actor only while a real subtask is producing evidence;
- return to planner when a primitive route stalls, repeats, or misses its expected visible target;
- verify only when planner or actor emits a done claim;
- reflect only on real failure/repetition evidence;
- stop immediately when the backend is unavailable or a human stop signal arrives.

Use one-minute live experiments as the main falsification tool. This matters because a production desktop organism can look plausible in static tests while wasting real time on LLM role order, repeated primitives, transient GUI failures, backend setup loops, reflection, or child/successor spawning. The metric is not "did a unit test pass"; the metric is "how much useful work did the organism complete before the one-minute kill switch?"

Before each live experiment:
1. Clean only ignored runtime artifacts: blackboard_state*, blackboard_events*, log-*, validation-*, lessons.json, evolution_ledger.json, runtime_artifacts/, comms/, __pycache__/. Do not delete source, prompts, schemas, docs, or .git.
2. Start a live ACP run with a concrete desktop task. Prefer tasks that require GUI progress and can be measured from screen/action evidence, for example opening/focusing Notepad and writing exact text. Keep the goal finite and forbid irrelevant routes such as Find or cmd when they are not part of the task.
3. Let it run for 60 seconds of wall time.
4. At 60 seconds write comms/stop.txt, wait briefly, then force-kill only remaining endgame-ai main.py processes if they did not exit.
5. Confirm no endgame-ai main.py, poke-acp, or kiro helper process is left running.

After each live experiment, parse blackboard_events.txt. Measure:
- total events and iterations;
- llm.request count by role;
- action.result count, verbs, targets, success, and observations;
- checklist.created and checklist.advance;
- actor.continue and actor.continue.skip;
- verifier, goal.complete, and run.end;
- backend.unavailable, stop.signal, role_error, parse_fail, reflect.skip, pid.reflect, reflector, child.spawn, successor, and successor.skip.

Treat useful work as concrete state-changing progress: focused/opened a target window, clicked a correct control, typed intended text, read required file content, advanced an actionable checklist step, emitted actor DONE from visible evidence, or received verifier confirmed. Treat waste as repeated primitive actions without target progress, planner-only turns that do not change route, verifier-only checklist steps, reflection during productive progress, backend-unavailable retry loops, successor spawning into the same unavailable backend, or stop signals recorded as role errors.

Patch only what the one-minute evidence proves. Prefer deleting or gating waste over adding more role calls. If a change claims runtime behavior, rerun the one-minute experiment and compare useful work per minute against the prior run. Report both the raw measured counts and the interpretation.

Do not run hanging unit tests. Compile/Pyright are useful static gates, but they do not replace live ACP measurement when the claim is runtime organism behavior. Do not push to GitHub unless the human explicitly asks.
```
