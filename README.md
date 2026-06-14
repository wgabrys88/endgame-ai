# endgame-ai

A living organism on Windows: five reactor rods, one local model (nemotron-3-nano-4B), bus wiring, pressure math, desktop hands, and a breeding reactor. See `RULES.md § VISION`.

## Branches (file count matters)

| Branch | Files | Lines | What it is |
|--------|-------|-------|------------|
| **`bare-metal`** | **42** | **~7k** | Current colony — MoE, bus, breeding |
| `unify-rewrite` | 49 | ~8k+ | Backup before bare-metal strip |
| `main` | 24 | ~3.6k | **Same organism, 1 instance** (GUI actor; no bus/breed) |

```bash
git checkout bare-metal
```

`main` is one instance of the same `main.py` → `engine.run` path. Colony is 5× that plus bus and reactor. Desktop (observer + win32 + actions) is core — see main README vision (M4, exec, see/act/verify).

## Run

```bash
python tui.py "Your long-term goal in one sentence"
```

**Requires:** LM Studio at `http://localhost:1234`, nemotron-3-nano-4B.

| Flag | Effect |
|------|--------|
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
python -m py_compile agents.py reactor.py comms.py engine.py tui.py main.py
```

## Docs

| File | Audience |
|------|----------|
| `README.md` | Humans — how to run |
| `RULES.md` | **Any AI** — § SYSTEM CORE + § VISION (organism, papers, bloat ledger) |
| `OBSERVATIONS.md` | AI — session log + forensics |

Fresh disk: `python -c "import log; log.cleanup_runtime(deep=True)"`