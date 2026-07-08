# endgame-ai — notes to self (post-compaction handover)

This file is my own working memory. Read it first, trust it, then execute.
It is intentionally short. If something is not here, it is not load-bearing.

Branch: `live-test-run`. Host reality: **Windows-11 only** at runtime (UIA via
`comtypes`); this dev box is WSL2, so the loop cannot fully run here — only
non-desktop nodes and structural/behavioral tests execute. `transport_file_proxy`
is the WSL2 debug endpoint: it writes the request JSON to disk and the operator
(me, acting as the LLM) answers. `transport_xai` is the real Windows transport.

## Mission

The organism is **only nodes + wiring**. Evolve it toward the fractal topology:
every node is a potential organism; topology supports one-to-many parallel
dispatch, many-to-one barrier fan-in, node instances (`node_execute:browser` =
one class, many wired instances), recursive `spawn_organism`, and runtime
rewiring. Build this on a minimal plugin substrate so any capability returns as
an on-demand plugin: drop a `node_*.py` / `cap_*.py` / `transport_*.py` file,
add one wiring line, zero core change. Minimum resting size, maximum reachable
capability.

## Axioms (hard — do not violate)

- System = nodes + wiring. Everything hot-swappable. No branching, no fallbacks,
  no defensive coding, no ceremony.
- No questions. Deduce and execute. The fractal design exists so nothing needs
  to ask.
- **Plugin existence is dynamic + file-based** (`core_loader.load(kind, name, w)`,
  name → `<prefix><name>.py`). A compile-time registry is FORBIDDEN — self-modify
  writes new `node_*.py` / `cap_*.py` at runtime; a registry would kill that.
  ABCs (only `BaseNode`) define SHAPE, never existence.
- **No one-line wrapper functions with docstrings** = bloat. Inline them.
- **No truncation of the organism's narrative.** Each node writes its
  interpretation of the goal into `state["effective_goal"]`; the next node reads
  it. This non-deterministic narrative is what breaks loops and moves the live
  organism forward. Never `str[:N]` it. If you must bound, filter at the source.
  (Legit `[:N]` that stays: hashes/ids, git commit subject, telemetry samples,
  fixed-field git-porcelain parsing.)
- Prompts in `wiring.json` use a biblical register by design (it makes the LLM
  controllable). Keep prompts + record contracts aligned whenever topology
  changes.

## Invariants to protect (verify after EVERY change)

- `python3 -m py_compile *.py` clean.
- `python3 check_topology.py` exits 0 (reachability + no dangling targets).
- Import smoke: `import core_organism, core_bus, core_wiring, core_state`.
- Hot-swap + self-modify intact: `core_nodes.hot_swap_to_known_good`,
  `resolve_known_good` / `update_known_good_ref`, and the self_modify apply block
  in `core_organism.run` (`apply_evolution_patch` → `commit_self_evolution` →
  reload wiring; on failure `hot_swap_to_known_good`) — currently at
  `core_organism.py` ~L108–133.
- `validate_wiring` and code must agree: if code hard-reads `w[...]["x"]`, `x`
  must be a required path in `core_wiring.validate_wiring`. No fallbacks.
- New tracked file ⇒ add a `!name` line to `.gitignore` (it is ignore-all + a
  whitelist).
- Commit each verified step. This README is the only doc; update it per step.
  (`report.md` was deleted on purpose — do not recreate a scratch file.)

## Current state (verified, committed on `live-test-run`)

Substrate + hygiene already done:
- `core_loader.load(kind, name, w)` is the single dynamic loader.
  `KINDS = {node, transport}`; `split_instance("a:b") → ("a","b")` for fractal
  instances. Add a plugin kind = one `KINDS` entry. `_load_node` and the inline
  transport loader are gone.
- Goal narrative: `effective_goal` is seeded once at organism start
  (`st.setdefault("effective_goal", st["goal"])`); every node reads
  `state["effective_goal"]` directly — no helper, no `ctx.get("goal")` fallback.
- All narrative truncations removed (full-fidelity narrative).
- `transport_file_proxy` config has a `reasoning` block (was missing → the
  transport was unusable; `core_brain.think` hard-reads `cfg["reasoning"]`).
