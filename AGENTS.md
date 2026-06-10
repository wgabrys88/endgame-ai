AGENTS.md — Session state (2026-06-10)

## Git (push-ready workspace)

| | |
|---|---|
| Branch | `refactor-v4` @ `bdc862e` |
| Ahead of origin | 11 commits |
| `main` | frozen |
| User paths in tracked files | **none** (use `$env:USERPROFILE\Downloads\endgame-ai` in docs) |
| Runtime artifacts | **cleared** — clean tree for breakthrough run |

**Do not push until user approves after their run.**

Recent commits (unpushed):
- `bdc862e` exec replaces cmd — real Python environment
- `0ea78c8` reflect_trigger NameError fix
- `08cb59b` full-width TUI, PID removed, chaos gates
- `e1fc39e` docs rewrite
- `7b2a9b3` stale lock fix
- `7e63699` TUI frozen screen fix
- `6812d39` pause via log.emit
- `7870063` goal.txt runtime input
- `74af47a` hover probe primary
- `faae19e` unified reactor loop
- `e7a45c5` maturity gates

---

## Architecture

```
MATH (3s):     stagnation → lorenz → _save(snapshot)     [PID removed]
MAIN:          scheduler → agent chain until halt/done
EVENT BUS:     log.emit() — pause = null sink
GOAL BUS:      goal.txt polled every cycle (even when paused)
HEADLESS:      exec / read_file / write_file / wait
GUI:           observer + actor (gui_mode required)
```

**Engine:** failure→replan · wing_cross keeps plan · reflector never clears plan · chaos_gate (energy≥2 + failures) + stag_gate → reflector

**Observer:** hover probe mandatory → tree walk → merge → depth SCREEN

**TUI:** full-width panel · autostart on CLI goal · Space pause · Enter goal input · `log.reactor_running()` + `active_events_path()`

**Exec sandbox:** `BASE_DIR`, `subprocess`, `spawn_main()`, `enable_gui()` — no cmd.exe

---

## Breakthrough run

```powershell
cd $env:USERPROFILE\Downloads\endgame-ai
python -c "import observer, engine, agents, actions, log, tui; print('OK')"
python tui.py "YOUR GOAL" --backend acp --event-budget 500
```

Workspace must be clean (no stale `pause`, `.endgame.lock`, old `events.jsonl`).

Suggested goal themes: self-understanding via README+logs, TUI polish, observer tree quality, Grok/Opera comparison before/after metrics.

---

## Runtime files (gitignored)

```
events.jsonl  events-{pid}.jsonl  .endgame.lock  snapshot.json
goal.txt  pause  gui_mode  lessons.txt  respawn.json  disabled.json
_debug_context_dump.txt  agent-tools/  terminals/
```

---

## Milestones

| # | Status |
|---|--------|
| M3 prompt self-evolution | done |
| M4 code evolution + spawn | partial — exec + spawn_main + import gate; no resurrection |

---

## Debug

```powershell
python debug_context.py planner --goal "test"
python debug_context.py actor --goal "test"
```

Requires `gui_mode` for screen in actor context.

---

## Rules for agents

- Never hardcode `ewojgab` or `C:\Users\...` in committed files — use `BASE_DIR` or `%USERPROFILE%` in docs only.
- Do not mass-kill python when user TUI/reactor owns the terminal.
- Do not push without user approval.
- Planner must use `exec` not `cmd`.
- `write_file gui_mode 1` before GUI steps.

---

## Files

12 core `.py` + `debug_context.py` + `acp_client.py` · 4 prompts · 4 schemas · ~3000 LOC