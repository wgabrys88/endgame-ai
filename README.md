# endgame-ai — consolidation pass (dedup / dead-code removal)

This README documents **one specific change**: a behavior-preserving
deduplication pass over the token-reduced organism branch. It is not a product
overview. It records what was merged, why it was safe, why I was confident, and
how to bring anything back **the smart way** if it is ever needed.

Design axioms this pass obeyed:

- The system is **wiring between nodes**. Everything that is not the node graph
  or a node's real work is suspicious surface.
- **Fail hard.** No fallbacks, no defensive branching, no silent defaults. One
  canonical implementation per idea; callers depend on it directly.
- Duplication is the enemy: N functions doing the same thing is N−1 too many.

---

## Plugin platform (fractal-topology substrate) — in progress

Building toward the main-branch **fractal topology vision** (README Appendix B):
each node is a potential organism; topology supports one-to-many, barrier
fan-in, node instances, recursive spawn, and runtime rewiring. The substrate is
a uniform plugin model so any capability (including everything from the 5000-LOC
main branch) returns as an on-demand plugin — drop a file, add a wiring line,
zero core change. Plugin *existence* stays dynamic and file-based so
self-evolution can keep writing new plugins at runtime; ABCs define only *shape*.

Progress:

- **Step A1 — unified loader (`core_loader.py`).** One `load(kind, name, w)`
  replaces the two ad-hoc loaders (`core_node_base._load_node`,
  `core_brain._load_transport_module`), which are now gone/delegating. Resolves a
  wiring-named file (`<name>.py`) and validates the kind's required export
  (`run` for nodes, `call` for transports) — fail hard, no fallback. Adds the
  fractal `base:instance` name split (e.g. `node_execute:browser` → one
  `node_execute.py` class, instance label threaded into `ctx.node_instance`), so
  one file backs many wired instances. Behavior-preserving for current linear
  topology (existing names contain no `:`).

  Bring back a plugin the smart way: add a new `kind` to `core_loader.KINDS`
  (one line: paths-key, module prefix, required export). Do not write a new
  loader.

- **Step A2 — transport ABC: intentionally NOT built.** The transport contract
  is a module-level `call(messages, cfg) -> {content, reasoning, ...}`. Existence
  is enforced by `core_loader` (export=`call`); return-shape by `core_brain.call`.
  An ABC would add ceremony and LOC and fight the self-evolution pattern of
  writing a `.py` that exports `call`. Contracts, not class trees, where a class
  removes no duplication. (`report.md` §13.)

- **Step A5 — goal-narrative unification, then de-bloated (see §15).** The
  effective-goal read/append was first factored into `bus.current_goal`/
  `append_goal`, then those helpers were DELETED as one-line bloat. Root fix:
  seed `effective_goal = goal` once at organism start, so every node reads
  `state["effective_goal"]` directly — no helper, no `ctx.get("goal")` fallback.

- **Truncations removed (critical).** All narrative truncations that lopped off
  a node's goal-interpretation (`lesson[:100]`, `code[:120]`, `descs[:3]`, …)
  were removed — that narrative is the loop-breaking meta-mechanism and must be
  full-fidelity. Filter at the source if content is unwanted; never truncate the
  organism's own narrative. Legitimate hash/id/git-subject/field slices kept.

---

## What changed (net −29 LOC, 6 files, zero topology/contract change)

| # | Cluster | Before | After | Files |
|---|---------|--------|-------|-------|
| 1 | Atomic JSON write | 3 real impls + 1 dead wrapper | 1 canonical (`core_wiring.atomic_write_json`) | `core_brain`, `core_nodes`, `transport_file_proxy` |
| 2 | `load_json` | 2 (1 dead passthrough) | 1 canonical (`core_wiring.load_json`) | `core_brain`, `core_nodes`, `core_organism` |
| 3 | `_git` subprocess runner | 3 near-identical | 2 (canonical `core_nodes._git`; `node_self_modify` now delegates) | `node_self_modify` |
| 4 | Runtime event logging | indirection dict rebuild | direct call | `core_state` |
| 5 | Desktop action wrappers | 6 copy-paste closures | 1 `_guarded(name, fn)` factory + 6 one-liners | `core_nodes` |

### 1. Atomic JSON write — unified on `core_wiring.atomic_write_json`
`core_brain.atomic_write_json` was a pure passthrough to `core_wiring` — deleted.
`transport_file_proxy._atomic_json` re-implemented the same tmp-file + `os.replace`
dance — deleted, now calls `core_wiring.atomic_write_json`. Callers in
`core_nodes.save_wiring` repointed to `core_wiring` directly.

Why safe: identical semantics (write temp, atomic rename). The canonical version
is actually stronger (pid+tid-suffixed temp avoids concurrent-writer clobber).

