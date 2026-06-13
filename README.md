# endgame-ai — self-reviewing breeding reactor

**Six AI personas running their own agent pipeline in parallel.** Each persona plans, executes Python, verifies results, and earns fission credits — while a live TUI shows colony health through spectrograms and a message bus console.

```bash
python tui.py --model-profile nemotron    # Nemotron (reasoning model)
python tui.py --model-profile gemma       # Gemma (fast, creative)
python tui.py                             # auto-detect from LM Studio
python tui.py --backend acp              # ACP/Kiro backend (sequential)
```

Starts **paused**. **Space** = LIVE. **q** = stop.

Requires [LM Studio](https://lmstudio.ai/) with any loaded model, or ACP (`kiro-cli acp` via WSL).

---

## Architecture

A reactor core with six fuel rods (personas). Each persona runs the same agent pipeline: **plan → run Python → verify → fission judge → fission**. Finished work earns **fission** — measurable colony progress.

### Terminology
- **Persona** = named process (architect, implementor, reviewer, comms_operator, devops, quality_critic)
- **Agent** = pipeline stage inside a persona (scheduler, planner, actor, verifier, reflector, mutator)

### Math Engine (threaded, per persona)
- **Stagnation** — ramps 0→1 based on lack of progress + failures
- **Lorenz attractor** — chaotic exploration signal; wing-crossing triggers replanning
- **PID controller** — integrates stagnation, triggers reflection/mutation

### Event-Driven Colony
- `comms_operator` is always active — it routes work via @mentions
- Other 5 personas run one cycle on boot, then **sleep** until @mentioned
- Sleeping personas poll the bus every 10s — zero LLM calls while idle
- LM Studio handles parallel requests natively — no staggering needed

### Persona Roster

| Slot | Persona | Mission |
|------|---------|---------|
| n1 | architect | Design refactors, plan code structure changes |
| n2 | implementor | Execute code modifications, fix bugs |
| n3 | reviewer | Review changes, catch regressions |
| n4 | comms_operator | Route work via bus, post status |
| n5 | devops | Git ops, branch management |
| n6 | quality_critic | Audit health, enforce standards |

---

## Model Profiles

Full hyperparameter sets per local model. Selected via `--model-profile`:

| Profile | Temperature | Top-K | Repeat Penalty | Planner Budget |
|---------|-------------|-------|----------------|----------------|
| nemotron | 1.0 | 20 | 1.05 | 8192 tokens |
| gemma | 0.6 | 40 | 1.07 | 1200 tokens |

Auto-detected from the LM Studio model name if not specified. Add more profiles in `config.py MODEL_PROFILES`.

---

## Message Bus

The bus (`runtime/comms/messages.json`) is the colony's nervous system:
- `@mention` = ping — activates the target persona
- Human posts via TUI input line
- `comms_operator` routes work to specialist personas

---

## Backends

### LM Studio (default)
- 6 parallel personas, each hitting the local HTTP API
- Set hosts in `.env`: `ENDGAME_LMS_HOSTS=http://host:1234`
- Tested with Nemotron 4B, Gemma 4B

### ACP (sequential)
- All 6 personas share one `kiro-cli acp` session via WSL
- Cross-process file lock ensures one call at a time
- `python tui.py --backend acp`

---

## TUI

Fixed 45-line layout showing:
- Per-persona: active agent, stagnation/energy/PID bars + spectrograms, recent events
- Chat panel: human and agent @mentions
- Events panel: LLM retries, fissions, errors

---

## Files

```
main.py          — entry point (single persona process)
reactor.py       — spawns 6 personas, monitors liveness, respawns dead
tui.py           — fixed 45-line TUI (launches reactor)
engine.py        — agent pipeline loop, plugin hot-swap, snapshots
agents.py        — all agents: plan/act/verify/reflect/mutate/math
llm.py           — LM Studio + ACP backends with retries
comms.py         — message bus: post/read/pending/@mention
log.py           — append-only JSONL events, bus mirroring
config.py        — all tunables, paths, roster, model profiles
actions.py       — Python subprocess runner
acp_client.py    — kiro-cli ACP JSON-RPC session manager
plugins/         — hot-swappable colony behaviors
prompts/         — system prompts + personality files
schemas/         — JSON schemas for structured LLM output
run_test.py      — test harness with timeout + kill
```

---

## Quick Start

```bash
# 1. Start LM Studio, load a model (Nemotron recommended)
# 2. Run
python tui.py --model-profile nemotron
# 3. Press Space to go LIVE
# 4. Watch personas work. Type @mentions to interact.
# 5. q to stop
```

---

## Self-Evolution

Personas mutate their own prompts:
- **Reflector** appends `RULE:` lines to `prompts/planner.txt` (max 6)
- **Personality evolution** appends `EVOLVE:` lines to personality files (max 4)
- **Mutator** writes plugins under `plugins/` to fix runtime errors
