# endgame-ai

A self-sustaining Windows 11 desktop automation reactor. It plans goals, observes the screen, executes actions, verifies results, and evolves its own behavior — all with zero pip dependencies.

## What it does

You give it a goal. It breaks it down into steps, executes them (headless Python or GUI automation), verifies completion, and moves on. When it gets stuck, math agents detect stagnation through a Lorenz attractor / PID controller system, triggering reflection that mutates the organism's own prompts. When capabilities are missing, the mutator agent writes new plugins at runtime.

Verified work = **fission**. The reactor sustains itself through fission events. If it can't make progress, it reflects, mutates, and adapts.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN THREAD                               │
│  engine._main_loop (every 0.15s)                                │
│  ┌──────────┐   ┌─────────┐   ┌────────┐   ┌──────────┐       │
│  │ Scheduler│──▶│ Planner │──▶│ Actor  │──▶│ Verifier │──┐    │
│  └──────────┘   └─────────┘   └────────┘   └──────────┘  │    │
│       │                                          │         │    │
│       │         ┌──────────┐   ┌─────────┐      │fission  │    │
│       └────────▶│Reflector │   │ Mutator │◀─────┘(fail)   │    │
│                 └──────────┘   └─────────┘                 │    │
│  ┌─────────────────────────────────────────────────┐       │    │
│  │ Plugin Loader: plugins/*.py (hot-loaded by mtime)│       │    │
│  └─────────────────────────────────────────────────┘       │    │
└────────────────────────────────────────────────────────────┘    │
                                                                   │
┌─────────────────────────────────────────────────────────────────┐
│                        MATH THREAD (every 3s)                    │
│  StagnationAgent ──▶ LorenzAgent ──▶ PidAgent                   │
│  (detects stuck)     (chaos/energy)  (control signal)           │
└─────────────────────────────────────────────────────────────────┘
                            │
                    shared board dict
```

- **10 agents**: 5 LLM (planner, actor, verifier, reflector, mutator) + 3 math + 1 scheduler + 1 observer
- **2 threads**: main reactor loop + math heartbeat
- **1 board dict**: single shared mutable state
- **Plugin system**: drop a .py file in `plugins/` → loaded next cycle

## Requirements

- Windows 10/11
- Python 3.13+
- LM Studio running on localhost:1234, OR Kiro CLI with ACP backend
- Zero pip packages (everything is stdlib + ctypes)

## Quick start

```bash
# Parent (ACP) watching child (LM Studio):
python tui.py --backend acp --event-budget 1000 "Your goal here"

# Standard launch:
python tui.py "Your goal" --backend lmstudio --event-budget 500

# Headless (no TUI):
python main.py "Your goal" --backend lmstudio --event-budget 200

# Verify import health:
python -c "import config,engine,agents,actions,log,llm,observer,win32,acp_client,tui,token_state,lessons;print('OK')"
```

## How it evolves

The organism has multiple self-evolution mechanisms, ordered by immediacy:

| Mechanism | Latency | What changes |
|-----------|---------|--------------|
| Prompt file read | instant | prompts/*.txt read on every LLM call |
| Prompt mutation | instant | Reflector appends RULE to prompt files |
| Plugin hot-load | ~0.15s | New .py in plugins/ loaded next cycle |
| Plugin mutation | ~5-10s | MutatorAgent writes new plugin to disk |
| Goal hot-swap | ~0.15s | Edit goal.txt → reactor pivots |
| Disk edit + spawn | ~2-5s | Write code + spawn_main() for new process |

## Math-driven scheduling

Math is the environment. LLMs are agents inside it. The LLMs never see math values.

```
StagnationAgent → neutron flux (0.0-1.0, rises when nothing succeeds)
LorenzAgent     → chaotic attractor (energy, wing_cross = regime change)
PidAgent        → integral pressure (accumulates when stag stays high)

Scheduler priority:
  1. Reflection gates (stag+pid/energy high → reflector)
  2. Wing cross (Lorenz regime change → replan)
  3. Normal routing (actor executes plan steps)

Escalation:
  reflector (prompt mutation) → mutator (code generation, after ≥3 persistent failures)

Activity dampening:
  mutations/reflections produce activity_events → stagnation drops 0.2/event
  prevents infinite reflect/mutate loops — gives work loop a window to retry
```

## Proven milestones (M4)

On 2026-06-10, the reactor demonstrated:
- Self-launch via TUI subprocess
- Self-edit of config.py at runtime
- Prompt mutation by reflector agent
- Child process spawn on evolved disk
- Child fission (independent verified work)
- Dual stop (parent + child both completed)
- GUI automation (browser, social media)
- Safety gate preventing bad .py writes

## File structure

```
endgame-ai/
├── main.py              Entry point, argparse, SIGINT, board init
├── engine.py            Reactor loop, math thread, plugin loader, fission
├── agents.py            All 10 agent classes + context rendering
├── actions.py           Exec engine, GUI verbs, spawn, write_file
├── observer.py          Screen observation via UIA + hover probe
├── config.py            All constants and paths (single source of truth)
├── log.py               Event bus, lock file, pause, budget
├── llm.py               LM Studio + ACP backends
├── win32.py             Raw ctypes COM/UIA (no pywin32)
├── acp_client.py        Kiro CLI ACP JSON-RPC over WSL2
├── tui.py               VT100 terminal dashboard (parent/child split)
├── token_state.py       Token usage accounting
├── lessons.py           Scored lesson store with keyword retrieval
├── prompts/             LLM system prompts (5 agents)
├── schemas/             JSON output schemas (5 agents)
├── plugins/             Hot-loaded plugins (run each cycle)
└── AGENTS.md            Authoritative technical map (for coding agents)
```

## Key constraints

- **Zero pip dependencies** — stdlib + ctypes only
- **events.jsonl format is frozen** — `{n, t, phase, d}` parsed by TUI
- **Board dict keys never rename** — snapshot.json and logs reference them
- **Math is the environment** — LLMs never see or tune math knobs
- **Self-modification is intentional** — the system can rewrite itself
- **PROMPT_MAX_RULES = 8** — prevents reflector meltdown (proven failure mode)

## For coding agents

Read `AGENTS.md` before modifying anything. It contains the full technical map: dependency graph, board dict schema, agent roster, execution model, plugin contract, and design constraints.

## License

MIT (c) 2026 wgabrys88
