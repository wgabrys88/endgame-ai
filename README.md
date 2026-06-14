# endgame-ai

A **5-slot AI colony** on your machine: parallel persona processes coordinated through a shared blackboard, steered by deterministic math, with a local LLM used only when planning or verification is needed.

**Active branch:** `codex-dev` — Colony Alpha + AgentBreeder scaffold (~82% vision). `grok-dev` is 13 commits behind; merge pending human approval.

```bash
git checkout codex-dev
python tui.py --model-profile nemotron
```

| Profile | Use |
|---------|-----|
| `nemotron` | Reasoning model, 1 concurrent LLM (recommended) |
| `gemma` | Faster, 2 concurrent |
| `--backend acp` | Sequential WSL/Kiro backend |
| `--gui` | Enable desktop/GUI automation (default: blocked) |

**Controls:** Space = pause/unpause · `g` = toggle GUI/safe mode · `q` = quit · `@persona message` = talk to the colony

---

## What you see

- **5 slots** — each is an OS process running one persona
- **Slot 1** — `comms_operator` routes work every 20s (no LLM for routing)
- **Slots 2–5** — workers stay **idle until routed** via the blackboard
- **TUI** — 45-line display; pipeline bars per slot: `S·P·A·V·F`; header shows `GUI` or `safe`

```
scheduler → planner → actor → verifier → fission_judge → reflector → mutator
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
python comms.py state      # structured telemetry per persona
python comms.py breeder    # evolve / breed.* evidence from observation bus
```

Human interrupt test (file — should confirm):

```
@implementor create hello.txt with hello world
```

GUI tasks in **safe mode** (default) are declined: `@devops open notepad` posts "not supported" — no Notepad windows.

For desktop automation (self-evolving organism mode):

```bash
python tui.py --model-profile nemotron --gui
```

Or press `g` during a run to toggle. Header shows `GUI` when safeguards are off.

Automated smoke test: `python run_test.py 120`

LLM tuning benchmark: `python llm.py bench` (compares legacy vs optimized nemotron)

**LM Studio:** load nemotron with Max Concurrent Predictions **1** and Unified KV Cache **on** — the colony also uses a cross-process lock so only one slot hits the server at a time.

**Logs:** Session JSONL (`sessions/`) includes `moe.route` + `pressure` every ~20s by design. After 6+ minutes you should see `reflect`, `mutate`, and `evolve` on the bus. See `KNOWLEDGE.md` log tiers.

---

## Branches

| Branch | Role |
|--------|------|
| `codex-dev` | **Active** — breeding loop, human file fix, breeder audit |
| `grok-dev` | Grok agent branch (behind codex-dev) |
| `unify-rewrite` | Integration trunk |
| `main` | Separate lineage (organism M4) — parallel species |

---

## Docs in this repo

| File | Audience |
|------|----------|
| `README.md` | You — quick start and orientation |
| `KNOWLEDGE.md` | Architecture, blackboard protocol, research map |
| `AGENTS.md` | AI coding tools — session handover, test results, GOAL |

Local handover (not in git policy): `Codex-log.md`, `ENDGAME_VISION.html`

---

## Core files

```
tui.py       — display and human input (--gui)
reactor.py   — 5 slots, spawn/kill/reassign, breeding reactor
main.py      — persona entry point
engine.py    — pipeline, pressure math, MoE routing
agents.py    — scheduler / planner / actor / verifier / reflector / mutator
comms.py     — blackboard v1 + breeder audit CLI
config.py    — slots, personas, thresholds, breeding knobs
llm.py       — LM Studio + ACP
log.py       — session JSONL under sessions/
prompts/     — planner, verifier, reflector, mutator, personalities
schemas/     — JSON schemas (bus, route, telemetry, planner, …)
plugins/     — hot-swappable (comms_beacon, …)
```

Deep reference: `KNOWLEDGE.md`. AI continuation: `AGENTS.md`.