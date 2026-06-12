# Grok Build — endgame-ai handoff

Session guide for Grok (or any coding agent) working on this repo.

## What you are editing

A **Windows breeding reactor**: 5 LM Studio agents in parallel, stdlib only, personalities in `prompts/personalities/`, strict JSON schemas in `schemas/`.

**Not** the old `main`-branch single-agent HUD. This branch is the **colony**.

## Run it

```powershell
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234"   # add remote if needed
python tui.py
```

Space = live/pause. q = kill tree.

## Branches to push

- `colony/dev` — agent autonomous target
- `reactor-personalities` — keep in sync with colony/dev for human dev

Never commit: `runtime/`, `events*.jsonl`, `snapshot.json`, `pause`, `gui_mode`, `*.lock`, `tmp*.py`, `terminals/`, usernames in paths.

## Architecture cheat sheet

| Layer | Files |
|-------|-------|
| Entry | `tui.py`, `reactor.py`, `main.py` |
| Loop | `engine.py`, `agents.py` |
| Execute | `actions.run_python`, `desktop.py`, `colony_env.py` |
| LLM | `llm.py`, `prompts/*.txt`, `schemas/*.json` |
| Desktop | `observer.py`, `win32.py`, `actions.py` verbs |
| Comms | `runtime/comms/` (runtime only) |

## Common tasks

| Task | Where |
|------|-------|
| Change agent behavior | `prompts/personalities/*.txt`, `prompts/planner.txt` |
| Tune scheduler/math | `agents.py`, `config.py` |
| Fix plan reject loops | `agents.py` SchedulerAgent + PlannerAgent `_reject_plan` |
| LM host routing | `reactor.py`, `llm.py`, `config.py` |
| GUI in plans | `desktop.py`, `prompts/planner.txt`, `engine._refresh_desktop` |
| TUI display | `tui.py` |

## Planner contract (Gemma 4B)

- Output strict JSON per `schemas/planner.json`.
- `sequence[].code` = short Python (under 40 lines/step).
- ASCII quotes only. `print()` for verifier evidence.
- `mode: direct` until COMPLETED has entries.
- Desktop: `enable_gui()` then `observe_screen()`, `desktop_click("3")`, etc.

## Docs to keep aligned

`README.md` (human), `AGENTS.md` (technical map), `CONTRIBUTING.md` (contrib rules), this file (Grok).

## Today's state (2026-06-12)

- 5 slots, plain-Python planner, desktop.py wired
- Smart LM host probe + load balance
- Plan-reject cooldown + reflect-before-replan
- `.gitignore` whitelist + runtime bootstrap on `tui.py` start
- Model preference: Gemma via `LMS_PREFERRED_MODEL=gemma`