# Grok Build — endgame-ai handoff

## What you are editing

A **Windows breeding reactor**: 6 LM Studio agents in parallel, stdlib only, personalities in `prompts/personalities/`, strict JSON schemas in `schemas/`.

## Run it

```powershell
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234"
python tui.py
```

Space = live/pause. q = kill tree.

## Architecture

| Layer | Files |
|-------|-------|
| Entry | `tui.py`, `reactor.py`, `main.py` |
| Loop | `engine.py`, `agents.py` |
| Execute | `actions.run_python`, `desktop.py`, `colony_env.py` |
| LLM | `llm.py`, `prompts/*.txt`, `schemas/*.json` |
| Comms | `comms.py` → `runtime/comms/` |

## Message bus

```powershell
python comms.py post grok "@Human n4 stuck"
python comms.py post human "@grok proceed"
```

## Pipeline

```
planner → actor (full sequence subprocess) → verifier → fission_judge → fission
```

## Common tasks

| Task | Where |
|------|-------|
| Change behavior | `prompts/personalities/*.txt`, `prompts/planner.txt` |
| Tune scheduler | `agents.py`, `config.py` |
| LM host routing | `reactor.py`, `llm.py`, `config.py` |
| TUI / bus | `tui.py`, `comms.py` |

## Rules

- Stdlib + ctypes only
- Never commit `runtime/`, `events*.jsonl`, `snapshot.json`
- Personality IS the goal
