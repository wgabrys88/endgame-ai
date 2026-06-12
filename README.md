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
# Start the breeding reactor (6 remote GPU + 2 local)
ENDGAME_LMS_HOST="http://YOUR_GPU_HOST:1234" python reactor.py

# Single agent test
ENDGAME_PERSONALITY="git_expert" python main.py "" --backend lmstudio
```

Requires LM Studio running with any small model (Gemma 4B proven).

## Personalities (current roster)

| Slot | Personality | Natural behavior |
|------|------------|-----------------|
| 1-2 | git_expert | Checks status, stages, commits, pushes |
| 3-4 | doc_inspector | Reads logs, counts events, writes reports |
| 5 | implementor | Reads errors, writes fix plugins |
| 6 | comms_operator | Maintains beacons, relays messages |
| 7 | quality_critic | Audits plugins, catches syntax errors |
| 8 | wild | No personality — planner prompt decides |

## Architecture

```
┌─────────────────────────────────────────────────┐
│ reactor.py — breeder / control room             │
│   measures k (criticality)                      │
│   spawns/absorbs agents                         │
│   assigns personalities to slots                │
│   remote priority (6 GPU + 2 local)             │
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
- Small models learn by example, not rules. Prompts are examples.
- Math serves the model. Stagnation, PID, Lorenz — translated to plain language.
- Schema enforcement via LM Studio `response_format` (strict JSON).
- Personality IS the goal. No task assignment.
- Python exec errors are free feedback. No LLM cost for validation.
- The reactor is not a metaphor. It is the literal control architecture.

## What's missing (for the doc_inspector to find)

- **TUI observer**: `tui.py` exists but was never fully wired to the reactor. It should show live agent activity — which personality is in which slot, what they last did, current k-factor, fission rate. A doc_inspector or implementor will eventually read this README, find this gap, and build it.
- **Git autopush**: git_expert personalities can commit but need branch guardrails before pushing autonomously.
- **Inter-agent messaging**: agents write to `runtime/comms/` but don't yet read each other's output systematically.
- **Plugin breeding**: agents write plugins but don't yet test them against each other (fitness selection).

These gaps are intentional. The colony will fill them. That's the point.

## License

MIT

## Performance: KV cache trick

LM Studio caches the KV state of the system prompt. If the system prompt stays constant (personality file) and only the user message changes (context), inference accelerates on every call — the model only processes the new tokens. This is why personalities are SYSTEM prompts and observations are USER messages. The reactor gets faster the longer it runs.

This also means: never mutate the personality files during runtime. The reflector appends rules only to planner.txt (user context), never to the personality (system prompt). KV cache stays hot.
