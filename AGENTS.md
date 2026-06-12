# Breeding Reactor — Technical Map

## Entry point

```bash
python tui.py
```

Launches reactor, renders spectrogram + message bus panels, starts **paused**. Space = toggle live. q = kill all (`taskkill /F /T`).

## File map

### Core
| File | Role |
|------|------|
| tui.py | Spectrogram TUI, bus CHAT/EVENTS panels, inject drain, spacebar pause |
| reactor.py | Breeder. 6 slots, LM host probe + load-balance (max 3 slots/host) |
| main.py | Single fuel rod. Args, engine loop, personality env |
| engine.py | Scheduler chain, plugin hot-swap, desktop refresh before planner |
| agents.py | planner, actor (run_python), verifier, fission_judge, reflector, mutator, math |
| actions.py | GUI verbs + run_python subprocess runner |
| desktop.py | observe_screen, desktop_click/write/press/hotkey/scroll/focus/wait |
| colony_env.py | BASE_DIR, COMMS_DIR, PLUGINS_DIR, bus_post, bus_id, enable_gui, spawn_main |
| comms.py | Message bus — chat, bus_request() delegation, inbox in format_bus_context |
| python_code.py | Planner Python syntax validation (ASCII, no prose-as-code) |
| config.py | Paths, math tuning, CONTEXT_POLICY, LMS hosts, bus caps |
| llm.py | LM Studio API, schema enforcement, host failover |
| log.py | JSONL bus, cleanup_runtime, pause gate, comms.mirror_event for work phases |
| observer.py | UIA desktop scan → element book `[n]` ids |
| win32.py | ctypes user32, SendInput, VK map |
| token_state.py | Token telemetry |
| lessons.py | Persistent lesson store |

### Personalities (`prompts/personalities/`)
| File | Identity |
|------|----------|
| git_expert.txt | Commits/pushes colony/dev |
| implementor.txt | Writes plugins |
| doc_inspector.txt | report.md from logs |
| comms_operator.txt | messages.json bus, beacons, coordination |
| quality_critic.txt | quality.json plugin audit |
| gui_operator.txt | Sole GUI specialist (@GUI / n6), desktop_* only |

One personality per slot (n1–n6). Reflector can append `EVOLVE:` lines to personality files.

### Schemas (LM Studio strict JSON)
| Schema | Output |
|--------|--------|
| planner.json | `{mode, sequence[{code}], done_when}` — Python in `code` |
| verifier.json | `{verdict, evidence}` |
| fission_judge.json | `{approve, reason}` — LLM gate before fission credit |
| reflector.json | `{diagnosis, suggestion, rule}` |
| mutator.json | `{action, filename, content}` |
| actor.json | Legacy; actor runs planner Python directly |

### Plugins (`plugins/`)
Hot-loaded every tick. `def run(board) -> dict | None`. Errors → `plugin.error`, never crash.

### Runtime (gitignored, bootstrapped by `log.cleanup_runtime`)
`runtime/comms/`:
- `messages.json` — peer chat/beacon only (human, grok, colony slots); capped `BUS_CHAT_MAX`
- `events_bus.jsonl` — rolling work events for TUI (math/plugin spam not mirrored)
- `inject.jsonl` — external posts drained by engine/TUI
- `report.md`, `quality.json`, beacons, telemetry

Per-agent: `events-child-n*.jsonl`. Board: `snapshot.json`.

## Process tree

```
tui.py → reactor.py → main.py ×5
```

Shared working directory. Only git_expert does git ops. Reactor sets `ENDGAME_PERSONALITY` + `ENDGAME_SLOT` per child.

## Planner → actor path

1. Planner LLM returns `sequence[].code` (plain Python).
2. ActorAgent calls `actions.run_python()` — full plan sequence in one subprocess with colony_env + desktop imports.
3. Verifier confirms LAST_RESULT.
4. FissionJudgeAgent (reflector prompt + fission_judge schema) approves or blocks fission.
5. Fission on approval.

**Desktop:** `enable_gui()` creates `gui_mode` file; engine refreshes screen before planner; code uses `desktop_*` helpers.

## Message bus

| Path | Content |
|------|---------|
| `runtime/comms/messages.json` | Chat/beacon — retained, not evicted by work spam |
| `runtime/comms/events_bus.jsonl` | Work phases mirrored from `log.emit` (rolling 200 lines) |
| `runtime/comms/inject.jsonl` | Drained inject queue for TUI + engine |

CLI (human/grok as colony peers):
```bash
python comms.py post human "@grok check n4"
python comms.py post grok "@Human need eyes on TUI"
```

**@mention protocol:** `@Human` = operator, `@grok` = external AI, `@GUI` = gui_operator, `@n1`–`@n6`, `@colony` = broadcast.

**Bus requests:** `bus_request(bus_id(), "gui_operator", "task")` — structured delegation; inbox shown first in planner context. Only gui_operator uses `desktop_*`; engine auto-enables `gui_mode` for n6.

Planner context: `format_bus_context(for_agent=…)` with YOUR INBOX + ** PING FOR YOU **. Non-GUI agents use `planner.txt`; gui_operator uses `planner_gui.txt`.

## Scheduler priorities

1. No plan → reflect if stuck (high stag + failures), else cooldown after reject, else planner.
2. Plan complete → verifier.
3. Reflect gate (PID/stag/chaos) → reflector.
4. Wing cross → replan.
5. Active/pending step → actor.

Plan reject: history + LAST_RESULT feedback, 10s cooldown, stagnation-capped failure weight.

## LM Studio hosts

- `ENDGAME_LMS_HOSTS` — candidate list (comma-separated). Default: localhost + `192.168.16.31:1234`.
- Reactor probes `/v1/models`, assigns least-loaded healthy host per slot.
- `LMS_MAX_SLOTS_PER_HOST` = 2 — caps concurrent slots per GPU.
- Child gets `ENDGAME_LMS_HOST` + full fallback list; `llm.py` fails over on error.
- `LMS_PREFERRED_MODEL` default `gemma` (override: `ENDGAME_LMS_MODEL`).
- `LMS_TIMEOUT` = 90s.

## Pause architecture

- File: `pause` in project root (presence = paused).
- TUI creates on start; spacebar toggles.
- `log.emit`: work phases sink when paused; math always flows.

## Branch architecture

```
reactor-personalities   Active dev (human + merged agent work)
colony/dev              Agent-only (git_expert pushes autonomously)
main                    Stable single-agent release
```

## Key constants (`config.py`)

| Constant | Value | Notes |
|----------|-------|-------|
| REACTOR_SLOTS | 6 | |
| MATH_INTERVAL | 5.0s | batched math event |
| PLAN_REJECT_COOLDOWN_SEC | 10 | anti spam |
| REFLECT_MIN_INTERVAL_SEC | 12 | |
| LMS_PREFERRED_MODEL | gemma | env override |
| LMS_TIMEOUT | 90 | seconds |
| LMS_MAX_SLOTS_PER_HOST | 3 | load balance cap |
| BUS_CHAT_MAX | 120 | chat retention |
| BUS_EVENTS_MAX_LINES | 200 | events bus rolling window |

## Rules

- No pip dependencies. Stdlib + ctypes only.
- No personal identifiers in code or commits.
- Personality IS the goal. No task assignment.
- Runtime artifacts never committed (see `.gitignore`).