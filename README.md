# endgame-ai

A **5-slot AI colony** on your machine: parallel persona processes coordinated through a shared blackboard, steered by deterministic math, with a local LLM used only when planning or verification is needed.

**Active branch:** `grok-dev` — Colony Alpha + AgentBreeder + KV-stable prompts + reasoning capture (2026-06-14).

```bash
git checkout grok-dev
python tui.py --model-profile nemotron
```

| Profile | Use |
|---------|-----|
| `nemotron` | Reasoning model, 1 concurrent LLM, schema in user message (recommended) |
| `nemotron_parallel` | Experimental: 5 concurrent LLM calls — LM Studio MC=5 + Unified KV on |
| `gemma` | Faster, 2 concurrent, no thinking |
| `--backend acp` | Sequential WSL/Kiro backend |
| `--gui` | Desktop/GUI automation (default: blocked) |

**Controls:** Space = pause/unpause · `g` = toggle GUI/safe · `q` = quit · `@persona message` = talk to the colony

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

## Before you run

1. LM Studio with nemotron loaded at `localhost:1234`, or use `--backend acp`
2. **Load settings:** Max Concurrent Predictions **1**; reasoning stripping **off** (so `reasoning_content` appears in API responses)
3. Close stale `tui.py` / `reactor.py` processes
4. `runtime/comms/` is wiped on TUI start (session logs in `sessions/` are kept)

### Quick sanity check

```bash
python tui.py --model-profile nemotron
```

Expect: `5/5 slots`, no 5s respawn loop, `moe.route` in slot-1 events after ~20s.

```bash
python comms.py state
python comms.py breeder
```

Human file test (should confirm):

```
@implementor create hello.txt with hello world
```

GUI in **safe mode** (default): `@devops open notepad` is declined.

```bash
python tui.py --model-profile nemotron --gui   # or press g
```

Smoke: `python run_test.py 120` · LLM bench: `python llm.py bench`

**Reasoning in logs:** `sessions/<timestamp>/events-child-sN.jsonl` — look for `llm.response` and `plan` events with `reasoning` field.

---

## Branches

| Branch | Role |
|--------|------|
| `grok-dev` | **Active** — reasoning capture, KV prompts, breeding loop |
| `codex-dev` | Codex lineage (merged into grok-dev) |
| `open-code-dev` | *Not created yet* — future OpenCode development branch |
| `unify-rewrite` | Integration trunk |
| `main` | Separate lineage (organism M4) |

---

## Docs

| File | Audience |
|------|----------|
| `README.md` | You — quick start |
| `KNOWLEDGE.md` | Architecture, blackboard, LLM/KV layer |
| `AGENTS.md` | AI handover — rules, tests, open questions, next agent |

Local only (not in git): `Codex-log.md`, `ENDGAME_VISION.html`

Grok Build workspace memory: `~/.grok/memory/wgabrys88-endgame-ai/MEMORY.md`