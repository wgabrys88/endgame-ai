# Breeding Reactor — Technical Map

## Entry point

```bash
python tui.py
```

Launches reactor, renders spectrogram, starts paused. Space = toggle live. q = kill all.

## File map

### Core
| File | Role |
|------|------|
| tui.py | Spectrogram TUI. Auto-launches reactor. Spacebar pause. |
| reactor.py | Breeder. Spawns 8 personalities, maintains k~1.0. |
| main.py | Single fuel rod. Parses args, runs engine loop. |
| engine.py | Tick loop. Phases, plugin hot-swap, events. |
| agents.py | Phase implementations: plan, exec, verify, reflect, mutate. |
| config.py | Constants, paths, budgets. PAUSE_PATH, MATH_INTERVAL. |
| llm.py | LM Studio API. Schema enforcement. |
| log.py | JSONL event bus. Math bypasses pause gate. |
| token_state.py | Token budget tracking. |
| lessons.py | Persistent lesson store. |

### Personalities (prompts/personalities/)
| File | Identity | Emergent behavior |
|------|----------|-------------------|
| git_expert.txt | Commits to colony/dev | git status → add → commit → push |
| doc_inspector.txt | Reads logs, writes reports | Counts events, writes markdown |
| implementor.txt | Fixes problems with code | Writes plugins when errors found |
| comms_operator.txt | Maintains channels | Beacons, relays, checks human.txt |
| quality_critic.txt | Validates code quality | Audits plugins with py_compile |

Slot 8 has no personality file (wild agent — pure planner drives it).

### Schemas (LM Studio strict JSON)
- planner.json: `{mode, sequence[], done_when}`
- verifier.json: `{verdict, evidence}`
- reflector.json: `{diagnosis, suggestion, rule}`
- mutator.json: `{action, filename, content}`

### Plugins (plugins/)
Hot-loaded every tick by engine.py. Written by agents. Each: `def run(board): -> dict | None`
Load or runtime errors emit `plugin.error` — never crash.

### Runtime (runtime/comms/)
Beacons (heartbeat), telemetry, fission log, human bridge, reports.
Agents read each other's output here.

## Process tree

```
tui.py → reactor.py → main.py ×8 (all same process tree)
```

taskkill /F /T on reactor PID kills everything. No orphans.

## Pause architecture

- File: `pause` in project root (presence = paused)
- TUI creates on start, spacebar toggles
- log.py line 135: `if paused() and phase not in _MATH_PHASES: return`
- Math phases always flow: stagnation, lorenz, pid
- Work phases sink when paused: plan, exec, verify, reflect, etc.

## Branch architecture

```
reactor-personalities   Active dev (human + merged agent work)
colony/dev              Agent-only (git_expert pushes here autonomously)
main                    Stable (merge when battle-tested)
```

## Key constants (config.py)
- MATH_INTERVAL = 3.0s (stagnation/PID/Lorenz tick rate)
- EVENT_BUDGET = 999999 (effectively unlimited)
- CONTROL_INTERVAL = 10s (reactor respawn check)

## Rules
- No pip dependencies. Stdlib + ctypes only.
- No personal identifiers in code.
- Personality IS the goal. No task assignment.
- Agents share working directory. Only git_expert does git ops.
