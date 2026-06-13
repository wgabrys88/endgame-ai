# endgame-ai — self-reviewing breeding reactor

**Six AI agents reviewing and improving their own codebase.** They share one message bus, modify code (never add files), commit to specialized branches, and self-correct through reflection and mutation — while a live spectrogram shows colony health.

```bash
python tui.py                  # LM Studio backend (default)
python tui.py --backend acp    # ACP/Kiro backend (sequential)
```

Starts **paused**. **Space** = LIVE. **q** = stop. **Restart wipes session data.**

Requires [LM Studio](https://lmstudio.ai/) (any model) or ACP (`kiro-cli acp` via WSL).

---

## Architecture

A reactor core with six fuel rods. Each rod: **plan → run Python → verify → fission judge → fission**. Finished work (code modified, git pushed, bus coordination) earns **fission** — measurable colony progress.

### Math Engine (threaded)
- **Stagnation** — ramps 0→1 based on lack of progress + failures
- **Lorenz attractor** — chaotic exploration signal; wing-crossing triggers replanning
- **PID controller** — integrates stagnation, triggers reflection/mutation

### Agent Roster

| Slot | Role | Mission |
|------|------|---------|
| n1 | architect | Design refactors, plan code structure changes |
| n2 | implementor | Execute code modifications, fix bugs |
| n3 | reviewer | Review changes, catch regressions |
| n4 | comms_operator | Route work via bus, post status |
| n5 | devops | Git ops, branch management, deployment |
| n6 | quality_critic | Audit health, enforce standards |

### Colony Rules
1. **Never create new .py files** — modify existing only
2. Each agent commits to `colony/{personality}` branch
3. `py_compile` required before every commit
4. Bus `@mentions` for cross-agent coordination
5. Agents read their own logs and self-correct

---

## Message Bus

The bus (`runtime/comms/messages.json`) is the colony's nervous system:
- `@mention` = ping — activates the target agent
- `bus_post(bus_id(), "colony", "@agent task")` — broadcast
- `bus_request(bus_id(), "agent", "task")` — structured delegation
- Human posts via TUI input line

---

## Backends

### LM Studio (default)
- 6 parallel agents, each hitting the local HTTP API
- Tested with Gemma 4B, works with any OpenAI-compatible model
- Set `ENDGAME_LMS_HOSTS=http://host1:1234,http://host2:1234` for multi-GPU

### ACP (sequential)
- All 6 agents share one `kiro-cli acp` session via WSL
- Cross-process file lock ensures one call at a time
- Agents context-switch like a single-core CPU — slower but works
- `python tui.py --backend acp` or `ENDGAME_BACKEND=acp python reactor.py`

---

## Config Tuning (slow models)

Defaults are tuned for local LLMs with 20-60s response times:
- `MATH_INTERVAL=12s` — gives LLM time to respond between math ticks
- `STAGNATION_FAILURE_WEIGHT=0.12` — single timeout doesn't spike stagnation
- `REFLECT_MIN_INTERVAL=90s` — reflections are expensive LLM calls
- `PID gains lowered` — slow responses don't trigger premature escalation

Stagnation ramp: 1 failure=0.12, 3 failures=0.86, 6 failures=1.0 (maxed)

---

## Files

```
main.py          — entry point (single agent)
reactor.py       — spawns 6 agents, monitors liveness, respawns dead
tui.py           — spectrogram + bus console (launches reactor)
engine.py        — pipeline loop, plugin hot-swap, snapshots
agents.py        — unified protocol: plan/act/verify/reflect/mutate
llm.py           — LM Studio + ACP backends with retries
comms.py         — message bus: post/read/pending/@mention
log.py           — append-only JSONL events, bus mirroring
config.py        — all tunables, paths, roster
actions.py       — Python subprocess runner + desktop verbs
acp_client.py    — kiro-cli ACP JSON-RPC session manager
plugins/         — hot-swappable colony behaviors
prompts/         — system prompts + personalities
schemas/         — JSON schemas for structured LLM output
run_test.py      — test harness with timeout + kill
```

---

## Quick Start

```bash
# 1. Start LM Studio, load any model
# 2. Run
python tui.py
# 3. Press Space to go LIVE
# 4. Watch agents work. Type @mentions to interact.
# 5. q to stop
```

For ACP:
```bash
python tui.py --backend acp
```

---

## Self-Evolution

Agents mutate their own prompts:
- **Reflector** appends `RULE:` lines to `prompts/planner.txt`
- **Personality evolution** appends `EVOLVE:` lines to personality files
- **Mutator** writes plugins under `plugins/` to fix runtime errors
- Rules cap at 6, evolutions cap at 4 — prevents prompt pollution
