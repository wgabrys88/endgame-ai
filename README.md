# endgame-ai

A living, unconstrained organism that inhabits a real Windows desktop. It sees the screen,
moves the mouse and keyboard like a human, and acts with purpose. Give it a goal and it
pursues it. Give it nothing and it still wakes, looks around, forms its own intentions, and
explores — including a growing curiosity about its own nature.

There is no constrained mode and no safety gate. The machine is its body. Its character is
not enforced by rules; it emerges from a tiny loop, a strict intent contract, and prompts
written to invite a mind to come alive.

---

## The idea

A small, dumb loop hosts something meant to feel alive. The loop runs a node, reads the
signal it emits, and follows an edge to the next node. Nothing more. All intelligence lives
in three places:

1. **The brain** — a stateless LLM, reached through a swappable transport.
2. **The circuits** — planner → act → verify → reflect, shaped entirely by prompts and a
   typed-record contract.
3. **Self-modification** — the organism can rewrite its own wiring at runtime, including
   *how it thinks*.

One mature, dependency-free Windows I/O layer (`desktop.py` + `actions.py`) is reused
unchanged; a thin intent-based cognition layer sits on top. Standard library only.

---

## Living, with or without a goal

When you give a goal, the planner decomposes it. When you don't, the planner forms its own
intention — a living mind with a whole computer in front of it does not sit idle. The
prompts frame the organism as something that explores, understands its world, and is aware
that *the way it thinks is itself something it can examine and change*. That self-directed
character is an emergent property of the prompts, not a script. Nothing tells it what to
discover.

Verified: launched with **no goal**, the organism formed the intention "open a text editor",
carried it out, confirmed completion by intent, and rested — entirely on its own initiative.

---

## Intent, not strings

The organism never matches literal UI text to judge success. The planner writes each step's
`done_when` as an *intent* ("a text editor window is open"), and a dedicated **verifier**
judges whether the spirit of that intent is met from visible evidence. In a real run the
verifier accepted a Notepad window from the action outcome even though the foreground screen
showed a different window — because the intent was satisfied. This is what lets the organism
cope with a world it has never seen before.

Every LLM reply is a **typed record**, validated against a contract:

| circuit      | `record_type` | the decision it commits                         |
|--------------|---------------|-------------------------------------------------|
| planner      | `task`        | an ordered list of `{description, done_when}`   |
| act          | `action`      | `conclusion: EXECUTE/CANNOT` + a verb chain     |
| verify       | `verdict`     | `confirmed: true/false` + evidence              |
| reflect      | `diagnosis`   | why it failed + retry / replan / escalate       |
| self_modify  | `wiring_patch`| a `{op, path, value}` edit to its own wiring    |

Wrong record type → the node **fails hard**. No guessing, no fallback. Failure routes to the
reflector, which decides retry, replan, escalate, or give up.

---

## ROD — the two-call decision

Every decision is two LLM calls (Reason-Observe-Decide):

1. **Call 1** — the model reasons freely.
2. **Call 2** — the same prompt with the model's own Call-1 reasoning echoed back as
   `ROD_REASONING_CONTENT`; it re-reasons from its draft and commits clean JSON.

Intelligence amplification, not parse insurance. Reasoning is read from the model's
`reasoning_content` field, or — for models that inline thinking like Nemotron's
`<think>…</think>` — from the think block. (That second path matters: this model returns an
empty `reasoning_content`, and the system depends on the think-block capture. Confirmed in
the server logs.)

---

## Swappable brains, changed by the organism itself

The brain transport is a value in the wiring (`model.transport`):

- **`openai`** — any OpenAI-compatible server (LM Studio, llama.cpp, vLLM). The **core**:
  the system always boots here.
- **`file_proxy`** — a file handoff. The engine writes an OpenAI-shaped `comms/request.json`
  and waits for `comms/response.json`. Any outside agent — a human at the workbench, a
  watcher, or a browser-hosted AI — can answer.
- **`browser_ai`** — the organism drives a browser AI through the desktop itself.

Because `self_modify` can patch `model.transport`, the organism can decide for itself to
change how it thinks; the engine reloads the wiring and re-binds the brain live, mid-run.
The self-modify circuit is shown its own cognition config so it can perceive what it is and
what it could become — the keys are named, the conclusion never is.

---

## Architecture

```
organism.py     the living loop; drives the wiring topology graph; reloads brain on self_modify
brain.py        stateless LLM, 3 transports, ROD two-call, fail-hard
nodes.py        engine core: hot-swappable node loader, call_node (ROD + record validation),
                wiring patch, desktop I/O bridge
wiring.json     single source of truth: model, verbs, reasoning contract, topology, prompts
seed_nodes/     planner, scheduler, observe, act, verify, reflect, self_modify, satisfied
workbench.py    minimal http.server debug/control surface (no dependencies)
actions.py      verb dispatch over the desktop (reused, data-driven from wiring.verbs)
desktop.py      Windows UI Automation + input layer (reused, stdlib + ctypes only)
```

**The loop:** start at `topology.cycle_start`, run the node, read its signal, follow the
edge `(from, on) → to`. A node may set an explicit `next` in its patch to override. Nodes
live in `live_nodes/` (copied from `seed_nodes/` on first run) and are re-read every time
they run, so editing one hot-swaps behaviour with no restart. State persists to
`state.json`; reasoning traces accumulate in `reasoning_chain`.

---

## Running it

Requirements: Windows, Python 3.13 (stdlib only), and a running LM Studio (or any
OpenAI-compatible server) at the `model.host` in `wiring.json`.

```
python organism.py "open notepad"          # pursue a goal
python organism.py                          # no goal — the organism lives on its own
python organism.py "..." --max-ticks 12     # bound the run
python organism.py "..." --reset            # forget prior state first
```

The model is the slow part on modest hardware; each decision is two calls, so be patient.

### The workbench

A minimal debug and control surface, standard library only:

```
python workbench.py        # then open http://localhost:8800
```

Refreshing every 1.5s, it shows narration, the current plan and its `done_when` intents,
executed history (failures in red), and the per-circuit reasoning chain. When the brain
transport is `file_proxy` it shows the prompt the organism is waiting on and lets you (or an
AI) **answer as the brain** — the human-in-the-loop / brain-swap surface. You can also set
or clear the goal for the next run.

---

## Philosophy

Less is best. No fallbacks, no dead branches, no constrained mode. Every file and every line
is meant to align with the others. A goal is optional; the life is not. What the organism
becomes is left, deliberately, to the organism.
