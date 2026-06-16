# Phase 0 Ablation

Phase 0 measures whether the colony earns its keep before mutator or bus rewrites. Real runs use exactly `--timeout 1200`; shorter runs are smoke tests only and do not count as Phase 0 evidence.

## Current Status

- Three proper 1200-second unicore calc/notepad runs have been recorded under `ablation_runs/`.
- The old 45-second runs and any 120-second examples are obsolete.
- The first 1200-second reruns exposed harness defects before they proved task success: placeholder path drift, weak verifier/fission evidence, and avoidable Python subprocess mistakes.
- The third 1200-second run confirmed the stricter file/Desktop fission gate works, but exposed a mutator-scope defect: task pressure rewrote core instrumentation plugins (`comms_beacon.py`, `fission_log.py`) instead of task-local behavior.
- Testing is paused until the pre-run gates below pass, then resumes with exactly `--timeout 1200`.

## Pre-Run Gates

Before starting another real ablation run:

1. Confirm the full task text reaches the LLM request. For long tasks, check LM Studio traces/logs for the complete `ACTIVE_TASK`, not just the first clause.
2. Confirm path context is real: prompts must use `WORKSPACE_DIR`, `USER_HOME`, `DESKTOP_DIR`, or `ENDGAME_*` constants, not placeholder username paths.
3. Confirm file/Desktop fission requires external evidence: actual resolved path, `exists=True`, and readback/content or metadata.
4. Confirm Python subprocess guidance is valid on Windows: do not use bare `subprocess.run(["start", ...])`, do not import `pyperclip`, and use raw strings/`Path` for Windows paths.
5. Confirm Phase 0 measurement does not rewrite whole personality prompts: `patch_prompt` remains disabled unless explicitly re-enabled after the mutator split.
6. Confirm Phase 0 task mutation cannot rewrite core instrumentation/control plugins. `comms_beacon.py` and `fission_log.py` are measurement/control surfaces, not task scratchpads.
7. Commit and push all fixes before running the next 1200-second test.

## Run Modes

Colony keeps the current five-slot behavior:

```powershell
python tui.py "goal text" --mode colony --model-profile nemotron_parallel
python reactor.py --mode colony --goal "goal text" --model-profile nemotron_parallel
```

Unicore runs one rod with the documented baseline persona:

```powershell
python tui.py "goal text" --mode unicore --model-profile nemotron --unicore-persona generalist
python reactor.py --mode unicore --goal "goal text" --model-profile nemotron --unicore-persona generalist
python main.py "goal text" --model-profile nemotron --persona generalist --slot 1
```

The default TUI mode remains `colony` to preserve current behavior. Explicit `--mode unicore` is the Phase 0 baseline path.

## Single-Rod Baseline

The primary unicore baseline persona is `prompts/personalities/generalist.txt`.

It is intentionally a do-everything rod: planner, actor, verifier, browser operator, filesystem worker, repo worker, and external-AI coordinator in one process. It does not delegate to sibling rods.

For a stronger baseline comparison, Phase 0 can also run:

```powershell
python main.py "goal text" --model-profile nemotron --persona implementor --slot 1
python main.py "goal text" --model-profile nemotron
```

Those cover the existing execution-heavy persona and the current no-persona fallback.

## Accepted Owner Task List

These are the owner-provided real-machine tasks for Phase 0:

1. open calculator, add two numbers, and get the result copied from the calculator into the notepad, save file on desktop.
2. open chrome and play on youtube shakira waka waka
3. open chrome and use grok.com ai to provide to him the single source code file of the endgame-ai workspace and asking what endgame is why it is asking and asking for code review, then when the grok instructions are provided, the endgame-ai system must validate if they can be implemented and the implementation must happen and then system must find a way, to validate the changes, that the entire system will benefit from them, this actually must be explained via multiturn conversation with grok, so endgame-ai asks grok for review of file and then follows the grok suggestion and asks grok if needed for clarifications and treat grok as an persona that the endgame-ai system must be aware of , its a large remote ai model that can act as part of the system on demand of the system, the realization of that by the endgame-ai itself will be a succes
4. post on x.com and linkedin.com usin chrome an updates about endgame-ai evolution process and self maintenance on behalf of owners account

