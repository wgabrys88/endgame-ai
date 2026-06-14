# RULES.md — Repository contract

**Branches:**
- **`bare-metal`** — minimal runnable colony (**42 files**, ~7k lines). Forward dev here.
- `unify-rewrite` — backup before bare-metal file strip (49 files).
- `main` — **legacy single-process** (24 files, ~3.6k lines). Different architecture — not compatible.
- **Milestone tag:** `dev-milestone-20260614` → `5ca4ee8`.

Every commit must respect this file. No exceptions.

## What git tracks (only)

| Category | Paths |
|----------|--------|
| **Run** | `*.py`, `prompts/**`, `schemas/**`, `plugins/**`, `.env` |
| **Humans** | `README.md` |
| **AI** | `OBSERVATIONS.md` |
| **Project** | `LICENSE`, `CONTRIBUTING.md`, `RULES.md`, `.gitignore`, `.gitattributes` |

**Never commit:** `runtime/`, `sessions/`, golden artifacts, benchmark outputs.

## Minimal core (`bare-metal` = 42 files, ~6971 lines)

| Layer | # | Files |
|-------|---|-------|
| **Entry** | 3 | `tui.py`, `reactor.py`, `main.py` |
| **Pipeline** | 3 | `engine.py`, `agents.py`, `comms.py` |
| **Infra** | 4 | `config.py`, `log.py`, `llm.py`, `python_code.py` |
| **Desktop/GUI** | 3 | `actions.py`, `observer.py`, `win32.py` |
| **Backend** | 1 | `acp_client.py` (optional `--backend acp`) |
| **Plugins** | 4 | all under `plugins/` |
| **Prompts** | 10 | 5 roles + 5 personalities |
| **Schemas** | 5 | planner, verifier, reflector, mutator, fission_judge |
| **Meta** | 8 | dotfiles + LICENSE + CONTRIBUTING + README + OBSERVATIONS + RULES |

**Identity model:** `config.Personality` + `engine.AgentContext` — one object per `main.py` process. `reactor.Breeder` encapsulates MAP-Elites state. `comms.format_phase_brief` shared with TUI.

**Stripped (not missing — merged or deleted):**
- `lessons.py`, `run_test.py`, unused schemas — dead files
- `colony_env.py` → merged into `comms.py` (actor sandbox API)
- `desktop.py` → merged into `actions.py`
- `llm.py` benchmark CLI (~970 lines) — runtime-only LLM path remains

**Line bloat still in repo (next targets, no new files):**
- `agents.py` ~1524 lines — split internally: validators, mutation, smokes
- `reactor.py` ~950 lines — `Breeder` class, smoke relocation
- Duplicate `_brief` in `tui.py` + `comms.py`

## Required updates on every commit

| If you changed… | Update |
|-----------------|--------|
| Behavior, wiring, CLI | `OBSERVATIONS.md` § COLD-START (HEAD SHA, file count, priorities) |
| Human run command | `README.md` |
| Git contract | `RULES.md` |
| Session evidence | `OBSERVATIONS.md` § Session log |

## Code rules

1. **No new `.py` files** — extend existing modules; merge duplicates inward.
2. **Bus-only coordination** — `comms.py`.
3. **`python -m py_compile`** on touched Python before push.
4. **Do not disable** verifier / fission gates.
5. **Personality = object** — use `config.Personality`, not scattered env reads in new code.

## Fresh start

```bash
python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py "your long-term goal"
```