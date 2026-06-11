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
# Standard launch with TUI dashboard:
python tui.py "Your goal here" --backend lmstudio --event-budget 500

# Headless (no TUI):
python main.py "Your goal" --backend lmstudio --event-budget 200

# Verify import health:
python -c "import config,engine,agents,actions,log,llm,observer,win32,acp_client,tui;print('OK')"
```

## How it evolves

The organism has multiple self-evolution mechanisms, ordered by immediacy:

| Mechanism | Latency | What changes |
|-----------|---------|--------------|
| Prompt file read | instant | prompts/*.txt read on every LLM call |
| config.X patch | instant | `exec("import config; config.X = Y")` |
| Prompt mutation | instant | Reflector appends RULE to prompt files |
| Plugin hot-load | ~0.15s | New .py in plugins/ loaded next cycle |
| Plugin mutation | ~5-10s | MutatorAgent writes new plugin to disk |
| Goal hot-swap | ~0.15s | Edit goal.txt → reactor pivots |
| Disk edit + spawn | ~2-5s | Write code + spawn_main() for new process |

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
├── tui.py               VT100 terminal dashboard
├── token_state.py       Token usage accounting
├── prompts/             LLM system prompts (5 agents)
├── schemas/             JSON output schemas (5 agents)
├── plugins/             Hot-loaded plugins (run each cycle)
├── evolved-organism-code/  Archived organism evolution artifacts
└── AGENTS.md            Authoritative technical map (for coding agents)
```

## Key constraints

- **Zero pip dependencies** — the organism must be able to self-install capabilities
- **events.jsonl format is frozen** — `{n, t, phase, d}` is parsed by TUI and tests
- **Board dict keys never rename** — snapshot.json and logs reference them
- **_verify_python_edit is sacred** — the organism's immune system against bad code
- **PROMPT_MAX_RULES = 8** — prevents reflector meltdown (proven failure mode)

## For coding agents

Read `AGENTS.md` before modifying anything. It contains the full technical map: dependency graph, board dict schema, agent roster, execution model, plugin contract, and design constraints.

## License

Private.
