# Contributing

MIT License — see [LICENSE](LICENSE). Copyright (c) 2026 wgabrys88.

## Branch

Work on `unify-rewrite` (or successor main). Pull before you start.

## Commit checklist

1. Read [RULES.md](RULES.md) — only tracked files may be staged.
2. Update [OBSERVATIONS.md](OBSERVATIONS.md) § COLD-START HANDOVER if behavior changed.
3. Update [README.md](README.md) if the human run path changed.
4. `python -m py_compile` on changed Python.
5. Smoke: `python agents.py --fission-smoke` when touching pipeline/breeder.

## Docs split

| Audience | File |
|----------|------|
| Humans | `README.md` |
| AI (zero context) | `OBSERVATIONS.md` |
| Git / commit law | `RULES.md` |

Do not add parallel handover files. Session telemetry stays under `sessions/` (gitignored).