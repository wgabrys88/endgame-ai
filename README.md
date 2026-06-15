# endgame-ai

A living organism that controls your Windows desktop. Not an agent framework — an evolving colony of specialized rods that plans, acts, verifies, and mutates under pressure.

## What It Is

Traditional agents: task → done → exit → dead.
This organism: task → fission → evolve → what next? → never stop.

Five concurrent worker processes coordinate through a shared bus, each with a distinct personality. A MAP-Elites breeder ensures the fittest survive. Prompts are DNA — they evolve under pressure.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  TUI (tui.py) — terminal dashboard                  │
│    └── Reactor (reactor.py) — process supervisor    │
│          ├── Slot 1: comms_operator (thalamus)      │
│          ├── Slot 2: architect (frontal cortex)     │
│          ├── Slot 3: implementor (motor cortex)     │
│          ├── Slot 4: reviewer (quality)             │
│          └── Slot 5: devops (infrastructure)        │
└─────────────────────────────────────────────────────┘
         │                    │
    ┌────▼────┐         ┌────▼────┐
    │ Bus/MoE │         │LM Studio│
    │(comms.py)│        │ (local) │
    └─────────┘         └─────────┘
```

### Biological Mapping

| Component | Biology | File |
|-----------|---------|------|
| Thalamus | All stimuli enter here | comms_operator persona |
| Frontal cortex | Planning, strategy | architect persona |
| Motor cortex | Direct execution | implementor persona |
| Visual cortex | Screen observation | desktop.py |
| Autonomic | Pressure fields | engine.py |
| Immune | Diagnose & patch | reflector + mutator |
| Reproductive | MAP-Elites breeder | reactor.py |
| Endocrine | Satisfied/metabolism | engine.py |

## Requirements

- Windows 11
- Python 3.11+
- [LM Studio](https://lmstudio.ai/) running locally with a model loaded
- Model recommendation: Nemotron or similar reasoning model

## Quick Start

```powershell
# Clone and enter
git clone https://github.com/wgabrys88/endgame-ai.git
cd endgame-ai

# Configure (edit .env if LM Studio is on a different host)
# Default: http://localhost:1234

# Run
python tui.py "Open notepad and write hello" --model-profile nemotron_parallel
```

## Configuration

### `.env`
```
ENDGAME_LMS_HOSTS=http://localhost:1234
```

### Model Profiles

- `nemotron` — Single slot, global lock, safe (default)
- `nemotron_parallel` — 5 concurrent slots, no lock, fast

## File Structure

```
main.py         Entry point for single worker process
engine.py       Main organism loop (plan → act → verify → fission)
reactor.py      Multi-process supervisor, MAP-Elites breeder
tui.py          Terminal dashboard (launches reactor)
agents.py       All agent classes (planner, actor, verifier, etc.)
comms.py        Bus/blackboard communication layer
llm.py          LM Studio HTTP client + ACP backend
config.py       Configuration, model profiles, personas
desktop.py      Windows UI Automation (observe + control)
actions.py      Desktop action execution (click, write, press, etc.)
log.py          Event logging
bench.py        LLM benchmark (30 scenarios)
replay.py       Interactive session replay/comparison tool
plugins/        Hot-swappable plugins (auto-loaded each cycle)
prompts/        Prompt DNA (system prompts for each circuit and persona)
```

## How It Works

1. **Human says goal** → comms_operator decomposes into subtasks
2. **Workers plan** → each rod plans one step through its expertise lens
3. **Actor executes** → desktop automation (click, type, scroll) or Python exec
4. **Verifier confirms** → checks print output against done_when criteria
5. **Fission judge** → awards credit for novel completed work
6. **Pressure builds** → stagnation increases, triggers mutation
7. **Mutator evolves** → patches plugins or rewrites personality prompts
8. **Breeder selects** → MAP-Elites archive preserves fittest DNA
9. **Satisfied state** → reduced metabolism when goal verified (not death)

## Tools

### bench.py — LLM Benchmark

Test 30 real-world scenarios against any model/params:

```powershell
# List all scenarios
python bench.py --list

# Run all with defaults
python bench.py

# Test specific scenarios with custom params
python bench.py --scenarios actor_click_edit,plan_open_notepad --temperature 0.5 --concurrent 3

# Output goes to test.txt
python bench.py --output results_modelA.txt
```

### replay.py — Session Replay

Browse past LLM requests and re-fire them to compare models:

```powershell
# Browse latest session
python replay.py

# Browse specific session
python replay.py sessions\20260615_134357

# Controls:
#   ↑↓     Navigate requests
#   SPACE   Re-fire selected request to LM Studio
#   s       Save comparison to test.txt
#   q       Quit
```

### Plugins

Drop a `.py` file in `plugins/` with `def run(board): ...` — it's hot-loaded every cycle.

```python
# plugins/my_plugin.py
def run(board):
    """Called every engine cycle."""
    if board.get("fissions", 0) > 3:
        print("3 fissions reached!")
```

## Key Design Principles

1. **Never exit** — The organism has no exit conditions. It rests (satisfied state), it never dies.
2. **Pressure drives evolution** — Stagnation → mutation → adaptation. No hand-holding.
3. **Prompts are DNA** — They evolve. The mutator can rewrite personality prompts using elite DNA crossover.
4. **No broadcast** — All messages route through MoE (Mixture of Experts). Targeted, not sprayed.
5. **Fission = reproduction** — Novel completed work earns credit. Repeated work is denied.

## License

MIT
