# endgame-ai

A self-sustaining Windows desktop automation reactor. Python 3.13, zero pip dependencies, raw ctypes Win32.

The system plans, acts, verifies, reflects, and **edits itself** — prompts and code — grounded in its own runtime logs.

**Branch:** `refactor-v4` on GitHub. `main` is frozen.

---

## What actually works (proven 2026-06-10)

| Run | Events | Result |
|-----|--------|--------|
| Goal mode (write file) | 28 | Fission, exit 0, headless |
| Prompt self-evolution | 75 work | Read logs → rewrote all 4 prompts → 2 fissions, zero `.py` touched |
| Code self-evolution | 228 work | Read source → `reduce.py` → broke config → human repair |
| Spawn + patch run | 113 work | Read logs → patched `config.py` → **spawned child `main.py`** → died on wrong backend |

**Milestone 3 (prompt self-evolution):** achieved.

**Milestone 4 (code self-evolution + spawn + resurrect):** ~60%. Spawn is real. Clean death/rebirth and verifier confirmation are not.

---

## Architecture

```
MATH (3s thread):  stagnation → lorenz → pid
                          ↓
SCHEDULER → planner → actor → verifier → fission
                ↓         ↓
            reflector   observer (gui_mode only)
```

- **Headless-first:** `cmd`, `read_file`, `write_file`, `wait` run via Python without LLM.
- **GUI:** actor resolves element IDs from screen when `gui_mode` file exists.
- **Power:** verified completions / elapsed seconds. Only truth counts.
- **Fission:** verifier-confirmed milestone. Chain reaction or stop.

---

## Files

```
main.py           Entry point
engine.py         Reactor loop + math thread + fission
agents.py         All agents + scheduler + context rendering
actions.py        Verb execution (headless steps)
config.py         Runtime constants (slim — GUI constants live in win32.py)
win32.py          ctypes Win32 + UIA constants
observer.py       Screen scanner
llm.py            ACP / LM Studio backend
log.py            Event logger (math phases free)
tui.py            Live flow dashboard (MATH / LOOP / SIDE)
acp_client.py     Kiro CLI ACP protocol
debug_context.py  LLM context dump tool
prompts/          Agent souls (self-evolved)
schemas/          JSON output schemas
```

Runtime (gitignored, created on run): `events.jsonl`, `snapshot.json`, `lessons.txt`, `gui_mode`

---

## Usage

```powershell
python main.py "your goal" --backend acp --event-budget 100
python tui.py "your goal" --backend acp --event-budget 100   # press Space to start
python debug_context.py planner --goal "your goal"
```

Requirements: Windows 11, Python 3.13, ACP or LM Studio backend.

---

## Maturity gates (landed 2026-06-10)

| Gate | Behavior |
|------|----------|
| **Post-fission halt** | Planner `mode:done` with completions → `halt` → `goal_satisfied` |
| **Import gate** | `write_file` on `.py` → `py_compile` + core import check |
| **Respawn contract** | `respawn.json` inherited by bare `main.py` spawns |
| **Single-writer logs** | `.endgame.lock` — twin writes `events-{pid}.jsonl` |
| **Unified loop** | Failure → replan; wing_cross keeps plan; headless steps never retry |

**Still open:** resurrection (detach → kill self → relaunch new code).

---

## Handover prompt (next session)

Repo path: `%USERPROFILE%\Downloads\endgame-ai`. Press Space in TUI to start.

```powershell
cd $env:USERPROFILE\Downloads\endgame-ai
python .\tui.py 'You are endgame-ai. Project root is the directory containing main.py — stay inside it. Read README.md, events.jsonl, and lessons.txt. Prove M4: edit one .py file safely (import gate must pass), spawn a child with inherited backend, watch its log, finish working without idle loops after fission.' --backend acp --event-budget 200
```

---

## Today

The shit is real. The organism read its logs, patched its config, spawned a copy of itself, and learned from failure. Not Milestone 4 — but the closest yet.