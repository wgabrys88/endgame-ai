# RULES.md — Repository contract

**Branches:**
- `unify-rewrite` — full development history (49 files at last sync).
- `bare-metal` — **minimal runnable core only** (44 tracked files). Use this for forward dev when avoiding bloat.
- **Milestone tag:** `dev-milestone-20260614` → `5ca4ee8` (`git checkout dev-milestone-20260614`).

Every commit must respect this file. No exceptions.

## What git tracks (only)

| Category | Paths |
|----------|--------|
| **Run** | `*.py`, `prompts/**`, `schemas/**`, `plugins/**`, `.env` |
| **Humans** | `README.md` |
| **AI** | `OBSERVATIONS.md` (handover prompt + methodology + session log) |
| **Project** | `LICENSE`, `CONTRIBUTING.md`, `RULES.md` (this file), `.gitignore`, `.gitattributes` |

**Never commit:** `runtime/`, `sessions/`, event JSONL, golden HTML, run artifacts (`benchmark.txt`, `Colony_Demo/`, snapshots, breed archives). Archive locally if needed — not in git.

## Minimal core (`bare-metal` = 44 files)

Everything below is required for `python tui.py "goal"` to run. Nothing else.

| Layer | Count | Files |
|-------|-------|-------|
| **Entry** | 3 | `tui.py`, `reactor.py`, `main.py` |
| **Pipeline** | 3 | `engine.py`, `agents.py`, `comms.py` |
| **Infra** | 4 | `config.py`, `log.py`, `llm.py`, `python_code.py` |
| **Desktop/GUI** | 5 | `colony_env.py`, `actions.py`, `desktop.py`, `observer.py`, `win32.py` |
| **Backend** | 1 | `acp_client.py` (optional `--backend acp`) |
| **Plugins** | 4 | `comms_beacon.py`, `fission_log.py`, `lessons_decay.py`, `web_sentinel.py` |
| **Prompts** | 10 | `planner`, `verifier`, `reflector`, `mutator`, `fission_judge` + 5 `personalities/*` |
| **Schemas** | 5 | matching the five LLM roles above |
| **Meta** | 8 | `.env`, `.gitignore`, `.gitattributes`, `LICENSE`, `CONTRIBUTING.md`, `README.md`, `OBSERVATIONS.md`, `RULES.md` |
| **Total** | **44** | |

**Removed on `bare-metal` (dead weight, zero import references):**

| File | Why removed |
|------|-------------|
| `lessons.py` | Never imported; `lessons_decay` plugin is separate |
| `run_test.py` | Legacy harness; production path is `tui.py` → `reactor.py` |
| `schemas/bus_v1.json` | Not loaded by `_load_schema()` |
| `schemas/route.json` | Not loaded |
| `schemas/telemetry.json` | Not loaded (telemetry is comms protocol, not this schema) |

**Not in git but on disk (mess):** `runtime/`, `sessions/`, `pause`, `gui_mode`, `unconstrained_mode`, `__pycache__/`, local markdown notes. Run `log.cleanup_runtime(deep=True)` before sessions.

## Required updates on every commit

| If you changed… | Update before commit |
|-----------------|----------------------|
| Behavior, wiring, CLI, defaults | `OBSERVATIONS.md` § COLD-START HANDOVER (HEAD SHA, branch, priorities) |
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