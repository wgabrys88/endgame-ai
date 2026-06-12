# Contributing

`endgame-ai` on `colony/dev` is a **Windows breeding reactor** — six parallel LLM agents with personalities, shared comms, plugin hot-swap, and a dedicated GUI slot (@GUI).

## Baseline

- Python 3.13+
- Windows 10/11
- **Zero pip dependencies** (stdlib + ctypes)
- LM Studio with a loaded model (Gemma 4B tested)
- Pyright clean target when types change

## Before you commit

1. `git status` — no runtime artifacts, no personal paths in tracked files.
2. `python -c "import log; log.cleanup_runtime()"` — fresh runtime seed.
3. `python -m compileall -q .`
4. Read `AGENTS.md` and `GROK.md` if you touch architecture.

## What must stay out of git

See `.gitignore` (whitelist: `!*.py`, `!prompts/**`, `!schemas/**`, `!plugins/**`, docs). Runtime is bootstrapped by `log.cleanup_runtime()` when TUI starts:

- `runtime/` (includes `comms/messages.json`, `events_bus.jsonl`, `inject.jsonl`)
- `events*.jsonl`, `snapshot.json`, `lessons.jsonl`
- `pause`, `gui_mode`, `*.lock`, `tmp*.py`, `report.md` (repo root), `session-log.md`

## Code conventions

- Constants in `config.py`
- Personalities in `prompts/personalities/` — mission text, ASCII only
- Planner output: strict JSON + Python in `sequence[].code`
- Plugins: `def run(board)` in `plugins/`, py_compile safe
- No personal identifiers in source

## Branches

| Branch | Use |
|--------|-----|
| `colony/dev` | Agent autonomous commits |
| `reactor-personalities` | Human + merged work (sync with colony/dev) |
| `main` | Stable single-agent release |

When fixing colony behavior, push to **both** `colony/dev` and `reactor-personalities` unless told otherwise.

## Validation

```powershell
python -m compileall -q .
python tui.py
```

Press Space for live run. Confirm agents plan, execute, and fission in TUI.

Optional env:

```powershell
$env:ENDGAME_LMS_HOSTS = "http://localhost:1234,http://remote:1234"
$env:ENDGAME_LMS_MODEL = "gemma"
```

## Pull requests

- Say what changed and how you verified it (TUI, logs, or compileall).
- Do not add pip dependencies.
- Do not commit runtime data.
- Update `README.md` / `AGENTS.md` when behavior changes.