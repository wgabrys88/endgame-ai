# Endgame-AI: Reactor Architecture

## The Nuclear Analogy Is Not An Analogy

This system IS a nuclear reactor. Not metaphorically.

| Reactor concept | Code equivalent |
|---|---|
| Fuel rod | `main.py` — single agent process |
| Fission event | Goal completion (verified by LLM) |
| Fission products | Plugins written by agents (probabilistic) |
| Neutrons | `spawn_main()` calls (propagate to new slots) |
| Control rods | `reactor.py` — regulates population via k-factor |
| Criticality (k=1) | Stable agent count maintained by reactor |
| Xenon poisoning | Stagnation accumulation (blocks progress) |
| Isotope type | Prompt personality (determines behavior) |
| Cross-section | Schema (constrains output probability) |
| Moderator | Math signals translated to plain language |
| Reactor operator | Human via `runtime/comms/human.txt` |

## File Map

### Core (the reactor)
- `reactor.py` — Population control. Measures k, spawns/absorbs. 117 lines.
- `main.py` — Entry point. Parses goal, runs engine loop.
- `engine.py` — Tick loop. Calls phases, records events, loads plugins.
- `agents.py` — Phase implementations: planner, actor, verifier, reflector, mutator.
- `config.py` — All constants. Context policy, budgets, hosts.
- `llm.py` — LM Studio calls with schema enforcement.
- `log.py` — Event emitter (JSON lines).
- `token_state.py` — Token budget tracking.
- `lessons.py` — Persistent lesson storage.

### Prompts (isotope personalities)
- `prompts/planner.txt` — Fission planner. Produces exec steps.
- `prompts/actor.txt` — GUI controller (legacy, used for screen mode).
- `prompts/reflector.txt` — Diagnoses stuck agents. Appends rules to planner only.
- `prompts/mutator.txt` — Writes plugins. Primary evolution path.
- `prompts/verifier.txt` — Confirms goal achievement.

### Schemas (neutron cross-sections)
All schemas use LM Studio `response_format` with `strict: true`.
The model is FORCED to output valid JSON matching the schema.

### Plugins (fission products)
Written by agents at runtime. Each must have `def run(board):`.
Hot-loaded every tick. Survive across agent lifetimes.

### Legacy GUI
- `actions.py`, `observer.py`, `tui.py`, `win32.py`, `acp_client.py`
- Still imported by core (conditional paths). Not used in reactor mode.

## Operating Rules

- Zero pip dependencies. Stdlib + ctypes only.
- No personal identifiers in committed code.
- Prompts are examples, never instructions. Small models copy, they don't reason about rules.
- Reflector modifies ONLY `planner.txt` (appends RULE: lines). Header is immutable.
- Mutator writes plugins. Validated with `py_compile` before accepting.
- Reactor measures k externally. Individual agents are never blocked.
- Agents with empty goals derive purpose from prompt personality.
- Python exec errors ARE the feedback loop (free AST validation).

## Host Allocation

- `ENDGAME_LMS_HOST` env var pins agent to specific LM Studio instance.
- Reactor fills remote (6 slots) first, then local (2 slots).
- Remote priority — faster GPU gets more work.

## Evolution Path

The reactor spawns personalities, not tasks. Next step:
agents get git access and develop their own branch.
