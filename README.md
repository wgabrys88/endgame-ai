# endgame-ai

Five Python processes, one local model (nemotron-3-nano-4B), a blackboard, pressure math, and a breeding reactor. The LLM is a subroutine; the deterministic loop is the organism.

## Branches

| Branch | Files | Use |
|--------|-------|-----|
| **`bare-metal`** | **44** | Minimal runnable core — recommended for forward dev |
| `unify-rewrite` | 49 | Full history; kept as backup |
| tag `dev-milestone-20260614` | — | Pin to `5ca4ee8` dev baseline |

```bash
git checkout bare-metal    # minimal core
git checkout unify-rewrite # full branch (backup)
```

## Run

```bash
python tui.py "Your long-term goal in one sentence"
```

Examples:

```bash
python tui.py "Evolve plugins until breed.improve survives restart"
python tui.py --safe "Colony maintenance only"
```

**Defaults:** GUI + unconstrained on, profile `nemotron_parallel` (LM Studio MC=5).  
**Requires:** LM Studio at `http://localhost:1234` with nemotron-3-nano-4B loaded.

| Flag | Effect |
|------|--------|
| `--safe` | Disable default GUI + unconstrained |
| `--model-profile nemotron` | Single-flight MC=1 |
| `--backend acp` | ACP backend |

**Goals (Codex-style):** trailing words = persistent long-term goal. TUI Enter = temporary pri=3 task. No goal = maintenance, then idle.

**TUI:** Enter=send, `f`=filter, `g`=GUI toggle, Space=pause, `q`=quit.

## Architecture (minimal 44-file core)

```text
tui.py → reactor.py → main.py × 5 slots
  s1 comms_operator   MoE router
  s2–s5 workers       architect, implementor, reviewer, devops
Pipeline: scheduler → planner → actor → verifier → fission_judge → reflector → mutator
```

20 Python modules (16 root + 4 plugins) · 10 prompts · 5 schemas · 8 meta/docs.

## Smoke tests

```bash
python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py
python agents.py --fission-smoke
python agents.py --git-verify-smoke
python reactor.py --archive-smoke
python reactor.py --breed-improve-smoke
```

## Docs

| File | For |
|------|-----|
| `README.md` | You (human) |
| `OBSERVATIONS.md` | AI tools — copy § COLD-START HANDOVER into new sessions |
| `RULES.md` | What git tracks + 44-file inventory + required updates per commit |
| `CONTRIBUTING.md` | License + commit checklist |

Fresh local state: `python -c "import log; log.cleanup_runtime(deep=True)"`