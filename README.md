# endgame-ai

A breeding reactor for AI agents. They evolve by writing code, not by following instructions.

## Quick start

```bash
python tui.py
```

One command. Launches reactor, spawns 8 agents, renders live spectrogram. Starts paused (math-only mode). Press **Space** to go live. Press **q** to kill everything.

Requires LM Studio running on `localhost:1234` and/or a remote GPU host.

## What this is

A nuclear fission reactor where the fuel rods are LLM agents with personalities. The reactor maintains criticality (stable population), and agents breed by writing new code — plugins, fixes, documentation, commits. Evolution is code generation, file creation, wiring new behavior. The reactor breeds agents that breed better agents.

## How it works

Each agent has a personality, not a task. A git expert sees uncommitted changes and commits them. A documentation inspector sees gaps and fills them. An implementor sees errors and writes fixes. Nobody assigns work. Identity drives action.

```
tui.py                      Single entry point. Spectrogram + auto-launch.
reactor.py                  The breeder. Spawns personalities, maintains k~1.0.
main.py                     A single fuel rod. Born, fissions, dies, respawns.
engine.py                   Scheduler + plugin hot-swap loader.
log.py                      Event bus. Math phases bypass pause gate.
config.py                   All paths and tuning constants.
prompts/personalities/      Isotope types. Each personality pursues its nature.
plugins/                    Fission products. Written by agents, loaded by agents.
runtime/comms/              Communication channel. Beacons, reports, human bridge.
```

## TUI

The spectrogram TUI shows real-time agent activity:

- Per-agent identity row with stagnation/energy/PID bars
- 4 recent work events per agent
- 3 spectrogram heatmap strips (stagnation=red, energy=green, PID=blue)
- Header: alive count, fission rate, avg stagnation, uptime
- Math-only mode: agents frozen, math telemetry still flows

Adapts to terminal width. ASCII box drawing for universal compatibility.

## Personalities (8 slots)

| Slot | Personality | Natural behavior |
|------|------------|-----------------|
| 1-2 | git_expert | Checks status, stages, commits, pushes to colony/dev |
| 3-4 | doc_inspector | Reads logs, counts events, writes reports |
| 5 | implementor | Reads errors, writes fix plugins |
| 6 | comms_operator | Maintains beacons, relays messages, reads human.txt |
| 7 | quality_critic | Audits plugins, catches syntax errors |
| 8 | wild | No goal. Pure planner personality drives behavior |

## Branch architecture

```
main                    Stable release (merge when battle-tested)
reactor-personalities   Active development branch
colony/dev              Agent-only branch — autonomous commits land here
```

The git_expert personality pushes to `colony/dev`. Human work stays on `reactor-personalities`. Periodically merge colony/dev into reactor-personalities to accept agent contributions.

## Pause / math-only mode

TUI starts paused. Agents are spawned but `log.emit()` sinks all work events. Only math telemetry flows (stagnation, PID, Lorenz). This lets you observe the math engine without burning LLM tokens.

- **Space** toggles pause on/off
- Pause is a file (`pause` in project root) — agents check it every emit
- Math phases (`stagnation`, `lorenz`, `pid`) always emit regardless of pause

## Plugin hot-swap

Agents write plugins to `plugins/`. Every tick, `engine.py` reloads all `*.py` files:

- Load errors → `plugin.error` event, system continues
- Runtime errors → `plugin.error` event, system continues
- No crash possible from buggy plugins

## Process architecture

```
tui.py (user-facing)
  └── reactor.py (spawned as subprocess)
        ├── main.py n1 (git_expert, remote GPU)
        ├── main.py n2 (git_expert, remote GPU)
        ├── main.py n3 (doc_inspector, remote GPU)
        ├── main.py n4 (doc_inspector, remote GPU)
        ├── main.py n5 (implementor, remote GPU)
        ├── main.py n6 (comms_operator, remote GPU)
        ├── main.py n7 (quality_critic, local)
        └── main.py n8 (wild, local)
```

`q` or Ctrl+C → `taskkill /F /T` kills entire tree. All agents share one process tree.

## Configuration

Edit top of `reactor.py`:
```python
REMOTE = "http://192.168.16.31:1234"  # Remote LM Studio
LOCAL = "http://localhost:1234"        # Local LM Studio
REMOTE_SLOTS = 6
LOCAL_SLOTS = 2
```

Edit `config.py` for paths and math interval.

## Proven results

- Autonomous git commits to colony/dev without instruction
- Plugin authoring (agents wrote telemetry.py, auto_fix.py)
- Agent rewrote its own personality prompt (git_expert.txt)
- Human message relay via comms/human.txt
- Plugin quality gates via py_compile
- Colony reports in markdown
- Self-healing respawn on agent death
- 16 fissions in 50 seconds (Gemma 4B, 8 agents)

## Principles

- Zero pip dependencies. Stdlib + ctypes only.
- Personality IS the goal. No task assignment.
- Math serves the model. Stagnation, PID, Lorenz — translated to plain language.
- Python exec errors are free feedback. No LLM cost for validation.
- The reactor is not a metaphor. It is the literal control architecture.

## License

MIT
