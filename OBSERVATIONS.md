# OBSERVATIONS.md

**AI-facing doc (git-tracked).** § COLD-START HANDOVER is the only briefing for tools with zero context. Update it on every behavior-changing commit (see `RULES.md`).

Humans: read `README.md`.

---

## COLD-START HANDOVER PROMPT

**Last updated:** 2026-06-14 (flush) · **Branch:** `unify-rewrite` · **HEAD:** `398afa5`

Copy the fenced block into any new AI session.

```text
PROJECT: endgame-ai — self-evolving multi-agent colony on consumer hardware.
Branch: unify-rewrite. Model: nvidia-nemotron-3-nano-4b, profile nemotron_parallel (LM Studio MC=5).

READ ORDER (zero prior context):
1. RULES.md — what git tracks, required doc updates per commit
2. OBSERVATIONS.md — this prompt + methodology + session log below
3. README.md — human run command
4. Code: comms.py, engine.py, agents.py, reactor.py, tui.py, config.py

ORGANISM (deterministic, not the LLM):
  pressure → MoE (s1) → blackboard → scheduler → planner → actor → verifier
  → fission_judge → reflector → mutator → breeder (reactor.py)

RUN:
  python tui.py "long-term goal sentence"
  python tui.py --safe "goal"   # guarded mode
  LM Studio localhost:1234, nemotron-3-nano-4B loaded.
  Fresh disk: python -c "import log; log.cleanup_runtime(deep=True)"

GOALS (Codex /goal):
  CLI trailing words → LONG_TERM_GOAL (runtime/colony_goal.txt, gitignored).
  MoE assigns work toward it. TUI Enter = pri=3 ACTIVE_TASK override until verified.
  No goal → maintenance audits → idle.

ARCHITECTURE: 5 slots — comms_operator + 4 workers. Bus-only via comms.py.

HARD RULES (RULES.md):
  - No new .py files
  - Never commit runtime/, sessions/, golden artifacts
  - py_compile changed Python; do not weaken verifier/fission gates

KEY FILES:
  Bus: comms.py (inbox_match, apply_interrupt, set_colony_goal)
  Loop: engine.py, agents.py, prompts/*.txt, schemas/*.json
  Ops: tui.py, reactor.py, config.py
  Breeder: reactor.py, plugins/fission_log.py (protected)

SMOKE (no LLM):
  python agents.py --fission-smoke
  python agents.py --git-verify-smoke
  python reactor.py --archive-smoke
  python reactor.py --breed-improve-smoke

STATE: Flushed — runtime/sessions cleared locally; git slim (52 files). Ready to run.
CURRENT PRIORITY:
  1. python tui.py "<goal>" with LM Studio live
  2. Append first post-slim session row to § Session log
  3. Prove breed.improve + restart survival

NOT IN GIT: runtime/, sessions/*.jsonl — keep locally only.
```

---

## Methodology

### Evidence (local, gitignored)

1. `sessions/<id>/events-reactor.jsonl` — breeder
2. `sessions/<id>/events-child-s1..s5.jsonl` — workers
3. `runtime/comms/messages.json` — blackboard
4. `runtime/breed_archive.json` — survivors

### Poll protocol

| Situation | Wait |
|-----------|------|
| Simple file task | 30–45s |
| Multi-step / git | 90–120s |
| Planner LLM active | ≥45s |
| Stuck loop | 3–5 min or new task |

### Session close (append to log below)

One table row + 5–15 lines: what worked, what failed, files to change together.

### Human / bus rules

- TUI posts `from=human`, pri=3 — no `@human` in body.
- pri=3 delivers without `@colony` (`comms.inbox_match`).
- Declines use pri=0 + `human_ack` (not pri=3).

### Wiring reference (current)

| Component | Role |
|-----------|------|
| `comms.apply_interrupt` | Single interrupt path |
| `comms.set_colony_goal` | Codex-style persistent goal |
| `engine._moe_route` | Routes `maintenance_goal_text()` |
| `_restore_after_human_task` | After human verify → idle → MoE |

---

## Session log

Append only. No golden archives in git — summaries live here.

| Session | Duration | Events | Headline | Notes |
|---------|----------|--------|----------|-------|
| *(flush 2026-06-14)* | — | — | Repo slimmed `3a30c9a` | Golden artifacts removed from git; RULES.md live |
| *(next run)* | | | | |

### Lessons (compressed, no forensic dumps)

- Colony survives long runs with MoE yield during human pri=3.
- Post-FR wiring: inbox_match, decline pri=0, git verify smoke, progress on TUI.
- Unproven: MAP-Elites convergence, restart-persistent elites.
- Operator mode: default GUI + unconstrained; `--safe` for guarded runs.

---

*Update § COLD-START HANDOVER HEAD on every commit. See RULES.md.*