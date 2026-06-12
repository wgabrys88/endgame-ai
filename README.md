# endgame-ai

A self-replicating agentic system modeled as a nuclear fission reactor.

## Architecture

```
reactor.py          Control room. Maintains criticality k~1.0.
main.py             Fuel rod. Single agent lifecycle.
agents.py           Phase scheduler (plan → exec → verify → mutate).
engine.py           Tick loop connecting phases.
config.py           All constants and tuning.
llm.py              LM Studio API (schema-enforced JSON).
plugins/            Fission products. Written BY agents FOR agents.
prompts/            Isotope personalities. Drive emergent behavior.
schemas/            Neutron cross-sections. Constrain output shape.
```

## How it works

The reactor spawns agents with personalities, not tasks. Each agent:

1. Receives a personality (prompt) and optional vague goal
2. Plans its own actions based on who it IS
3. Executes Python via `exec` — errors are free AST feedback
4. Verifies results, achieves fission (goal completion)
5. Mutates — writes plugins that improve the colony

The reactor measures criticality (fissions/deaths) and maintains population:
- Subcritical → spawn more agents
- Supercritical → absorb weakest
- Stable → let them run

## Running

```bash
# Single agent
python main.py "exec print('hello')" --backend lmstudio

# Full reactor (6 remote + 2 local)
ENDGAME_LMS_HOST="http://192.168.16.31:1234" python reactor.py
```

Requires LM Studio running at localhost:1234 (or custom host via env var).

## Key principles

- Zero pip dependencies (stdlib + ctypes only)
- Small models learn by EXAMPLE not rules
- Math SERVES the model (translates to plain language)
- Personality IS the goal — agents pursue what they ARE
- Python exec errors = free feedback (no LLM cost)
- Plugins are hot-loaded every cycle — colony self-modifies

## License

MIT
