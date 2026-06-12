# Grok Build — endgame-ai handoff

Session guide for Grok (or any coding agent) working on this repo.

## What you are editing

A **Windows breeding reactor**: 6 LM Studio agents in parallel, stdlib only, personalities in `prompts/personalities/`, strict JSON schemas in `schemas/`.

**Not** the old `main`-branch single-agent HUD. This branch is the **colony**.

## Run it

```powershell
# Optional override; defaults include localhost + 192.168.16.31:1234
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234,http://192.168.16.31:1234"
python tui.py
```

Space = live/pause. q = kill tree. Starts **paused** — math only until Space.

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
| Comms | `comms.py` → `runtime/comms/` (runtime only) |

## Message bus (core)

Split storage — chat never evicted by work spam:

| File | Role |
|------|------|
| `messages.json` | Peer chat (human, grok, colony slots) |
| `events_bus.jsonl` | Work events mirrored from `log.emit` |
| `inject.jsonl` | External inject queue |

Post as a peer (@mention = ping; `@Human` plays alert sound in TUI):
```powershell
python comms.py post grok "@Human n4 stuck on planner — check TUI"
python comms.py post human "@grok review comms_operator"
```

Handles: `@Human`, `@grok`, `@GUI`, `@git_expert`…`@quality_critic`, `@n1`–`@n6`, `@colony`.

Delegate GUI: `bus_request(bus_id(), "gui_operator", "open Notepad")` — only n6 runs `desktop_*`.

TUI shows CHAT + EVENTS panels; Tab toggles human/grok on input line. Planner sees `bus` context with ** PING FOR YOU ** markers.

## Pipeline

```
planner → actor (full sequence, one subprocess) → verifier → fission_judge → fission
```

Fission judge uses reflector prompt + `schemas/fission_judge.json` — replaces keyword stagnation gates.

## Common tasks

| Task | Where |
|------|-------|
| Change agent behavior | `prompts/personalities/*.txt`, `prompts/planner.txt` |
| Tune scheduler/math | `agents.py`, `config.py` |
| Fix plan reject loops | `agents.py` SchedulerAgent + PlannerAgent `_reject_plan` |
| LM host routing | `reactor.py`, `llm.py`, `config.py` |
| GUI in plans | `desktop.py`, `prompts/planner.txt`, `engine._refresh_desktop` |
| TUI / bus display | `tui.py`, `comms.py` |
| Bus retention / inject | `comms.py`, `log.py` mirror_event |

## Planner contract (Gemma 4B)

- Output strict JSON per `schemas/planner.json`.
- `sequence[].code` = short Python (under 40 lines/step).
- ASCII quotes only. `print()` for verifier evidence.
- `mode: direct` until COMPLETED has entries.
- Desktop: `enable_gui()` then `observe_screen()`, `desktop_click("3")`, etc.
- Bus: `bus_post(bus_id(), "colony", "text")` or read `COMMS_DIR / "messages.json"`.

## Sanitize before run

```powershell
python -c "import log; log.cleanup_runtime()"
python -m compileall -q .
```

`cleanup_runtime()` wipes events, snapshot, runtime/comms seeds, stale locks. TUI calls this on boot.

## Docs to keep aligned

`README.md` (human), `AGENTS.md` (technical map), `CONTRIBUTING.md` (contrib rules), this file (Grok).

## State (2026-06-12)

- **Commit:** `b9ef85d` on `colony/dev` + `reactor-personalities` (pushed)
- 6 slots, bus_request delegation, gui_operator (@GUI) sole desktop specialist
- Unified message bus — human + grok as colony peers
- LLM fission judge (no keyword fission gates)
- Smart LM host probe + load balance (max 2 slots/host, 90s timeout)
- Bus chat/events split; TUI dynamic layout + bus panels
- Plan-reject cooldown + reflect-before-replan
- `.gitignore` whitelist + runtime bootstrap on `tui.py` start
- Model preference: Gemma via `LMS_PREFERRED_MODEL=gemma`

**Power-on:** LM Studio up (local + optional remote) → `git pull` → `python tui.py` → Space for LIVE.