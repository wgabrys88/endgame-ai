# endgame-ai

A **living digital organism** on your machine — not a chatbot wrapper.

Five persona processes run in parallel, coordinated through a shared blackboard, steered by deterministic math (pressure, MoE routing). A small local LLM is called only when planning or verification is needed. The breeding reactor decides what survives.

**Branch:** `unify-rewrite` @ `2b20732` — Colony Alpha (2026-06-14).

```bash
git checkout unify-rewrite && git pull
python tui.py --model-profile nemotron
```

| Profile | Use |
|---------|-----|
| `nemotron` | Default: 1 concurrent LLM, reasoning on, schema in user message |
| `nemotron_parallel` | Burst: 5 concurrent LLM — LM Studio MC=5 + Unified KV on |
| `gemma` | Faster, 2 concurrent, no thinking |
| `--backend acp` | Sequential WSL/Kiro backend |
| `--gui` | Desktop automation (default: blocked) |

**Controls:** Enter = send · `g` = GUI/safe · Space = pause · `q` = quit · `@persona message` = talk to the colony

---

## The vision (one paragraph)

**Endgame:** Self-evolving colony on consumer hardware. Small models. Real actions. Breeding reactor selects what lives.

You built the same shapes research papers describe — by building under pressure. Math agents are the immune system; the LLM is an expensive subroutine inside a cheap deterministic loop, not the organism itself. Read `ENDGAME_VISION.html` (local, not in git) for the full visual breakdown and paper references.

---

## What you see

- **5 slots** — each is an OS process running one persona
- **Slot 1** — `comms_operator` routes work every 20s (no LLM for routing)
- **Slots 2–5** — workers idle until routed via the blackboard
- **TUI** — pipeline bars per slot: `S·P·A·V·F`; header shows profile + `think=N` on LLM events

```
scheduler → planner → actor → verifier → fission_judge → reflector → mutator
```

---

## Before you run

1. LM Studio with nemotron at `localhost:1234`, or `--backend acp`
2. **Default load:** Max Concurrent Predictions **1**; reasoning stripping **off**
3. Close stale `tui.py` / `reactor.py` processes
4. `runtime/comms/` is wiped on TUI start (`sessions/` kept)

### Quick sanity check

```bash
python tui.py --model-profile nemotron
```

Expect: `5/5 slots`, no respawn loop, `moe.route` on slot 1 after ~20s.

```bash
python comms.py state
python comms.py breeder
```

Human file test:

```
@implementor create hello.txt with hello world
```

Smoke: `python run_test.py 120` · LLM bench: `python llm.py bench`

---

## Branches (remote)

```
unify-rewrite  ← THE work branch (all colony code lives here)
main           ← older label on same history; GitHub default pointer
```

Need a tool-specific session? Branch from `unify-rewrite`:

```bash
git checkout -b my-session
```

---

## Docs

| File | Audience |
|------|----------|
| `README.md` | You — quick start |
| `KNOWLEDGE.md` | Architecture, blackboard, LLM layer |
| `AGENTS.md` | **AI handover** — vision, rules, tests, copy-paste prompt |

Local only (not in git): `ENDGAME_VISION.html`, `Codex-log.md`, `lm-studio-server-log.md`