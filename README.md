# endgame-ai

A self-sustaining Windows desktop automation reactor. Python 3.13, zero pip dependencies, raw ctypes Win32/UIA.

The system plans, acts, verifies, reflects, and can edit its own prompts and Python — grounded in runtime logs and lessons.

**Active branch:** `refactor-v4` · **`main` is frozen**

---

## What it does

| Layer | Role |
|-------|------|
| **Math thread** (3s) | `stagnation → lorenz → pid` — drives energy, wing-cross, reflect triggers |
| **Scheduler** | Picks next agent from board state |
| **Planner** | Writes plan steps + `done_when` |
| **Actor** | GUI verbs only (`click`, `write`, `press`, …) when `gui_mode` exists |
| **Verifier** | Confirms milestone → fission |
| **Reflector** | Mutates prompt files from stagnation/failure |
| **Observer** | Hover-probe + UIA tree → depth-indented SCREEN |

Headless steps (`read_file`, `write_file`, `cmd`, `wait`) execute in Python without the actor LLM.

---

## Architecture

```
MATH (daemon, 3s):   stagnation → lorenz → pid  →  snapshot.json
                              ↓
MAIN LOOP:   scheduler → planner → actor → verifier → fission
                              ↓         ↓
                         reflector   observer (gui_mode only)

EVENT BUS:   everything → log.emit()  (pause = null sink)
```

**Unified reactor loop** (`engine.py`):

- Scheduler returns `next` agent; engine runs the chain until `halt`, `done`, or unknown.
- Any step failure → mark failed → replan (never retry identical headless step).
- `wing_cross` resets math state only — plan and `done_when` stay.
- Reflector mutates prompts only — never clears plan.
- Goal changes via `goal.txt` clear plan and `done_when` each cycle.

**Power:** verified completions ÷ elapsed seconds. Fission only on verifier truth.

---

## Observer

Screen scan is **hover-probe first, tree second** — mandatory for browsers and modern UI where elements appear only on hover.

1. Sine-grid hover over focused window (`element_from_point`)
2. UIA tree walk for depth and gaps
3. Merge (probe wins), classify, render depth-indented SCREEN with `[id]` actionable elements

Create `gui_mode` (empty file) in repo root to enable GUI path. Remove it for headless-only runs.

---

## TUI

```powershell
python tui.py
python tui.py "initial goal" --backend acp --event-budget 200
```

**Layout:** left column (~25% width, full height) — goal, metrics, vertical flow chains, plan, goal input. Right column — full event stream with wrapped text.

| Key | Action |
|-----|--------|
| **Enter** | Focus goal input; submit sends goal and launches reactor if idle |
| **Space** | Toggle pause (events sink to null via `log.emit`) |
| **Esc** | Cancel goal input |
| **q** | Quit TUI |

**Runtime goal:** typed goal writes `goal.txt`. Engine polls each cycle and hot-swaps goal (stateless LLM calls make this natural).

**Pause:** `pause` file exists → `log.emit` writes nothing and does not consume work budget. In-flight agent chain finishes; new cycles block until unpaused. Math thread still updates `snapshot.json`.

TUI follows the live log via `log.active_events_path()` (handles stale `.endgame.lock` and `events-{pid}.jsonl` fallbacks).

---

## Direct run (no TUI)

```powershell
python main.py "your goal" --backend acp --event-budget 100
python main.py "your goal" --backend lmstudio --event-budget 50
python debug_context.py planner --goal "your goal"
```

**Requirements:** Windows 10/11, Python 3.13, LM Studio (`localhost:1234`) or ACP (Kiro CLI).

---

## Core files

```
main.py           Entry — board init, goal.txt seed, respawn.json
engine.py         Math thread + main loop + fission + goal poll
agents.py         All agents, scheduler, context rendering
actions.py        Headless + GUI verb execution, import gate on .py writes
observer.py       Hover probe + tree walk + SCREEN render
log.py            Event bus, pause, lock, active_events_path()
tui.py            Live dashboard + goal input
config.py         Paths and constants
win32.py          ctypes Win32 + UIA
llm.py            LM Studio / ACP backend
acp_client.py     Kiro ACP protocol
debug_context.py  Dump LLM context to _debug_context_dump.txt
prompts/          Agent prompts (self-evolved)
schemas/          JSON output schemas
```

~3 000 LOC core · 12 `.py` modules · 4 prompts · 4 schemas

---

## Runtime files (gitignored)

| File | Purpose |
|------|---------|
| `events.jsonl` | Primary event log (lock holder) |
| `events-{pid}.jsonl` | Fallback when lock contested |
| `.endgame.lock` | Single-writer PID lock (auto-cleaned if stale) |
| `snapshot.json` | Live board snapshot for TUI |
| `goal.txt` | Runtime goal — engine polls each cycle |
| `pause` | Pause flag — `log.emit` null sink |
| `gui_mode` | Enables observer + GUI actor path |
| `lessons.txt` | Reflector lessons (append) |
| `respawn.json` | Inherited by child `main.py` spawns |
| `disabled.json` | Legacy/runtime toggle |

---

## Safety gates

| Gate | Behavior |
|------|----------|
| **Import gate** | `write_file` on `.py` → `py_compile` + core import check |
| **Post-fission halt** | Planner `mode:done` with completions → `halt` |
| **Respawn contract** | `respawn.json` written at start for child spawns |
| **Log lock** | One primary writer; stale lock removed via `GetExitCodeProcess` |
| **Headless no-retry** | Failed headless step → replan, not identical retry |
| **Verifier** | Blocks trivial/read-only milestones on self-evolution goals |

**Not built:** resurrection (detach → kill self → relaunch new code).

---

## Proven locally (2026-06-10)

| Capability | Evidence |
|------------|----------|
| Headless reactor | `cmd` / `read_file` / `write_file` fission runs |
| Prompt self-evolution | Reflector rewrote all 4 prompts from logs — 2 fissions, 75 work events |
| Code self-evolution | Agent edited `.py` — import gate caught breaks; manual repair needed |
| Child spawn | Actor spawned `main.py` child — died on wrong backend |
| GUI + observer | `gui_mode` + hover probe + depth tree in production path |
| Runtime goal + pause | `goal.txt` hot-swap, Space pause via `log.emit` |

**Milestone 3** (autonomous prompt evolution): achieved.

**Milestone 4** (safe code evolution + spawn + resurrect): partial — spawn real, resurrection and clean rebirth not done.

---

## Configuration

Defaults in `config.py`:

- `EVENT_BUDGET = 20` (work events; math phases free)
- `MAX_HISTORY = 100`
- `MATH_INTERVAL = 3.0`
- `PROBE_STEP_PX = 90`

Override budget: `--event-budget N` on `main.py` or `tui.py`.