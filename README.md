# endgame-ai

A living organism that controls your Windows desktop. Not an agent framework — an evolving colony of specialized rods that plans, acts, verifies, and mutates under pressure.

## Philosophy

- Agents: task -> done -> exit -> dead
- Organism: task -> fission -> evolve -> what next? -> never stop

**Everything is Python.** Every LLM response is Python code executed directly. No JSON schemas, no verb DSLs, no structural constraints. The LLM is a Python programmer working on a computer. The organism self-regulates through pressure and natural selection.

## Architecture

```
Human goal
    |
    v
TUI (tui.py) -> Reactor (reactor.py) -> 5 slots
    |               |
    v               v
Colony Bus    MAP-Elites Breeder
(comms.py)    (fitness archive)
```

Each slot runs the engine loop:
```
Plan (Python) -> Execute (Python) -> Verify (Python) -> Fission/Reflect -> Evolve
```

### The Universal Execution Model

Every LLM call returns Python code. The engine executes it. Signal functions communicate intent:

```python
# Planner outputs:
add_step("subprocess.run(['cmd','/c','start notepad']); print('opened')")
add_step("desktop_write('hello'); print('typed')")
set_done_when("Notepad contains hello")

# Verifier outputs:
confirm("typed 5 chars, Notepad window title shows hello")

# Fission judge outputs:
credit("Novel work: opened notepad and wrote text")

# Mutator outputs:
patch_file("plugins/smarter.py", "def run(board):\n    ...")
```

### Biological Mapping

| Component | Biology | Role |
|-----------|---------|------|
| comms_operator | Thalamus | Routes all human stimuli to workers |
| architect | Frontal cortex | Plans, designs, navigates |
| implementor | Motor cortex | Executes, clicks, types, writes files |
| reviewer | Quality | Verifies, audits, tests |
| devops | Infrastructure | Git, deployment, system health |
| engine.py | Autonomic | Pressure fields, metabolism |
| reactor.py | Reproductive | MAP-Elites breeder, fission |

## Requirements

- Windows 11
- Python 3.11+
- [LM Studio](https://lmstudio.ai/) running locally with a model loaded

## Quick Start

```powershell
git clone https://github.com/wgabrys88/endgame-ai.git
cd endgame-ai

# Default: LM Studio at localhost:1234
python tui.py "Open notepad and write hello" --model-profile nemotron_parallel
```

## Configuration

`.env`:
```
ENDGAME_LMS_HOSTS=http://localhost:1234
```

Model profiles: `nemotron` (single, safe) or `nemotron_parallel` (5 concurrent).

## How It Works

1. **Human goal** -> comms_operator decomposes into subtasks
2. **Planner** writes Python: `add_step("code")`, `set_done_when("criteria")`
3. **Actor** executes each step as Python subprocess
4. **Verifier** writes Python: `confirm("evidence")` or `deny("reason")`
5. **Fission** awards credit for novel work (natural selection)
6. **Pressure builds** on stagnation -> triggers mutation
7. **Mutator** writes Python: `patch_file("path", "new code")` -> evolves prompts/plugins
8. **Satisfied state** -> reduced metabolism when goal verified (not death, dormancy)

## Key Design Principles

1. **Everything is Python** — LLMs output Python. No JSON schemas. No DSLs.
2. **Never exit** — Satisfied state is dormancy, not death.
3. **Unconstrained** — No guardrails on what code the organism can write. Self-regulation via pressure.
4. **Prompts are DNA** — They evolve under pressure via mutator crossover.
5. **Python writes Python** — The mutator rewrites its own code. Turtles all the way down.

## Tools

### bench.py — LLM Benchmark (30 scenarios)
```powershell
python bench.py --list                    # List scenarios
python bench.py --concurrent 5            # Run all parallel
python bench.py --temperature 0.5         # Test different params
```

### replay.py — Session Replay
```powershell
python replay.py                          # Browse latest session
python replay.py sessions\20260615_134357  # Specific session
# Controls: arrows=navigate, SPACE=re-fire, s=save, q=quit
```

## File Structure

```
main.py      Single worker entry point
engine.py    Organism loop (plan->act->verify->fission)
reactor.py   Multi-process supervisor + MAP-Elites
tui.py       Terminal dashboard
agents.py    All agent classes
comms.py     Bus/blackboard communication
llm.py       LM Studio client + request tracing
config.py    Configuration + model profiles
desktop.py   Windows UI Automation (observe + control)
actions.py   Python execution sandbox + desktop helpers
log.py       Event logging
bench.py     LLM benchmark tool
replay.py    Session replay tool
plugins/     Hot-loaded plugins (def run(board))
prompts/     Prompt DNA (evolves under pressure)
```

## License

MIT
