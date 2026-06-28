# endgame-ai — a living, self-evolving desktop organism

A minimal computer-control agent designed as a genuine human-replacement operator on
your own machine. The loop is deliberately simple and "dumb." Real intelligence and
long-term growth come from three things:

1. **Hot-swappable LLM brains** — local OpenAI-compatible servers (LM Studio, llama.cpp,
   vLLM) or a GUI/browser-hosted agent (e.g. Grok) used interchangeably.
2. **Runtime self-evolution** — the organism creates, modifies, deletes, and hot-swaps
   its own independent Python **node modules**, then executes them directly. This is how
   it expands its own capabilities.
3. **Stateless reasoning feedback** — every LLM call is stateless; continuity comes from
   re-injecting the model's own prior reasoning into the next call, so later thinking is
   noticeably more capable.

It is alive: with a goal it pursues it and replans; with no goal it still ticks,
narrates, and may act or grow a capability on its own initiative.

> ⚠️ **This is an explicitly dangerous tool when run with `--autonomous`.** It controls a
> real desktop with no sandbox and can rewrite its own executable code. Run it only on a
> machine where you accept that power.

## Files

| File | Role |
|------|------|
| `organism.py` | The living loop, the context object handed to nodes, the dumb router, and the CLI. Entry point. |
| `brain.py` | Stateless multi-transport LLM (`openai`, `gui`) + reasoning-feedback. |
| `nodes.py` | The self-evolution substrate: list/read/create/modify/delete/execute node modules. **Contains the single safety point.** |
| `hands.py` | Thin adapter over the proven `desktop.py` / `actions.py` Windows I/O layer (observe + verbs). |
| `seed/*.py` | Initial node modules copied into `live_nodes/` on first run. |
| `config.json` | Brain transport + loop settings. |

Runtime-only (not committed, regenerated): `live_nodes/` (mutable working copy of the
nodes), `state.json`, `comms/` (gui-transport handoff files).

## How it works

The loop executes the current node, reads the **signal** it emits, and routes:

1. an explicit `next` in the node's patch wins; else
2. a signal that names an existing node routes there; else
3. fall back to the **`mind`** node — the decision-maker.

There is no fixed graph file. `mind` observes the screen, considers the goal/memory, and
chooses one move: `act` (run a desktop verb), `grow` (author a new node), or `rest`. New
nodes extend behavior without touching the loop.

### Nodes

A node is plain Python run in a namespace with: `ctx` (organism context), `emit(signal,
**patch)`, `log(msg)`, and stdlib (`time, json, re, os, pathlib`). Through `ctx` a node
can `ctx.hands.observe()`, `ctx.hands.act(verb, target, value)`, `ctx.think(system,
user)`, and read/write `ctx.state` / `ctx.memory`. Node files are re-read on every
execution, so a node modified mid-run is picked up on its next tick — true hot-swap.

## The safety model (single point)

Safety exists in **exactly one place**: `nodes.write_node()` — the moment the organism
writes or modifies its own node code. Everywhere else (executing nodes, controlling the
desktop, deleting nodes) is unguarded by design.

- **Default (guarded):** `write_node` refuses, surfaces the proposed code, and the
  organism rests so a human can decide.
- **`--autonomous`:** the gate is disabled; the organism freely authors and installs its
  own code. The human makes this one decision at launch time.

## Run

Requires Windows for live desktop control (uses `desktop.py`,
which uses Windows UI Automation via `ctypes`). Off-Windows, hands degrade gracefully so
the cognition loop can still be exercised. No third-party dependencies.

```powershell
# guarded — pursues a goal, asks before writing its own code
python organism.py "open notepad and type hello"

# free initiative, no goal
python organism.py

# full autonomy — can rewrite itself with no questions
python organism.py "research and improve yourself" --autonomous

# bounded run / fresh start
python organism.py "..." --max-ticks 20 --reset
```

Configure the brain in `config.json`: set `brain.transport` to `openai` (and `host` /
`model`) for LM Studio, or `gui` for a browser-hosted agent reached via the
`comms/request.json` ↔ `comms/response.json` file handoff.
