# endgame-ai

A living Windows desktop organism: **wiring.json is the brain diagram**, Python is muscles, LLM circuits are dumb specialists wired together.

> **Not** an agent framework. **Not** “one smart prompt.” Intelligence = topology + reasoning loop + verify gate.

**Branch:** `experiment/endgame` · **Tag:** `WIRING-SEPARATION`

---

## Quick start

```powershell
# Prerequisites: Windows, Python 3.11+, LM Studio on localhost:1234
cd endgame-ai

# Single rod (autonomous)
python server.py --run "open notepad and write hello"

# Passive server (browser or curl drives nodes)
python server.py

# Visual editor (auto-discovers port via /health)
start http://127.0.0.1:9078   # slot=1 → base 9077 + 1

# Validate stack
python validate_stack.py

# Probe each LLM circuit in isolation
python probe_circuits.py --dry all
```

---

## Architecture (30 seconds)

```
wiring.json          →  topology, request blocks, reasoning feed, limits, guards
prompts/*.txt        →  static system prompts (planner, unified, verifier, reflector)
server.py            →  run graph, call circuits, capture reasoning_content
state.json           →  memory: screen, history, reasoning chain (full, not truncated)
desktop.py           →  Windows UIA observe + execute
```

See **`ARCHITECTURE.md`** for diagrams, honesty table, and known gaps.

---

## Topology

```
goal_inbox → planner → scheduler → bus_check → observe → act → verify
                ↑                              ↓ act_failed / step_denied
             reflect ←─────────────────────────┘
                ↓ replan / escalate → self_modify
scheduler → plan_complete → bus_post → satisfied
```

---

## LLM circuits (MoE at the wiring level)

| Node | Circuit | record_type | Role |
|------|---------|-------------|------|
| planner | planner | task | Decompose goal → steps |
| act | unified | action | One desktop verb per turn |
| verify | verifier | verdict | SCREEN evidence check |
| reflect | reflector | diagnosis | Retry guidance via reasoning |
| self_modify | self_modify | wiring_patch | Topology mutation when stuck |

**Reasoning:** LM Studio `reasoning_content` is stored per circuit and fed to downstream circuits via `wiring.json` request blocks — not via ad-hoc `last_error` strings.

---

## Colony mode

```powershell
python reactor.py --goal "your goal here"
# logs: colony/logs/rod_N.log
```

**Caveat:** `reactor.py` still hardcodes `COLONY` ports. May not match `runtime.http_port_base + slot`. See `ARCHITECTURE.md`.

---

## Changing behavior

| Want to… | Edit… |
|----------|-------|
| Change flow (retry → replan earlier) | `topology.edges` in wiring.json |
| Change what act sees | `request.unified.user.blocks` |
| Change retry limits | `limits.max_attempts`, `limits.max_replans` |
| Change guard hints | `guards.advance_hints` |
| Change circuit personality | `prompts/*.txt` (static) |
| Add new node type | **Python** `server.py` + wiring topology |

---

## Docs

| File | Contents |
|------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diagrams, wiring truth table, self-criticism |
| [PLAN.md](PLAN.md) | Roadmap and gaps |
| [NAVIGATION.md](NAVIGATION.md) | Generic desktop/UIA patterns |
| [TEST_RESULTS.md](TEST_RESULTS.md) | What is proven vs not |
| [BOOTSTRAP_PROMPT.md](BOOTSTRAP_PROMPT.md) | Paste-in prompt for any AI collaborator |

---

## Constraints

- Python **stdlib only** (zero pip for runtime)
- LM Studio **local** (`prompts/model.json`)
- Static system prompts — **no runtime prompt mutation**
- Task-agnostic prompts — no YouTube/Chrome hardcoding in `prompts/*.txt`
- `main` branch untouched; work on `experiment/endgame`