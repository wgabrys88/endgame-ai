# endgame-ai

Five Python processes, one local model (nemotron-3-nano-4B), a blackboard, pressure math, and a breeding reactor. The LLM is a subroutine; the deterministic loop is the organism.

Branch: `unify-rewrite`.

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

## Architecture

```text
tui.py → reactor.py (5 slots)
  s1 comms_operator   MoE router
  s2–s5 workers       architect, implementor, reviewer, devops
Pipeline: scheduler → planner → actor → verifier → fission_judge → reflector → mutator
```

## Smoke tests

```bash
python -m py_compile reactor.py agents.py comms.py engine.py tui.py
python agents.py --fission-smoke
python agents.py --git-verify-smoke
python reactor.py --archive-smoke
```

## Docs

| File | For |
|------|-----|
| `README.md` | You (human) |
| `OBSERVATIONS.md` | AI tools — copy § COLD-START HANDOVER into new sessions |
| `RULES.md` | What git tracks + required updates per commit |
| `CONTRIBUTING.md` | License + commit checklist |

Fresh local state: `python -c "import log; log.cleanup_runtime(deep=True)"`