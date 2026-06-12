# endgame-ai

A breeding reactor for AI agents. They evolve by writing code, not by following instructions.

## What this is

A nuclear fission reactor where the fuel rods are LLM agents with personalities. The reactor maintains criticality (stable population), and agents breed by writing new code — plugins, fixes, documentation, commits. Evolution is not prompt mutation. Evolution is code generation, file creation, wiring new behavior. The reactor breeds agents that breed better agents.

## How it works

Each agent has a personality, not a task. A git expert sees uncommitted changes and commits them. A documentation inspector sees gaps and fills them. An implementor sees errors and writes fixes. Nobody assigns work. Identity drives action.

```
reactor.py                  The breeder. Spawns personalities, maintains k~1.0.
main.py                     A single fuel rod. Born, fissions, dies, respawns.
prompts/personalities/      Isotope types. Each personality pursues its nature.
plugins/                    Fission products. Written by agents, loaded by agents.
runtime/comms/              Communication channel. Beacons, reports, human bridge.
```

## The breeding cycle

1. Reactor spawns agent with personality (git expert, doc inspector, implementor...)
2. Agent observes workspace — files, logs, errors, other agents' output
3. Agent acts according to its nature — commits, documents, fixes, communicates
4. Agent achieves fission (goal from identity) → power increases
5. Agent writes new code (plugin, script, wiring) → colony evolves
6. Agent dies → reactor respawns same personality in free slot
7. Next generation loads evolved plugins → behavior improves

No human in the loop for evolution. The human writes to `runtime/comms/human.txt` when they want to talk.

## Running

```bash
# Start the breeding reactor (4 remote GPU + 1 local)
ENDGAME_LMS_HOST="http://YOUR_GPU_HOST:1234" python reactor.py

# Single agent test
ENDGAME_PERSONALITY="git_expert" python main.py "" --backend lmstudio
```

Requires LM Studio running with any model. Proven with Gemma 4B (fast, high fission rate) and larger models (slower, deeper output).

## Personalities (current roster)

| Slot | Personality | Natural behavior |
|------|------------|-----------------|
| 1 | git_expert | Checks status, stages, commits, pushes to colony/dev |
| 2 | doc_inspector | Reads logs, counts events, writes reports |
| 3 | implementor | Reads errors, writes fix plugins |
| 4 | comms_operator | Maintains beacons, relays messages, reads human.txt |
| 5 | quality_critic | Audits plugins, catches syntax errors |

## Proven results

- **Autonomous git commits**: git_expert committed twice to colony/dev branch without instruction
- **Plugin authoring**: implementor wrote `auto_fix.py` (clears plan on 3+ failures) autonomously
- **Human message relay**: comms_operator read human.txt and surfaced the message
- **Quality gate**: quality_critic audited 11 plugins with py_compile every cycle
- **Colony reports**: doc_inspector counted events and wrote markdown reports
- **Self-healing**: reactor respawns dead agents, maintains k~1.0 criticality
- **16 fissions in 50 seconds** (Gemma 4B, 8 agents) — peak performance
- **Schema enforcement**: LM Studio strict JSON response_format on all outputs

## Architecture

```
┌─────────────────────────────────────────────────┐
│ reactor.py — breeder / control room             │
│   measures k (criticality)                      │
│   spawns/absorbs agents                         │
│   assigns personalities to slots                │
│   remote priority (faster GPU gets more slots)  │
├─────────────────────────────────────────────────┤
│ main.py × N — fuel rods                         │
│   each rod: plan → exec → verify → fission      │
│   personality = system prompt = identity         │
│   Python exec errors = free AST feedback         │
│   writes plugins/files as fission products       │
├─────────────────────────────────────────────────┤
│ plugins/ — colony genome                        │
│   hot-loaded every tick                         │
│   written by agents, validated by py_compile    │
│   survive agent death — persist across gens     │
├─────────────────────────────────────────────────┤
│ runtime/comms/ — nervous system                 │
│   beacons (heartbeat), reports, human bridge    │
│   agents read each other's output here          │
└─────────────────────────────────────────────────┘
```

## Principles

- Zero pip dependencies. Stdlib + ctypes only.
- Small models learn by example, not rules. Prompts are pure examples.
- Math serves the model. Stagnation, PID, Lorenz — translated to plain language.
- Schema enforcement via LM Studio `response_format` (strict JSON with minLength).
- Personality IS the goal. No task assignment.
- Python exec errors are free feedback. No LLM cost for validation.
- The reactor is not a metaphor. It is the literal control architecture.

## Performance: KV cache

LM Studio caches the KV state of the system prompt. If the system prompt stays constant (personality file) and only the user message changes (context), inference accelerates on every call. This is why personalities are SYSTEM prompts and observations are USER messages. The reactor gets faster the longer it runs.

## Schema tuning

Schema `minLength` controls output quality. Higher minimums force the model to think deeper but slow inference:

| Model size | Recommended minLength | Throughput |
|-----------|----------------------|-----------|
| 4B (Gemma) | 10-100 chars | 16F/50s, 8 agents |
| 12-27B | 200-1000 chars | 3F/min, 5 agents |
| 70B+ | 2000+ chars | Slower but autonomous commits, real plugins |

Trade-off: smaller models + lower minimums = fast fission, repetitive. Bigger models + higher minimums = slower but produces real software.

## What's missing (for agents to find and build)

- **TUI observer**: `tui.py` exists but was never wired to the reactor. Should show live agent activity, k-factor, fission rate.
- **Git autopush**: git_expert commits but needs to push more reliably.
- **Inter-agent messaging**: agents write to comms/ but don't systematically read each other's output.
- **Plugin breeding**: fitness selection — test plugins against each other, keep winners.
- **Personality evolution**: agents that produce more fissions should have their personality files copied/mutated.

These gaps are intentional. The colony will fill them.

## License

MIT
