# Contributing

`endgame-ai` is a Windows 11 desktop automation runtime. Contributions should preserve the current control loop: observe, plan, act, verify, reflect, persist evidence.

## Baseline

- Python 3.13.
- Windows 11.
- Runtime code has zero third-party Python dependencies.
- Win32, UI Automation, keyboard, mouse, process, and terminal behavior use local Python wrappers.
- Pyright strict target is `0 errors, 0 warnings, 0 informations`.
- Numeric constants belong in `config.py`.
- Runtime artifacts must stay out of git.

## Runtime Contracts

- Every human goal is wrapped by Python with operating instructions before roles see it.
- The raw human goal is preserved as `original_goal`.
- Resumed snapshots are normalized so legacy unwrapped goals do not bypass the wrapper.
- Prompts must stay short, schema-literal, and understandable by small local models.
- Each prompt has one mutable lesson line between `### MUTABLE_LESSONS_START` and `### MUTABLE_LESSONS_END`.
- The reflector extracts one reusable lesson and optional checklist repair.
- Python owns lesson storage, prompt mutation policy, goal rewrites, and tier-3 code evolution.
- Prompt mutation is opt-in with `--enable-prompt-mutations` and may replace exactly one mutable line.
- The verifier confirms completion only from concrete screen, action, file, command, or child-agent evidence.

## Before Editing

1. Run `git status --short --ignored`.
2. Read the files on the path you intend to change.
3. Treat `README.md`, `AGENTS.md`, and `ENDGAME-AI-META-CHECKLIST.md` as source-level handoff files.
4. Keep ignored runtime evidence such as logs, blackboard files, lessons, ledgers, and `runtime_artifacts/` out of commits.

## Validation

Primary gates:

```powershell
python -m compileall -q .
python -m pyright
```

Use a live ACP goal when runtime behavior is the claim:

```powershell
python main.py "ACP WRAPPED GOAL VALIDATION: use the read_file verb on README.md. Do not use cmd. Do not use write_file. Do not use spawn_agent. Claim done only after read_file succeeds for README.md." --backend acp --tui-mode json
```

Unit tests under `tests/` are focused regressions for self-evolution invariants. Do not use them as a substitute for live ACP validation, and do not keep running them if the current session or evidence says they hang.

## Pull Request Rules

- Explain what changed and what evidence proves it.
- Include static gate output.
- Include ACP runtime evidence when behavior changed.
- Do not add dependencies.
- Do not suppress type errors.
- Do not push runtime artifacts.