- Error-routing bounded: `state["error_streak"]` resets on any successful node,
  increments on error, HALTS HARD at `topology.max_error_streak` (=5). Fixed the
  unbounded recursive hot-loop in `run()`'s except branch.

Topology data model (B1 done): edges may be a single node name OR a list.
`core_organism.next_nodes_for` returns `list[str]`; `next_node_for` delegates and
still REJECTS fan-out (`len != 1`) until the frontier loop (B2) exists.

Current wiring is still the **linear** pipeline (fractal topology not written
yet). `cycle_start = node_observe`. 10 nodes:
planner, scheduler, observe, execute, frame_action, verify, reflect,
self_modify, satisfied, error.

**B2 done — frontier loop.** `core_organism.run` now schedules a `frontier`
(`list[str]` of active nodes) instead of a single `current`. Loop: pop head →
process → `frontier.extend(next_nodes_for(...))`. Linear = pop 1 / push 1
(byte-identical to the old sequential path). Fan-out = a list-valued edge pushes
several successors (processed BFS: pop head, append successors). `next_node_for`
DELETED (its only job was rejecting fan-out). Per-node try/except is now INSIDE
the loop: on node exception it pushes the `error` successors back onto the
frontier and continues — **the recursive `run(start_node=...)` re-entry is gone**;
`error_streak`/`max_error_streak` halt still applies (iterative now). `halt`
signal and streak-cap both clear the frontier and return. Frontier persists in
`state["frontier"]`; resume seeds it from `state["frontier"]` else `[current]`
(old state files without `frontier` still resume from `next_node`). New terminal
`_phase = "frontier_drained"` when the frontier empties. Node-start/complete
events now carry `frontier` + `successors`.

Verified (stubbed `call_node` + real `wiring.json` base with topology override):
linear traversal identical; fan-out dispatches all successors; persistent
failure halts at streak 5 with exactly 5 invocations and NO recursion; fan-out
BFS order correct; old-state resume works. Real wiring is STILL linear — fan-out
is available but unused until B6.

## Remaining build order — Phase B (fractal). One verified commit each.

- **B3 done — `node_barrier` (many-to-one fan-in).** Mechanical node
  `node_barrier.py`. Reads its arity from `topology.barriers[<node>]`, counts
  arrivals in `state["_barriers"][<node>]`. Emits `wait` (absorb) until the final
  arrival, then resets the counter to 0 and emits `join` (proceed). `wait` is a
  scheduler control signal like `halt`: the frontier loop intercepts it BEFORE
  `next_nodes_for` — absorbs the slot (`_phase=barrier_wait`), pushes no
  successor, `continue`. A barrier's wiring edges are `{"join": "<succ>",
  "wait": "wait"}` (the `"wait":"wait"` sentinel satisfies `validate_signal`;
  `check_topology` treats `halt`+`wait` as terminal sentinels). New required
  wiring path `topology.barriers` (currently `{}`; populated in B6). NOT yet in
  `topology.nodes` — the capability exists on disk, wired live only in B6 (adding
  it to `nodes` would demand a prompt entry it doesn't need as a mechanical node).
  Verified: arity-2 join fires the successor exactly once after both branches
  arrive (1st→wait, 2nd→join), counter resets to 0; under-arity (3 expected, 2
  arrive) holds the gate, successor never fires, count preserved; linear
  regression intact.

- **B4 — `cap_spawn.spawn_organism(goal, duration)`** capability: run
  `core_organism` as a child, return the child's `effective_goal`. Depth-gate via
  wiring (`fractal.max_recursion_depth`, default 3). This is the literal fractal
  claim: a node that is itself an organism.
- **B5 — runtime topology patch.** Extend `apply_evolution_patch` with topology
  ops so `reflect` can rewire the graph mid-run (`topology_patch` signal already
  routes to self_modify).
- **B6 — rewrite `wiring.json` into the visionary fractal topology**: one-to-many
  execute-by-capability instances, barrier fan-in to reflect, aligned
  biblical-register prompts + record contracts. Verify with `check_topology.py`
  under list-edge semantics. THIS is "produce the visionary topology."

Design rule for B: ABC only where it removes real duplication (`BaseNode` does;
transport/tool ABCs do NOT — their contract is the module-level `call`/`run`
export enforced by the loader + call site). Capabilities are the real dedup:
`node_execute` + instances collapse many executors into one class.
