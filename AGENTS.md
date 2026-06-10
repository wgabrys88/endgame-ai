AGENTS.md — Session state (2026-06-10)

## Git

| | |
|---|---|
| Branch | `refactor-v4` @ `7b2a9b3` |
| Ahead of origin | 7 commits (not pushed — needs user approval) |
| `main` | frozen @ `109173b` |

Recent local commits:
- `7b2a9b3` stale lock fix (`GetExitCodeProcess`)
- `7e63699` TUI frozen screen — live events path, drop Win sync output
- `6812d39` pause via `log.emit` null-sink
- `7870063` vertical TUI + `goal.txt` runtime input
- `74af47a` hover probe restored as primary observer scan
- `faae19e` unified reactor loop, slimmer core
- `e7a45c5` maturity gates (halt, import gate, respawn, log lock)

---

## Architecture (current)

```
MATH thread (3s):  stagnation → lorenz  →  _save(snapshot)  (pid removed — chaos)
MAIN loop:         scheduler → agent chain until halt/done/break
EVENT BUS:         log.emit() — single choke point; pause = null
GOAL BUS:          engine._poll_goal() reads goal.txt each cycle
```

**Engine chain** (`engine.py`):
- `_main_loop`: if `log.paused()` → sleep, no new cycles
- `_poll_goal`: goal.txt change → update board, clear plan/done_when, emit `goal_change`
- `_run_agent`: observer first when `_needs_screen()` (gui_mode + non-headless actor step)
- Failure anywhere → `failed` + `next: planner` (no headless retry)
- `wing_cross` → reset math only, keep plan
- Fission → verifier-confirmed milestone → power += 1/elapsed

**Observer** (`observer.py`):
- Always hover-probe focused window first (mandatory — browsers/modern UI)
- Always tree-walk after; `_merge` probe-primary
- Depth-indented SCREEN: context nodes + `[id]` actionable

**TUI** (`tui.py`):
- Left ~25%: goal, status, metrics, vertical MATH/LOOP/SIDE, plan, goal input
- Right ~75%: wrapped event stream
- `log.active_events_path()` — never read stale `events.jsonl` when reactor uses alt file
- Space → `log.set_paused()` · Enter → goal input → `goal.txt` · auto-launch if idle

**Headless** (`actions.py`):
- `cmd` via `cmd.exe /c` utf-8
- `read_file` / `write_file` / `wait` direct execution
- Import gate on `.py` writes

**Prompts** (stripped — behavior in Python):
- `planner.txt` ~34 lines — headless syntax + GUI intentions
- `actor.txt` ~26 lines — GUI only, ID resolution from SCREEN

---

## Runtime files (gitignored)

```
events.jsonl          Primary log (lock holder)
events-{pid}.jsonl    Fallback writer
.endgame.lock         PID lock — clean_stale_lock() on start
snapshot.json         Board snapshot (math + main loop)
goal.txt              Runtime goal — engine polls
pause                 Pause flag — log.emit null sink
gui_mode              Enables observer + GUI actor
lessons.txt           Reflector memory
respawn.json          Child spawn contract
disabled.json         Legacy
_debug_context_dump.txt
agent-tools/  terminals/
```

---

## Milestones

| # | Status | Notes |
|---|--------|-------|
| M3 prompt self-evolution | **done** | 4 prompts rewritten from logs, verified, 2 fissions |
| M4 code evolution + spawn + resurrect | **~60%** | spawn works; resurrection not built; import gate catches bad edits |

**Landed gates:** post-fission halt, import gate, respawn contract, log lock + stale cleanup

**Open:**
- Resurrection (kill self → relaunch new code)
- Push to origin (user approval)
- Long-run stability (planner 90s timeouts on bloated context — use `read_file` not giant cmd)

---

## Proven this branch

- Unified reactor: failure→replan, wing_cross keeps plan, reflector never clears plan
- Prompt soul evolution from runtime evidence (zero `.py` in that run)
- Code edits with import gate (reduce.py broke config — lesson #37)
- Child spawn via actor cmd (backend mismatch killed child)
- Hover probe + tree observer path
- TUI vertical column, goal.txt hot-swap, pause bus
- TUI freeze fix: stale lock + wrong events file + Win SYNC removed

---

## Debug

```powershell
python debug_context.py planner --goal "your goal"
python debug_context.py actor --goal "your goal"
```

Requires `gui_mode` for screen/desktop in context. Writes `_debug_context_dump.txt`.

```powershell
python -c "import observer, engine, agents, actions, log, tui; print('OK')"
```

---

## Files

12 core `.py` + `debug_context.py` + `acp_client.py` · 4 prompts · 4 schemas · ~3000 LOC

Do not push without user approval. Do not mass-kill python when endgame-ai TUI/reactor is the user's terminal session.