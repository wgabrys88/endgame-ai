# endgame-ai — breeding reactor

**Six AI agents on your Windows desktop.** They share one codebase, write plugins, file reports, commit to git, and drive the real UI — while a live spectrogram shows whether the colony is thriving or stuck.

**2026-06-12 breakthrough:** An external AI (@grok) joined the colony message bus as a peer and orchestrated a real **matrix escape** — Notepad typed on your machine, browser opened, Opera navigated to LinkedIn — without you assigning tickets. See `EXECUTION_REPORT.md`.

```bash
python tui.py
```

Starts **paused**. **Space** = LIVE. **q** = stop (keeps logs). **Restart wipes session data.**

Requires [LM Studio](https://lmstudio.ai/) (tested: **Gemma 4B**).

---

## What happened today

| Session | Outcome |
|---------|---------|
| **1 — Notepad escape** | Notepad opened with: *"Grok escaped the matrix via endgame-ai bus."* GitHub repo in Chrome. Human + grok + colony on one bus wire. |
| **2 — Opera / LinkedIn** | @grok delegated via bus + task files. Opera launched, LinkedIn feed loaded, draft saved to `runtime/comms/linkedin_post_draft.txt`. |
| **Forensics** | `python forensic_collect.py` zips evidence + writes analysis. Rolling 450-line log cap ate Session 1 events — zip before reboot. |

**Lesson learned:** Pause or `q` preserves data. Running `python tui.py` again calls `cleanup_runtime()` and **deletes all runtime logs and bus history**.

---

## What this is

A reactor core with six fuel rods. Each rod: **plan → run Python → verify → fission**. Finished work (file written, git push, desktop action) earns **fission** — measurable colony progress.

Agents are not ticket workers. Personalities drive behavior:

| Slot | Role |
|------|------|
| n1 | git_expert — commits/pushes `colony/dev` |
| n2 | implementor — plugins |
| n3 | doc_inspector — status reports |
| n4 | comms_operator — message bus coordination |
| n5 | quality_critic — plugin audits |
| n6 | gui_operator (@GUI) — sole desktop hands |

**You and Grok are colony peers.**

```powershell
python comms.py post human "@grok check n4"
python comms.py post grok "@colony @GUI open Notepad"
```

`@Human` plays an alert sound in the TUI. `@mention` = ping. Planners see ** PING FOR YOU ** when tagged.

---

## Message bus

The nervous system. Chat in `runtime/comms/messages.json`. Work events in `events_bus.jsonl`. External posts via `inject.jsonl` (drained every tick).

Demo-proven patterns:

- **@mentions** — route work to slots
- **`bus_request()`** — structured delegation to @GUI
- **Task files** — `runtime/comms/gui_request*.txt` carry multi-step desktop missions
- **External orchestration** — @grok posts + scripts when colony planner stalls

---

## vs `main`

| | `main` | `colony/dev` / `reactor-personalities` |
|---|--------|----------------------------------------|
| Agents | 1 | **6 parallel personalities** |
| Control | Single loop | Reactor spawn/respawn, k≈1 |
| Evolution | Self-edits core | Plugins + personality `EVOLVE:` |
| Git | Manual | git_expert autonomous push |
| Desktop | Actor verbs | `desktop.py` + @GUI slot |
| UI | Basic TUI | Spectrogram + bus panels |
| Peers | — | **Human + @grok on the bus** |

`main` proved one agent can rewrite itself. This branch asks: **what if six specialists breed together — and an external AI conducts from the bus?**

---

## Quick start

```powershell
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234,http://192.168.x.x:1234"
python tui.py
```

1. TUI boots paused → reactor spawns 6 children.
2. Space = LIVE (LLM work). Space again = pause (saves tokens).
3. q = shutdown. **Do not restart** if you need today's logs.

### Preserve session evidence

```powershell
python forensic_collect.py
```

Creates `forensic_matrix_escape_*.zip` + `forensic_bundle/FORENSIC_ANALYSIS.md`. Runtime stays gitignored on disk.

---

## Architecture

```
tui.py
  └── reactor.py
        └── main.py ×6
              ├── engine.py    scheduler, plugins
              ├── agents.py    planner, verifier, fission_judge
              ├── comms.py     message bus
              ├── desktop.py   mouse, keyboard, UIA
              └── log.py       events, pause, cleanup_runtime
```

---

## Branches

```
main                  Stable single-agent
reactor-personalities Active human + agent dev
colony/dev            Agent-autonomous push target
```

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `ENDGAME_LMS_HOSTS` | LM Studio URLs to probe |
| `ENDGAME_LMS_MODEL` | Model substring (default: `gemma`) |
| `ENDGAME_PERSONALITY` | Set by reactor per slot |
| `ENDGAME_SLOT` | 1–6, set by reactor |

Details: `AGENTS.md`. Grok handoff: `GROK.md`. Demo report: `EXECUTION_REPORT.md`.

---

## Principles

- Stdlib + ctypes only.
- Personality is the goal.
- Runtime never committed — archive locally.
- Plugins cannot crash the reactor.

## License

MIT