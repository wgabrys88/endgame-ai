# Breeding Reactor — Agent Technical Map

## Entry point

```bash
python tui.py
```

Starts **paused**. **Space** = LIVE. **q** = kill tree.

---

## Process tree

```
tui.py → reactor.py → main.py ×6
```

Reactor sets `ENDGAME_PERSONALITY` + `ENDGAME_SLOT` per child. Only `git_expert` does git ops.

---

## Core files

| File | Role |
|------|------|
| `tui.py` | Spectrogram TUI, bus panels, pause toggle |
| `reactor.py` | Breeder: 6 slots, LM host probe, respawn |
| `main.py` | Single fuel rod: args, engine loop |
| `engine.py` | Scheduler, plugin hot-swap, math thread |
| `agents.py` | planner, actor, verifier, fission_judge, reflector, mutator |
| `actions.py` | `run_python` subprocess runner + GUI verbs |
| `desktop.py` | `observe_screen`, `desktop_*` helpers |
| `colony_env.py` | Pre-imported env for agent scripts |
| `comms.py` | Message bus: chat, events, inject |
| `python_code.py` | Syntax validation |
| `config.py` | Constants and paths |
| `llm.py` | LM Studio API + schema enforcement |
| `log.py` | JSONL events, pause gate |
| `observer.py` | UIA desktop scan |
| `win32.py` | ctypes user32, SendInput |

---

## Personalities (`prompts/personalities/`)

| Slot | File | Identity |
|------|------|----------|
| n1 | `git_expert.txt` | Commits/pushes `colony/dev` |
| n2 | `implementor.txt` | Writes `plugins/*.py` |
| n3 | `doc_inspector.txt` | `runtime/comms/report.md` |
| n4 | `comms_operator.txt` | Bus coordination |
| n5 | `quality_critic.txt` | `py_compile` audits |
| n6 | `gui_operator.txt` | Sole GUI specialist (@GUI) |

---

## Pipeline

```
planner → actor (run_python) → verifier → fission_judge → fission
```

---

## Message bus

| Path | Content |
|------|---------|
| `runtime/comms/messages.json` | Peer chat (120 cap) |
| `runtime/comms/events_bus.jsonl` | Work events (200 lines rolling) |
| `runtime/comms/inject.jsonl` | External posts drained by engine |

**Peers:** `@Human`, `@grok`, `@GUI`, `@n1`–`@n6`, `@colony`.

```bash
python comms.py post grok "@colony @GUI open Notepad"
python comms.py post human "@grok status"
```

---

## Key constants

| Constant | Value |
|----------|-------|
| REACTOR_SLOTS | 6 |
| MATH_INTERVAL | 5.0s |
| PLAN_REJECT_COOLDOWN_SEC | 10 |
| BUS_CHAT_MAX | 120 |
| BUS_EVENTS_MAX_LINES | 200 |

---

## Rules

- Stdlib + ctypes only. No pip.
- Personality IS the goal.
- Runtime never committed.
- Plugins cannot crash the reactor.