### 2. `load_json` — unified on `core_wiring.load_json`
`core_brain.load_json` was a one-line passthrough — deleted. Its two real callers
(`core_organism` resume-state read, `core_nodes` wiring reload) now import from
`core_wiring`, which is where JSON-decode-error handling already lives.

### 3. `_git` — one runner
`core_nodes._git` is the superset (returns `CompletedProcess`, has a `check=`
flag). `node_self_modify` had a stdout-only clone with 3 call sites; it already
imported `core_nodes`, so those now call `core_nodes._git([...]).stdout`. The
local `_git` and the now-unused `subprocess` import were removed.

Not merged (deliberate): `core_brain.StablePrefix._git` stays local. `core_nodes`
imports `core_brain`, so making `core_brain` import `core_nodes` would create a
circular import. Fail-hard beats a circular dependency. Documented, not hidden.

### 4. Runtime event logging — removed the middle dict
`core_state.runtime_event` used to build a throwaway `{"event_log_path": ...}`
dict before calling `core_brain.log_runtime_event`. All callers already pass the
full wiring dict, and `log_runtime_event` resolves the log path from it, so the
intermediate rebuild was pure churn. Now it calls straight through.

### 5. Desktop action wrappers — factory instead of copy-paste
`build_capability_runtime` had six near-identical closures
(`click/type_text/press_key/hotkey/scroll/open_url`), each `_assert_duration_open`
+ `_record_action` around one desktop method. Replaced with a `_guarded(name, fn)`
factory and six one-line bindings that keep the exact per-method arg coercion.
Same runtime namespace keys, same behavior, ~5× less code for that block.

---

## Corrections to the prior review

- An earlier note flagged `core_bus.observation_brief`'s local `tree` variable as
  dead. **That was wrong** — `tree` is used to source `rendered_node_count`,
  `max_llm_nodes`, and `llm_node_limit_hit`. I read the body before touching it
  and left it intact. Recorded here so the mistake is not repeated.

---

## Why I was confident (meta)

- **Static verification, not vibes.** After every edit: `python3 -m py_compile
  *.py` (all 26 files clean) plus an import smoke test of the pure-Python core
  (`core_wiring/core_bus/core_state/core_organism`). Windows-only UIA/ctypes
  imports are deferred inside functions, so compile is a valid check on Linux.
- **Grepped every call site first.** Each removed symbol
  (`brain.load_json`, `brain.atomic_write_json`, `_atomic_json`, the local
  `_git`) was searched repo-wide before and after; post-change residual
  references = none.
- **Read bodies before merging**, not just names. That is how the `tree`
  false-positive and the `core_brain._git` circular-import trap were caught.
- **Topology untouched.** No edit went near `wiring.json`, the node graph, node
  `run(ctx)` signatures, transport `call(messages, cfg)` signatures, or the
  `_RECORD_RULES` contract. A reachability script confirmed the graph is intact
  (10 nodes, all reachable from `node_observe`, no dangling edge targets).

Confidence bound: this is a **static** guarantee (compiles, imports, contracts
preserved). It is not a live-run guarantee — actually executing the organism
needs Windows 11 + UIA + `XAI_API_KEY`, which this review host does not have.

---

## How to bring things back — the smart way

If any removed surface is ever wanted again, re-add it **as one canonical
implementation**, never by re-cloning:

- **Need a second atomic-write flavor** (e.g. text, or fsync-durable)? Add one
  parameter to `core_wiring.atomic_write_json` (`durable: bool`), do not add a
  new writer. One function, one behavior, one place to audit.
- **Need git access from a module that can't import `core_nodes`** (circular)?
  Do not clone `_git`. Extract the ~5-line runner into a tiny leaf module
  (`core_git.py`) with no intra-project imports, and have `core_nodes`,
  `core_brain`, and nodes all import *that*. Break the cycle at the dependency,
  not by duplicating code.
- **Need per-action logging/throttling on desktop helpers**? Extend the single
  `_guarded(name, fn)` factory (e.g. add a rate limit or an event tag arg). Every
  helper inherits it for free; do not re-expand into per-method bodies.
- **Need richer runtime events**? Add fields at the single `log_runtime_event`
  call, keep `core_state.runtime_event` a thin pass-through. Do not reintroduce
  an intermediate reshaping dict.

Rule of thumb for reintroduction: if the new thing shares behavior with an
existing function, it is a **parameter or a shared leaf module**, not a new copy.
The bad way is copy-paste-and-tweak; the smart way is one owner + explicit
dependency.

---

## Reversibility

Every change is confined to code (no wiring/topology/prompt edits) and is a
plain `git revert` away. The consolidation is diff-reviewable as a single pass:
`git diff` shows +19 / −48 across the 6 files above.
