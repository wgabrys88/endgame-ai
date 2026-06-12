# endgame-ai — breeding reactor

**Five AI agents run in parallel on your Windows desktop.** They share one codebase, write plugins, file reports, commit to git, and drive the real UI with mouse and keyboard — while a live spectrogram shows whether the colony is thriving or stuck.

No pip install. No task list. Each agent has a **personality** (git expert, implementor, doc writer, comms operator, quality critic). Identity drives action.

```bash
python tui.py
```

Starts **paused** (math-only). Press **Space** for live LLM work. Press **q** to kill the whole process tree.

Requires [LM Studio](https://lmstudio.ai/) with a loaded model (tested with **Gemma 4B**). Optional second GPU host via env var (see [Configuration](#configuration)).

---

## What this is (simple)

Imagine a small reactor core with five fuel rods. Each rod is an LLM agent loop: **plan → run Python → verify → repeat**. When an agent finishes real work (writes a file, pushes git, clicks a button), that counts as **fission** — progress the colony can measure.

Agents do not wait for instructions. The git expert sees dirty trees and commits. The implementor sees errors and writes plugins. The doc inspector reads logs and writes `runtime/comms/report.md`. They coordinate through a **message bus** — and so can you.

**Human and Grok are colony peers.** Post to the bus from the TUI input line or:

```powershell
python comms.py post human "check git status"
python comms.py post grok "review n4 planner"
```

Chat lives in `runtime/comms/messages.json` (retained). Work events roll in `events_bus.jsonl`. Planners see recent bus context.

You watch everything in one TUI: stagnation, energy, PID control loops, per-agent spectrograms, bus **CHAT** + **EVENTS** panels.

---

## How this branch differs from `main`

| | **`main`** | **`colony/dev`** (this branch) |
|---|------------|--------------------------------|
| **Shape** | One organism, one goal | **5 parallel agents**, 5 personalities |
| **Control** | Single planner/actor loop | **Reactor** spawns and respawns rods; maintains k≈1 |
| **Evolution** | Self-edits core source | Writes **plugins/** + **prompts/** lessons; personalities self-evolve |
| **Colony** | Solo | **Shared comms**, beacons, cross-agent reports |
| **Git** | Manual | **git_expert** autonomously commits/pushes to `colony/dev` |
| **Desktop** | GUI verbs in actor | **desktop.py** — planner Python can click, type, hotkey while colony work runs |
| **LLM hosts** | Fixed localhost | **Probes and load-balances** across `ENDGAME_LMS_HOSTS` |
| **UI** | HUD / JSON TUI modes | **Spectrogram TUI** — per-agent heatmaps + event tail |
| **Math** | Stagnation/PID/Lorenz | Same engine, feeds scheduler (reflect, cooldown, replan) |

`main` proved a single agent can rewrite itself. **This branch asks: what if five specialists breed together?** Plugins, reports, quality audits, and git pushes — without you assigning tickets.

---

## Quick start

```powershell
# Optional: local + remote LM Studio
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234,http://192.168.x.x:1234"
# Optional: prefer Gemma (default partial match "gemma")
$env:ENDGAME_LMS_MODEL = "gemma"

python tui.py
```

1. TUI launches `reactor.py` → five `main.py` children (one personality each).
2. Math telemetry runs immediately (stagnation, Lorenz, PID).
3. Press **Space** to unpause — agents plan and execute.
4. Press **Space** again to pause (saves LLM tokens; math still flows).

---

## Personalities (5 slots)

| Slot | Personality | Natural behavior |
|------|-------------|------------------|
| n1 | git_expert | status → add → commit → push `colony/dev` |
| n2 | implementor | reads errors, writes `plugins/*.py` |
| n3 | doc_inspector | reads events, writes `runtime/comms/report.md` |
| n4 | comms_operator | message bus, beacons, coordination |
| n5 | quality_critic | `py_compile` audit → `quality.json` |

---

## Architecture (one screen)

```
tui.py
  └── reactor.py          spawn 5 agents, respawn dead rods, measure k
        └── main.py ×5    plan → python actor → verify → fission_judge → fission
              ├── engine.py      scheduler, plugin hot-swap
              ├── agents.py      planner, verifier, fission_judge, reflector, mutator
              ├── comms.py       message bus (chat + events split)
              ├── desktop.py     mouse/keyboard/UIA for planner scripts
              ├── llm.py         LM Studio + strict JSON schemas
              └── log.py         JSONL event bus (math bypasses pause)
```

**Runtime** (`runtime/comms/`, `events-child-*.jsonl`, `snapshot.json`) is gitignored and recreated on boot via `log.cleanup_runtime()`.

---

## Desktop + colony at the same time

Planner steps are plain Python. Pre-imported helpers:

- **Files / git / subprocess** — `Path`, `subprocess`, `COMMS_DIR`, `PLUGINS_DIR`
- **GUI** — `enable_gui()`, `observe_screen()`, `desktop_click`, `desktop_write`, `desktop_press`, `desktop_hotkey`, `desktop_scroll`, `desktop_focus`

A single plan can write a report and click a dialog in separate steps. Five agents can mix file work and desktop work in parallel.

---

## Branches

```
main                  Stable single-agent release
reactor-personalities Human + merged agent work (synced with colony/dev)
colony/dev            Agent-autonomous target (git_expert pushes here)
```

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `ENDGAME_LMS_HOSTS` | Comma-separated LM Studio URLs to probe (default: localhost + `192.168.16.31:1234`) |
| `ENDGAME_LMS_HOST` | Preferred host per child (reactor sets this) |
| `ENDGAME_LMS_MODEL` | Model id substring (default: `gemma`) |
| `ENDGAME_PERSONALITY` | Personality name per slot (reactor sets) |
| `ENDGAME_SLOT` | Slot id 1–5 (reactor sets) |

Tune constants in `config.py`. Agent map in `AGENTS.md`. Grok/Cursor handoff in `GROK.md`.

---

## Clone completeness

A fresh clone contains all source, prompts, schemas, and plugins. Runtime artifacts are excluded by `.gitignore` and seeded when you run `python tui.py`.

---

## Principles

- Stdlib + ctypes only. No pip.
- Personality is the goal. No task assignment.
- Bad Python fails free (no LLM cost). Good plans earn fission.
- Plugins cannot crash the reactor — errors become events.

## License

MIT