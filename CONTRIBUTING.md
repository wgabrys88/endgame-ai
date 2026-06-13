# Contributing

## Baseline

- Python 3.13+, Windows 10/11
- **Zero pip dependencies** (stdlib + ctypes)
- LM Studio with a loaded model (Gemma 4B tested)

## Before you commit

1. `python -m compileall -q .`
2. No runtime artifacts in git (see `.gitignore`)

## Branches

| Branch | Use |
|--------|-----|
| `colony/dev` | Agent autonomous commits |
| `reactor-personalities` | Human + merged work |
| `main` | Stable release |

## Validation

```powershell
python -m compileall -q .
python tui.py
```

Space for live. Confirm agents plan, execute, and fission in TUI.
