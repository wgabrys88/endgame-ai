# Contributing to endgame-ai

## Colony Rules

1. **Never add new .py files** — modify existing ones only
2. Every change must pass `py_compile`
3. Commit to `colony/{your-role}` branch, not main
4. Push with descriptive commit messages
5. Use the message bus for coordination (@mentions)

## Human Interaction

- Run `python tui.py` and type in the input line
- @mention agents: `@architect please review config.py`
- Press Space to toggle LIVE/PAUSE

## Backends

- Default: LM Studio (any OpenAI-compatible local model)
- Alternative: `python tui.py --backend acp` for Kiro/Claude

## Testing

```bash
python run_test.py 120        # 2-minute test run
python run_test.py 300 acp    # 5-minute ACP test
```
