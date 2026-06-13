---
name: endgame-ai
description: Use when editing endgame-ai — the Windows breeding reactor with six LLM agents, message bus, plugin hot-swap, and strict stdlib-only rules. Covers tui.py, reactor.py, engine.py, agents.py, prompts, schemas, plugins, and comms.
---

# endgame-ai Project Skill

## Project identity

`endgame-ai` is a **Windows breeding reactor**: six parallel LM-Studio-powered agents sharing a codebase, a JSON message bus, and the real Windows desktop. Entry point is `python tui.py`.

Key docs (always respect):
- `AGENTS.md` — architecture, branches, process tree, known issues, rules
- `GROK.md` — build handoff, planner contract, bus usage
- `CONTRIBUTING.md` — commit rules, validation, what must stay out of git

## Architecture at a glance

```
tui.py → reactor.py → main.py ×6
  ├── engine.py   scheduler + plugin hot-swap
  ├── agents.py   planner, actor, verifier, fission_judge, reflector, mutator, math
  ├── actions.py  GUI verbs + run_python subprocess runner
  ├── desktop.py  observe_screen, desktop_*
  ├── comms.py    message bus (runtime/comms/)
  ├── llm.py      LM Studio API client
  ├── log.py      JSONL events, cleanup_runtime
  ├── observer.py UIA desktop scan
  └── win32.py    ctypes Windows API
```

## Personality slots

| Slot | Personality | Role |
|------|-------------|------|
| n1 | git_expert | commits/pushes `colony/dev` |
| n2 | implementor | writes `plugins/*.py` |
| n3 | doc_inspector | writes `runtime/comms/report.md` |
| n4 | comms_operator | bus mirror/coordination (NO desktop_*) |
| n5 | quality_critic | py_compile audits |
| n6 | gui_operator | sole desktop hands (`@GUI`) |

## Critical rules

- **Stdlib + ctypes only. No pip.**
- **Never commit runtime artifacts** (`runtime/`, `events*.jsonl`, `snapshot.json`, etc.).
- **Only n6 / gui_operator runs `desktop_*`** helpers; other personalities delegate via `bus_request(..., "gui_operator", ...)`.  
- **Planner outputs strict JSON** per `schemas/planner.json` (or `schemas/planner_gui.json` for n6).  
- **Each plan step is plain Python** in `sequence[].code`; actor runs them in one subprocess via `actions.run_python()`.  
- **GUI plans must start each step with** `book, _, _ = observe_screen(print_screen=False)`.  
- **TUI boot calls `cleanup_runtime()`** — it wipes `runtime/`, logs, snapshot. Pause/quit preserves them; restart does not.  
- **Default branch for human work:** `reactor-personalities`. Agent target: `colony/dev`. `main` is stable single-agent, not active dev.

## Bus usage

- Chat: `runtime/comms/messages.json`
- Work events: `runtime/comms/events_bus.jsonl`
- External inject: `runtime/comms/inject.jsonl`
- Post: `python comms.py post <from> "@target text"`
- Delegate GUI: `bus_request(bus_id(), "gui_operator", "task text")`
- Mention aliases include `@Human`, `@grok`, `@GUI`, `@colony`, `@n1`–`@n6`.

## Before validating work

1. `python -m compileall -q .`
2. If runtime must be fresh: `python -c "import log; log.cleanup_runtime()"`
3. Run TUI: `python tui.py` — starts paused; press Space for live.

## Common edits

| Task | Files |
|------|-------|
| Agent behavior / goals | `prompts/personalities/*.txt`, `prompts/planner.txt` |
| Planner JSON contract / schemas | `schemas/*.json` |
| Scheduler / math / reflect gates | `agents.py`, `config.py` |
| Plugin auto-fix / hot-swap | `plugins/*.py` (must define `run(board)`) |
| GUI automation primitives | `desktop.py`, `actions.py`, `observer.py`, `win32.py` |
| Bus / TUI | `comms.py`, `tui.py` |

## Known post-demo issues to watch

1. Rolling 450-line log cap evicts early session proof.
2. Role leak: n4 once ran `desktop_*`; n6 should be sole GUI hands.
3. Gemma planner emits `NameError: book`, syntax errors, wrong window titles.
4. Verifier too permissive (credited observing TUI/PowerShell).
5. `@mention` requires a trailing space; `@groktext` does not ping.
