# endgame-ai

A **5-slot AI colony** on your machine: parallel persona processes coordinated through a shared blackboard, steered by deterministic math, with a local LLM used only when planning or verification is needed.

**Active branch:** `grok-dev` — Colony Alpha (stable slots, blackboard v1, MoE routing, orchestrator).

```bash
git checkout grok-dev
python tui.py --model-profile nemotron
```

| Profile | Use |
|---------|-----|
| `nemotron` | Reasoning model, 1 concurrent LLM (recommended) |
| `gemma` | Faster, 2 concurrent |
| `--backend acp` | Sequential WSL/Kiro backend |

**Controls:** Space = pause/unpause · `q` = quit · `@persona message` = talk to the colony

---

## What you see

- **5 slots** — each is an OS process running one persona
- **Slot 1** — `comms_operator` routes work every 20s (no LLM for routing)
- **Slots 2–5** — workers stay **idle until routed** via the blackboard
- **TUI** — 45-line display; pipeline bars per slot: `S·P·A·V·F`

```
scheduler → planner → actor → verifier → fission_judge   (inside each persona)
```

The LLM is not the organism. It is a subroutine inside a Python control loop.

---

## Priority

| Level | Name | When |
|-------|------|------|
| 3 | HUMAN | You typed a message |
| 2 | CRITICAL | MoE escalation (stuck worker) |
| 1 | NORMAL | comms_operator assigned work |
| 0 | MAINTENANCE | Idle until inbox |

---

## Before you run

1. LM Studio with nemotron loaded at `localhost:1234`, or use `--backend acp`
2. Close any stale `tui.py` / `reactor.py` processes
3. `runtime/comms/` is wiped on TUI start (session logs in `sessions/` are kept)

### Quick sanity check

```bash
python tui.py --model-profile nemotron
```

Expect: `5/5 slots` in the header, no respawn every 5s, one `moe.route` in slot-1 events after ~20s.

```bash
python comms.py state    # structured telemetry per persona
```

Human interrupt test: `@implementor read config.py and summarize`

Automated smoke test: `python run_test.py 120`

---

## Branches

| Branch | Role |
|--------|------|
| `grok-dev` | **Active** — colony rewrite, bus v1, MoE loop |
| `unify-rewrite` | Architectural base; likely merge target later |
| `main` | Separate lineage (organism M4, self-rewrite proven) — parallel species, not parent of grok-dev |

---

## Docs in this repo

| File | Audience |
|------|----------|
| `README.md` | You — quick start and orientation |
| `KNOWLEDGE.md` | Architecture, blackboard protocol, research map |
| `AGENTS.md` | AI coding tools (Codex, Cursor, Grok) — session handover rules |

Session notes and vision docs live outside the repo (Grok memory index), not in git.

---

## Core files

```
tui.py       — display and human input
reactor.py   — 5 slots, spawn/kill/reassign
main.py      — persona entry point
engine.py    — pipeline, pressure math, MoE routing
agents.py    — scheduler / planner / actor / verifier
comms.py     — blackboard v1
config.py    — slots, personas, thresholds
llm.py       — LM Studio + ACP
log.py       — session JSONL under sessions/
prompts/     — planner, verifier, personalities
schemas/     — JSON schemas (bus, route, telemetry, planner, …)
plugins/     — hot-swappable (comms_beacon, …)
```

Deep reference: `KNOWLEDGE.md`. AI continuation: `AGENTS.md`.