# endgame-ai — breeding reactor

Six AI agents on your Windows desktop. They share one codebase, write plugins, file reports, commit to git, and drive the real UI — while a live spectrogram shows whether the colony is thriving or stuck.

```bash
python tui.py
```

Starts **paused**. **Space** = LIVE. **q** = stop. Requires [LM Studio](https://lmstudio.ai/) (tested: Gemma 4B).

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

---

## Message bus

Chat in `runtime/comms/messages.json`. Work events in `events_bus.jsonl`. External posts via `inject.jsonl`.

---

## Quick start

```powershell
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234,http://192.168.x.x:1234"
python tui.py
```

1. TUI boots paused → reactor spawns 6 children.
2. Space = LIVE. Space again = pause.
3. q = shutdown.

---

## Architecture

```
tui.py → reactor.py → main.py ×6
                        ├── engine.py    scheduler, plugins
                        ├── agents.py    planner, verifier, fission_judge
                        ├── comms.py     message bus
                        ├── desktop.py   mouse, keyboard, UIA
                        └── log.py       events
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
| `ENDGAME_LMS_HOSTS` | LM Studio URLs |
| `ENDGAME_LMS_MODEL` | Model substring (default: `gemma`) |
| `ENDGAME_PERSONALITY` | Set by reactor per slot |
| `ENDGAME_SLOT` | 1–6, set by reactor |

---

## Principles

- Stdlib + ctypes only.
- Personality is the goal.
- Runtime never committed.
- Plugins cannot crash the reactor.

## License

MIT