The same fixtures are available from:

```powershell
python ablation.py list-tasks
```

Run a fixture by task id:

```powershell
python tui.py --mode unicore --ablation-task-id phase0_calc_notepad
python tui.py --mode colony --ablation-task-id phase0_calc_notepad
```

Run a finite ablation without the TUI:

```powershell
python ablation.py run --mode unicore --task-id phase0_calc_notepad --timeout 1200
python ablation.py run --mode colony --task-id phase0_calc_notepad --timeout 1200
```

Run repeated finite ablations:

```powershell
python ablation.py run --mode unicore --task-id phase0_calc_notepad --timeout 1200 --repeat 8 --batch-id phase0-calc-unicore
python ablation.py run --mode colony --task-id phase0_calc_notepad --timeout 1200 --repeat 8 --batch-id phase0-calc-colony
```

Do not use `--repeat` blindly after a new failure mode appears. Inspect each new 1200-second run, compare the LM Studio request/response log with exported `ablation_runs/<batch_id>/`, and continue only if the failure is not a harness defect.

The finite runner:

- starts `reactor.py` with the selected mode and task fixture
- stops the process tree after `--timeout`; real Phase 0 ablation tests use exactly `1200` seconds
- preserves runtime summaries under `runtime/ablation/`
- exports committed records under `ablation_runs/<batch_id>/`
- records stdout, stderr, copied session event logs, summary metrics, git state before/after, and evaluator verdict metadata

AI coding tools can record their verdict with:

```powershell
python ablation.py run --mode unicore --task-id phase0_calc_notepad --timeout 1200 --evaluator codex --verdict unreviewed --note "Codex will inspect the run record after completion"
```

Run all four accepted task fixtures with the same timeout:

```powershell
python ablation.py run --mode unicore --task-id phase0_calc_notepad --timeout 1200 --batch-id phase0-calc-unicore-1200
python ablation.py run --mode unicore --task-id phase0_youtube_waka_waka --timeout 1200 --batch-id phase0-youtube-unicore-1200
python ablation.py run --mode unicore --task-id phase0_grok_code_review --timeout 1200 --batch-id phase0-grok-unicore-1200
python ablation.py run --mode unicore --task-id phase0_social_updates --timeout 1200 --batch-id phase0-social-unicore-1200
python ablation.py run --mode colony --task-id phase0_calc_notepad --timeout 1200 --batch-id phase0-calc-colony-1200
python ablation.py run --mode colony --task-id phase0_youtube_waka_waka --timeout 1200 --batch-id phase0-youtube-colony-1200
python ablation.py run --mode colony --task-id phase0_grok_code_review --timeout 1200 --batch-id phase0-grok-colony-1200
python ablation.py run --mode colony --task-id phase0_social_updates --timeout 1200 --batch-id phase0-social-colony-1200
```

## Metrics

Every reactor run writes a manifest and rolling summary under `runtime/ablation/<run_id>/`.

The summary includes all core metric fields from the README:

- task success rate
- first-pass success
- external verifier agreement
- median and p95 latency
- tokens per solved task
- bus overhead ratio
- solution diversity
- mutation uplift
- regression rate
- crash recovery rate

Some fields remain `null` until the run has enough evidence or an external/human verdict. That is intentional: Phase 0 logging records missing evidence instead of pretending it exists.

Summarize the latest session manually:

```powershell
python ablation.py summarize --session latest
```

Watch a human-driven TUI run from a second terminal:

```powershell
python ablation.py summarize --session latest --watch --interval 5
```

The summary now includes diagnostics for local runtime failures and prompt/log propagation:

- actor failures such as `unknown key`, Python subprocess timeout, missing window, syntax/path errors, and plugin runtime errors
- whether execution continued after a failed actor step before verifier saw the failure
- trace-level `ACTIVE_TASK` lengths and stale prompt patterns such as placeholder paths or `pyperclip`
- LM Studio control-log events inside the session time window, including expected timeout cancellations or real backend errors
