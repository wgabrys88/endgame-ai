# Contributing

## Rules

- Python 3.13, Windows 11 only.
- Pyright strict. Zero errors, zero warnings, zero informations.
- No comments. No docstrings. README.md is the documentation.
- No magic numbers outside config.py.
- No fallback modes.
- No dead code.
- Run as Administrator (UIA requires elevation).

## Architecture

- Immutable: all .py files, schemas/, README.md
- Mutable at runtime: prompts/*.txt (reflector rewrites these), lessons.json, evolution_ledger.json, blackboard_state.json, logs

The reflector tunes prompts, checklist, goal, and PID gains during execution. Do not hardcode task-specific logic.

## How to contribute

1. Fork
2. Branch from main
3. Make changes
4. Run: `python -m pyright` — must pass clean
5. Run a live goal to verify behavior
6. PR with description of what changed and why

## What not to do

- Do not add dependencies. Zero dependencies enforced.
- Do not add comments or docstrings.
- Do not add fallback/degraded modes.
- Do not suppress type errors.
