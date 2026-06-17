# endgame-ai v2

Minimal OOP rewrite. Single slot architecture (implementor slot pattern).

## Architecture

```
User goal --> Slot
               |
               +-- Planner (creates tasks)
               +-- Actor (executes tasks via GUI or subprocess)
               +-- Verifier (judges completion from evidence)
               +-- Mutator (tunes prompts under pressure)
               |
               Bus (shared blackboard)
```

## Run

```powershell
python tui.py "open notepad and type hello"
python tui.py --no-desktop "exec: print('hello')"
python tui.py --host http://192.168.1.5:1234 --temperature 0.2 "goal"
```

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| goal | (none) | Initial goal text |
| --host | http://localhost:1234 | LM Studio URL |
| --timeout | 600 | LLM request timeout seconds |
| --temperature | 0.12 | LLM temperature |
| --max-tokens | 1536 | LLM max output tokens |
| --no-desktop | false | Disable GUI observation |
| --workspace | parent dir | Working directory for exec |
| --bus-file | (none) | Persist bus to JSONL file |

## Files (1190 LOC)

| File | LOC | Purpose |
|------|-----|---------|
| tui.py | 208 | Entry point, TUI display, CLI args |
| slot.py | 285 | Planner/Actor/Verifier/Mutator circuits |
| desktop.py | 428 | Mouse hover probe observer, GUI actions |
| llm.py | 112 | LM Studio client |
| actions.py | 82 | Verb executor (click/write/press/hotkey/scroll/focus) |
| bus.py | 75 | Shared blackboard with optional persistence |

## Adding More Slots

The architecture is designed for multi-slot expansion:

```python
from llm import LLMClient
from bus import Bus
from slot import Slot

bus = Bus()
llm = LLMClient(host="http://localhost:1234")

architect = Slot(llm=llm, bus=bus, prompts_dir=Path("prompts/architect"), workspace=ws)
implementor = Slot(llm=llm, bus=bus, prompts_dir=Path("prompts/implementor"), workspace=ws)
reviewer = Slot(llm=llm, bus=bus, prompts_dir=Path("prompts/reviewer"), workspace=ws)

# All slots share the same bus - they see each other's records
architect.set_goal("design the solution")
implementor.set_goal("implement it")
reviewer.set_goal("verify quality")
```

Each slot gets its own prompts directory. The Bus is the shared communication layer.
A comms_operator planner can read the bus and route goals to slots.

## Design Decisions

- No env vars. All config via CLI args.
- No colony/reactor/breeder complexity. Single slot does the work.
- Mouse hover probe only. No UIA tree walking (simpler, faster, sufficient).
- OOP throughout. Every component is unit-testable in isolation.
- Prompts are plain .txt files. Mutator can patch them.
- Bus records are the universal communication format.
