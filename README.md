# endgame-ai

Five Python processes, one local model (nemotron-3-nano-4B), a blackboard, pressure math, and a breeding reactor.

## Branches (file count matters)

| Branch | Files | Lines | What it is |
|--------|-------|-------|------------|
| **`bare-metal`** | **42** | **~7k** | Current colony — MoE, bus, breeding |
| `unify-rewrite` | 49 | ~8k+ | Backup before bare-metal strip |
| `main` | 24 | ~3.6k | **Legacy** single-process (no reactor/comms/breed) |

```bash
git checkout bare-metal
```

`main` is smaller on disk because it is an **older, simpler organism** — not a subset of bare-metal.

## Run

```bash
python tui.py "Your long-term goal in one sentence"
```

**Requires:** LM Studio at `http://localhost:1234`, nemotron-3-nano-4B.

| Flag | Effect |
|------|--------|
| `--safe` | Disable default GUI + unconstrained |
| `--model-profile nemotron` | Single-flight MC=1 |
| `--backend acp` | ACP backend (needs `acp_client.py`) |

Each slot is a `config.Personality` instance (name + slot + mission). TUI Enter = pri=3 override.

## Architecture (42 files)

```text
tui.py → reactor.py → main.py × 5 (Personality per slot)
Pipeline: scheduler → planner → actor → verifier → fission_judge → reflector → mutator
Bus: comms.py (includes actor sandbox + GUI toggle)
```

18 Python modules · 10 prompts · 5 schemas · 8 meta/docs.

## Smoke tests

```bash
python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py llm.py
python agents.py --fission-smoke
python reactor.py --archive-smoke
```

## Docs

| File | Audience |
|------|----------|
| `README.md` | Humans |
| `OBSERVATIONS.md` | AI — § COLD-START HANDOVER |
| `RULES.md` | Git contract + 42-file inventory |

Fresh disk: `python -c "import log; log.cleanup_runtime(deep=True)"`