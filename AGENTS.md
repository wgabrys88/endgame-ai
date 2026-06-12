# Breeding Reactor — Technical Map

## Entry point

```bash
python tui.py
```

Launches reactor, renders spectrogram, starts **paused**. Space = toggle live. q = kill all (`taskkill /F /T`).

## File map

### Core
| File | Role |
|------|------|
| tui.py | Spectrogram TUI. Auto-launches reactor. Spacebar pause. |
| reactor.py | Breeder. 5 slots, LM host probe + load-balance, k~1.0. |
| main.py | Single fuel rod. Args, engine loop, personality env. |
| engine.py | Scheduler chain, plugin hot-swap, desktop refresh before planner. |
| agents.py | planner, actor (run_python), verifier, reflector, mutator, math agents. |
| actions.py | GUI verbs + run_python subprocess runner. |
| desktop.py | observe_screen, desktop_click/write/press/hotkey/scroll/focus/wait. |
| colony_env.py | BASE_DIR, COMMS_DIR, PLUGINS_DIR, enable_gui, spawn_main. |
| python_code.py | Sanitize/validate planner Python (ASCII, no prose-as-code). |
| config.py | Paths, math tuning, CONTEXT_POLICY, LMS hosts. |
| llm.py | LM Studio API, schema enforcement, host failover. |
| log.py | JSONL bus, cleanup_runtime, pause gate. |
| observer.py | UIA desktop scan → element book `[n]` ids. |
| win32.py | ctypes user32, SendInput, VK map. |
| token_state.py | Token telemetry. |
| lessons.py | Persistent lesson store. |

### Personalities (`prompts/personalities/`)
| File | Identity |
|------|----------|
| git_expert.txt | Commits/pushes colony/dev |
| implementor.txt | Writes plugins |
| doc_inspector.txt | report.md from logs |
| comms_operator.txt | messages.json, beacons |
| quality_critic.txt | quality.json plugin audit |

One personality per slot (n1–n5). Reflector can append `EVOLVE:` lines to personality files.

### Schemas (LM Studio strict JSON)
| Schema | Output |
|--------|--------|
| planner.json | `{mode, sequence[{code}], done_when}` — Python in `code` |
| verifier.json | `{verdict, evidence}` |
| reflector.json | `{diagnosis, suggestion, rule}` |
| mutator.json | `{action, filename, content}` |
| actor.json | Legacy; actor runs planner Python directly |

### Plugins (`plugins/`)
Hot-loaded every tick. `def run(board) -> dict | None`. Errors → `plugin.error`, never crash.

### Runtime (gitignored, bootstrapped)
`runtime/comms/` — human.txt, messages.json, report.md, quality.json, beacons, telemetry.
`events-child-n*.jsonl` — per-agent log. `snapshot.json` — board snapshot.

## Process tree

```
tui.py → reactor.py → main.py ×5
```

Shared working directory. Only git_expert does git ops.

## Planner → actor path

1. Planner LLM returns `sequence[].code` (plain Python).
2. ActorAgent calls `actions.run_python()` — temp script with colony_env + desktop imports.
3. Verifier confirms LAST_RESULT; fission on success.

**Desktop:** `enable_gui()` creates `gui_mode` file; engine refreshes screen before planner; code uses `desktop_*` helpers.

## Scheduler priorities

1. No plan → reflect if stuck (high stag + failures), else cooldown after reject, else planner.
2. Plan complete → verifier.
3. Reflect gate (PID/stag/chaos) → reflector.
4. Wing cross → replan.
5. Active/pending step → actor.

Plan reject: history + LAST_RESULT feedback, 10s cooldown, stagnation-capped failure weight.

## LM Studio hosts

- `ENDGAME_LMS_HOSTS` — candidate list (comma-separated).
- Reactor probes `/v1/models`, assigns least-loaded healthy host per slot.
- Child gets `ENDGAME_LMS_HOST` + full fallback list; `llm.py` fails over on error.
- `LMS_PREFERRED_MODEL` default `gemma` (override: `ENDGAME_LMS_MODEL`).

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
| REACTOR_SLOTS | 5 | |
| MATH_INTERVAL | 5.0s | batched math event |
| PLAN_REJECT_COOLDOWN_SEC | 10 | anti spam |
| REFLECT_MIN_INTERVAL_SEC | 12 | |
| LMS_PREFERRED_MODEL | gemma | env override |

## Rules

- No pip dependencies. Stdlib + ctypes only.
- No personal identifiers in code or commits.
- Personality IS the goal. No task assignment.
- Runtime artifacts never committed (see `.gitignore`).