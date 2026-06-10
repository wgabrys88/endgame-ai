# endgame-ai

A self-sustaining Windows desktop automation reactor. Python 3.13, zero pip dependencies, raw ctypes Win32/UIA.

The system plans, acts, verifies, reflects, and can edit its own prompts and Python — grounded in runtime logs and lessons.

**Active branch:** `refactor-v4` · **`main` is frozen**

---

## Quick start (breakthrough run)

```powershell
cd $env:USERPROFILE\Downloads\endgame-ai
python tui.py "Your goal here" --backend acp --event-budget 500
```

| Key | Action |
|-----|--------|
| **Enter** | Goal input — submit to hot-swap or launch |
| **Space** | Pause / resume (`log.emit` null sink) |
| **q** | Quit TUI |

Project root is always `BASE_DIR` (directory containing `main.py`). Stay inside it.

**Requirements:** Windows 10/11, Python 3.13, ACP (Kiro CLI) or LM Studio (`localhost:1234`).

---

## What it does

| Layer | Role |
|-------|------|
| **Math thread** (3s) | `stagnation → lorenz` — energy, wing-cross, chaos reflect |
| **Scheduler** | Routes to planner / actor / verifier / reflector |
| **Planner** | Plan steps + `done_when` |
| **Actor** | GUI only when `gui_mode` exists |
| **Verifier** | Confirms milestone → fission |
| **Reflector** | Mutates prompts from stagnation/failure |
| **Observer** | Hover-probe + UIA tree → SCREEN |

**Headless** (no actor LLM): `exec`, `read_file`, `write_file`, `wait`.

**Exec environment** (injected): `BASE_DIR`, `Path`, `os`, `sys`, `json`, `time`, `subprocess`, `spawn_main()`, `enable_gui()`.

---

## Architecture

```
MATH (daemon, 3s):   stagnation → lorenz  →  snapshot.json
                              ↓
MAIN LOOP:   scheduler → planner → actor → verifier → fission
                              ↓         ↓
                         reflector   observer (gui_mode only)

EVENT BUS:   log.emit()  — pause file = null sink
GOAL BUS:    goal.txt polled each cycle
```

- Failure → replan (no identical headless retry).
- `wing_cross` resets math only — plan stays.
- Reflector mutates prompts only — never clears plan.
- Power = verified completions ÷ elapsed seconds.

---

## Headless: exec not cmd

`cmd` is removed. Planner emits Python:

```
exec import pathlib; print(pathlib.Path(BASE_DIR).name)

exec:
import subprocess, os, pathlib
opera = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Programs/Opera/opera.exe"
if opera.exists():
    subprocess.Popen([str(opera), "https://grok.com"])
    print("launched")
wait 5
write_file gui_mode 1
```

Spawn child reactor: `spawn_main(goal="...")` inside exec (uses `respawn.json`).

---

## Observer

Hover-probe **first** (mandatory for browsers/modern UI), tree-walk **second**, merge probe-primary, depth-indented SCREEN with `[id]` actionable elements.

`write_file gui_mode 1` or `enable_gui()` in exec before GUI plan steps.

---

## TUI

Full-width dashboard: goal, metrics, MATH/LOOP/SIDE flow, plan, recent events, goal input.

- Autostart when goal passed on CLI (`--no-autostart` to disable).
- `log.active_events_path()` — follows live log, cleans stale `.endgame.lock`.
- Goal submit unpause + writes `goal.txt`; engine picks up while running.

---

## Direct run

```powershell
cd $env:USERPROFILE\Downloads\endgame-ai
python main.py "your goal" --backend acp --event-budget 200
python debug_context.py planner --goal "your goal"
```

---

## Core files

```
main.py engine.py agents.py actions.py observer.py log.py tui.py
config.py win32.py llm.py acp_client.py debug_context.py
prompts/  schemas/
```

~3 000 LOC · 12 core modules · 4 prompts · 4 schemas

---

## Runtime files (gitignored — created on run)

| File | Purpose |
|------|---------|
| `events.jsonl` | Event log |
| `events-{pid}.jsonl` | Fallback writer |
| `.endgame.lock` | Single-writer lock |
| `snapshot.json` | TUI board snapshot |
| `goal.txt` | Live goal |
| `pause` | Pause flag |
| `gui_mode` | GUI path enabled |
| `lessons.txt` | Reflector memory |
| `respawn.json` | Child spawn contract |

---

## Safety gates

| Gate | Behavior |
|------|----------|
| Import gate | `.py` writes → `py_compile` + core import check |
| Post-fission halt | `mode:done` with completions → halt |
| Log lock | Stale lock cleaned via `GetExitCodeProcess` |
| Verifier | Blocks trivial milestones |

**Not built:** resurrection (kill self → relaunch new code).

---

## Milestones

| # | Status |
|---|--------|
| M3 prompt self-evolution | Achieved |
| M4 code evolution + spawn + resurrect | Partial — exec + spawn_main; no resurrection |

---

## Config defaults

`EVENT_BUDGET=20`, `MAX_HISTORY=100`, `MATH_INTERVAL=3.0`, `EXEC_TIMEOUT=60s`, `PROBE_STEP_PX=90`

Override: `--event-budget N`