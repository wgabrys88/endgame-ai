# endgame-ai

An unconstrained, self-evolving desktop organism. It runs on a real Windows machine,
observes the screen, and operates the mouse and keyboard like a human operator to pursue a
goal — or, given no goal, to simply *live*: explore, reason about what it sees, and act on
its own initiative.

There is no constrained mode. The organism has full control of the machine. Its character
comes not from rules but from how it is asked to think.

---

## The idea

A small, dumb loop hosts something that is meant to feel alive. The loop does almost
nothing: it runs a node, reads the signal that node emits, and follows an edge to the next
node. All intelligence lives in three places:

1. **The brain** — a stateless LLM, reached through a swappable transport.
2. **The circuits** — a planner → act → verify → reflect pipeline whose behaviour is shaped
   entirely by prompts and a typed-record contract.
3. **Self-modification** — the organism can rewrite its own wiring at runtime, including
   *which brain it thinks with*.

The whole system reuses one mature, dependency-free Windows I/O layer (`desktop.py` +
`actions.py`) and adds a thin, intent-based cognition layer on top. Standard library only.

---

## Intent, not strings

The organism never matches literal UI text to decide if it succeeded. The planner writes
each step's `done_when` as an *intent* ("a text editor window is open", "the page shows the
chat"), and a dedicated **verifier** judges whether the spirit of that intent is met from
what is visible on screen. This is what lets it cope with windows it has never seen before.

Every LLM reply is a **typed record**, validated against a contract:

| circuit      | `record_type` | the decision it commits                         |
|--------------|---------------|-------------------------------------------------|
| planner      | `task`        | an ordered list of `{description, done_when}`   |
| act          | `action`      | `conclusion: EXECUTE/CANNOT` + a verb chain     |
| verify       | `verdict`     | `confirmed: true/false` + evidence              |
| reflect      | `diagnosis`   | why it failed + retry / replan / escalate       |
| self_modify  | `wiring_patch`| a `{op, path, value}` edit to its own wiring    |

If a circuit returns the wrong record type, the node **fails hard** — it does not guess and
it does not fall back. Failure is routed to the reflector, which decides what to do next.

---

## ROD — the two-call decision

Every decision is two LLM calls (Reason-Observe-Decide):

1. **Call 1** — the model reasons freely about the situation.
2. **Call 2** — the same prompt, with the model's own Call-1 reasoning echoed back as
   `ROD_REASONING_CONTENT`. It re-reasons from its draft and commits clean JSON.

This is intelligence amplification, not parse insurance: the second pass critiques its own
first thoughts. Reasoning is read from the model's `reasoning_content` field, or — for
models that inline thinking, like Nemotron's `<think>…</think>` — from the think block.

---

## Swappable brains

The brain transport is just a value in the wiring (`model.transport`):

- **`openai`** — any OpenAI-compatible server (LM Studio, llama.cpp, vLLM). This is the
  **core**: the system always boots here.
- **`file_proxy`** — a file handoff. The engine writes an OpenAI-shaped `comms/request.json`
  and waits for `comms/response.json`. Any outside agent (human, watcher, or a
  browser-hosted AI) can answer.
- **`browser_ai`** — the organism drives a browser AI through the desktop itself.

Because `self_modify` can patch `model.transport`, the organism can decide — for itself — to
change how it thinks. The engine reloads the wiring and re-binds the brain live, mid-run.

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
they run, so editing one hot-swaps behaviour with no restart.

**State** persists to `state.json` between ticks. **Reasoning traces** accumulate in
`reasoning_chain` for debugging.

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

The model is the slow part on modest hardware; a decision is two calls, so be patient.

### The workbench

A minimal debug and control surface, no dependencies — just the standard library:

```
python workbench.py        # then open http://localhost:8800
```

It reads the organism's live files and shows, refreshing every 1.5s:

- **Narration** — what the organism is doing, newest first.
- **Plan** — the current steps and their `done_when` intents.
- **History** — executed action chains and their outcomes (failures in red).
- **Reasoning chain** — the model's thinking per circuit.
- **file_proxy handoff** — when the brain transport is `file_proxy`, the workbench shows
  the prompt the organism is waiting on and lets you (or an AI) **answer as the brain** by
  writing the response record. This is the human-in-the-loop / brain-swap surface.
- **Control** — set or clear the goal for the next run (`goal.json`).

---

## Status

Working and verified on Windows against LM Studio (`nvidia-nemotron-3-nano-4b`):

- The full pipeline runs: planner → scheduler → observe → act → verify → reflect.
- A real run opened Notepad and entered the genuine recovery loop
  (`verify → step_denied → reflect → retry → observe → act`).
- The ROD two-call pattern is confirmed in the server logs (each decision is two calls,
  the second carrying the echoed reasoning).

The brain-swap scenario (the organism routing its own cognition through a browser-hosted AI)
and the debug/control workbench are the active frontier.

---

## Philosophy

Less is best. No fallbacks, no dead branches, no constrained mode. Every file and every line
is meant to align with the others. The organism's "aliveness" is an emergent property of a
tiny loop, a strict intent contract, and prompts written to invite exploration — not a pile
of special cases.
