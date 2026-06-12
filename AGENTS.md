# Breeding Reactor — Technical Map

## This is a breeder reactor

A breeder reactor produces more fissile material than it consumes. This system breeds agents that write code that makes future agents better. The fission products (plugins, scripts, documentation) become fuel for the next generation.

## File map

### Core
| File | Role | Lines |
|------|------|-------|
| reactor.py | Breeder control. Maintains k, spawns personalities. | ~120 |
| main.py | Fuel rod entry. Parses args, runs engine. | ~90 |
| engine.py | Tick loop. Phases, plugins, events. | ~290 |
| agents.py | Phase impls: plan, exec, verify, reflect, mutate. | ~800 |
| config.py | Constants, context policy, budgets. | ~140 |
| llm.py | LM Studio API. Schema enforcement. | ~320 |
| log.py | JSONL event emitter. | ~40 |
| token_state.py | Token budget tracking. | ~200 |
| lessons.py | Persistent lesson store. | ~60 |

### Personalities
| File | Identity | Emergent behavior |
|------|----------|-------------------|
| prompts/personalities/git_expert.txt | Lives for clean commits | Runs git status, stages, commits |
| prompts/personalities/doc_inspector.txt | Reads logs, writes reports | Counts events, writes markdown |
| prompts/personalities/implementor.txt | Fixes problems with code | Writes plugins when errors found |
| prompts/personalities/comms_operator.txt | Maintains channels | Beacons, relays, checks human.txt |
| prompts/personalities/quality_critic.txt | Validates, rejects bad code | Audits plugins with py_compile |

### Schemas (response_format, strict: true)
LM Studio enforces these server-side. The model MUST output valid JSON.
- planner.json: `{mode, sequence[], done_when}`
- verifier.json: `{verdict, evidence}`
- reflector.json: `{diagnosis, suggestion, rule}`
- mutator.json: `{action, filename, content}`
- actor.json: `{actions[], conclusion}` (GUI mode only)

### Plugins (fission products)
Hot-loaded every tick. Written by agents. Validated by py_compile.
Each: `def run(board): -> dict | None`

### Legacy GUI
actions.py, observer.py, tui.py, win32.py, acp_client.py
Imported conditionally. Not used in reactor mode. The TUI is unwired — waiting for an implementor to connect it to reactor telemetry.

## Rules
- No pip dependencies ever.
- No personal identifiers in code.
- Reflector only appends rules to planner.txt. Nothing else.
- Mutator only writes to plugins/. Validated before accepting.
- Git experts push to their own branch only. Never main.
- Schema enforcement is mandatory. No freeform LLM output.
- The reactor doesn't assign tasks. Personality drives behavior.
