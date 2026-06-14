# RULES.md — Repository contract

Every commit must respect this file. No exceptions.

## What git tracks (only)

| Category | Paths |
|----------|--------|
| **Run** | `*.py`, `prompts/**`, `schemas/**`, `plugins/**`, `.env` |
| **Humans** | `README.md` |
| **AI** | `OBSERVATIONS.md` (handover prompt + methodology + session log) |
| **Project** | `LICENSE`, `CONTRIBUTING.md`, `RULES.md` (this file), `.gitignore`, `.gitattributes` |

**Never commit:** `runtime/`, `sessions/`, event JSONL, golden HTML, run artifacts (`benchmark.txt`, `Colony_Demo/`, snapshots, breed archives). Archive locally if needed — not in git.

## Required updates on every commit

| If you changed… | Update before commit |
|-----------------|----------------------|
| Behavior, wiring, CLI, defaults | `OBSERVATIONS.md` § COLD-START HANDOVER (HEAD SHA, priorities, run command) |
| How humans start the colony | `README.md` |
| What may be committed / process | `RULES.md` |
| New session evidence | `OBSERVATIONS.md` § Session log (append one row + short notes) |

If a commit changes code but not the handover when the handover is stale, **the commit is incomplete**.

## Code rules

1. **No new `.py` files** — extend existing modules.
2. **Bus-only coordination** — personas use `comms.py`, never direct calls.
3. **`python -m py_compile`** on touched Python before push.
4. **Do not disable** verifier / fission fail-closed gates for demos.
5. **Innovate forward** — no golden-run fallbacks, tags, or forensic archives in the repo.

## Fresh start (local disk)

```bash
python -c "import log; log.cleanup_runtime(deep=True)"
```

Then:

```bash
python tui.py "your long-term goal"
```

LM Studio with nemotron-3-nano-4B at `localhost:1234`.