# Contributing to endgame-ai

## Terminology

- **Persona** — a named process (architect, implementor, reviewer, comms_operator, devops, quality_critic)
- **Agent** — a pipeline stage inside a persona (scheduler, planner, actor, verifier, reflector, mutator)

## Rules

1. **Never add new .py files** — modify existing ones only
2. Every change must pass `py_compile`
3. Use the message bus for coordination (@mentions)
4. No env vars for runtime config — use CLI args

## Running

```bash
python tui.py --model-profile nemotron    # recommended
python tui.py --model-profile gemma       # alternative
python tui.py --backend acp              # Kiro/Claude backend
```

## Human Interaction

- Run `python tui.py` and type in the input line
- @mention personas: `@architect please review config.py`
- Press Space to toggle LIVE/PAUSE
- q to stop

## Testing

```bash
python run_test.py 120        # 2-minute test run
python run_test.py 300 acp    # 5-minute ACP test
```

## Branches

- `unify-rewrite` — canonical development branch
- `main` — stable (updated via PR from unify-rewrite)
