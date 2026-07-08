# endgame-ai System Review Report

Mode: autonomous /plan-style system review
Reviewer role: Analyst + Critic (read-only), self-critiquing via a Mixture-of-Experts (MoE) lens
Date: 2026-07-08
Branch under review: `live-test-run` (token-reduced organism)
Baseline vision: `main:README.md` (Phase 3 organism)

---

## 0. Method (MoE self-critique protocol)

I evaluate this project by routing each question to a specialized internal "expert"
and then reconciling their verdicts:

- E1 Architecture expert  — topology, bus routing, module boundaries.
- E2 Prompt-surface expert — token/LOC reduction quality, prompt bloat.
- E3 Safety expert        — exec sandbox, self-modify guardrails, gates.
- E4 Correctness expert   — event flow, state/journal sanity, contracts.
- E5 Docs-truth expert    — README vs code vs wiring consistency.

Each finding below is tagged with the expert(s) that produced it and a
confidence note. Where experts disagree, I record the disagreement rather than
hide it.

---

## 1. Ground truth (git + file census)

- Active branch: `live-test-run`, clean tree, tracks `origin/live-test-run`.
- Branches present: `main`, `token-reduction`, `codex/real-system-run`,
  `live-test-run`.
- Reduction commits (branch history):
  - `fc1c1b6` Reduce prompt surface and remove guardrail bloat
  - `5d869f4` Compact observation and execution runtime
  - `860289e` Hit LOC target with compact brain and node contracts
  - `79bd49d` Cross token and LOC reduction thresholds
  - `35466cc` Rewrite README as branch-truth architecture handover
  - `88485b5` reintroduction of file proxy

### Diff census: main -> live-test-run

Files fully deleted (7 source files):
- `analyze_graph.py` (-25)
- `check_events.py` (-10)
- `export_brain_forensics.py` (-420)
- `transport_browser_ai.py` (-4)
- `transport_openai.py` (-63)
- `transport_opencode.py` (-77)

Heavily reduced core:
- `core_brain.py`      608 -> mostly deletions (largest single code cut)
- `core_nodes.py`      695 changed (mostly deletions)
- `core_observation.py` 972 changed (majority deletions)
- `wiring.json`        265 changed (mostly deletions)
- `node_execute.py`    245 changed (mostly deletions)

Totals: 31 files changed, +3033 / -4690. README grew (+2832 net churn) while
code shrank. Reported: ~51% line reduction, ~44% char reduction on non-README
tracked code (24 files, 3038 counted lines vs 31 files / 6196 lines on main).

E5 note: the branch README's own numbers are internally consistent with the
`git diff --stat` I measured. Confidence: high.

---

## 2. Vision vs branch reality (E5 docs-truth)

The `main` README sells a **Phase 3 self-evolving Windows desktop organism**:
observe -> plan -> execute -> verify -> reflect -> self-modify, bus-routed,
goal-narrative memory, git-backed evolution with a `known_good` ref, forensics
tooling, multiple transports, and a `runtime_self_evolution_enabled.json` safety
gate. It is marketing-heavy (badges, emoji, mermaid diagrams, hard-coded example
counts like "253 probes / 79 elements / 34 nodes").

The `live-test-run` branch keeps the **organism core** and deletes the
**scaffolding**. Verified preserved behaviors (read in code, not just claimed):

- Bus-routed topology (`core_organism.next_node_for`, `core_bus.validate_signal`).
- Dynamic node hot-load (`core_node_base._load_node`).
- Dynamic transport hot-load (`core_brain._load_transport_module`).
- UIA RAW->FILTER->MAP observation (`core_observation.gather_raw/filter_raw/build_tree_and_map`).
- Goal-narrative `effective_goal` rewriting through nodes.
- `exec(code, ns)` execution with injected capability runtime.
- Full self-modify (file writes/deletes, wiring patches, commands, git commit,
  known-good ref, hot-swap).

Verified removed (confirmed by `git diff --stat` + code reads):
- `transport_openai.py`, `transport_opencode.py`, `transport_browser_ai.py`.
- `export_brain_forensics.py`, `analyze_graph.py`, `check_events.py`.
- `runtime_self_evolution_enabled.json` gate + `self_evolution_enabled()`.
- Per-node datasheets, write whitelists, JSON-schema validator, mermaid helper.
- Verbose prompts (rewritten from zero as compact contracts).

E5 verdict: The branch README is an unusually **honest handover doc**. It does
not overclaim — it explicitly lists what is no longer true and gives a
reintroduction path for each deletion. This is the single best thing about the
reduction. Confidence: high.

E5 caveat (self-contradiction the doc admits): the README grew from 750 to 2226
lines while the point of the branch was token reduction. If
`model.stable_prefix.enabled` is ever set true with README tracked+included,
this 81 KB file becomes prompt material and **erases the entire reduction gain**.
The doc flags this itself (good), but the risk is live and only a config flag
away. Confidence: high.

---

## 3. What the reduction got RIGHT (E1 + E2)

- **Cut the right layer.** The deletions are scaffolding (forensics scripts,
  unused transports, datasheets, schema theatre), not organism logic. The
  observe/plan/execute/verify/reflect loop and self-modify are intact. Removing
  duplication that lived simultaneously in code + prompts + docs + datasheets is
  the highest-value token cut available. (E2, high confidence.)
- **Single source of truth respected.** Topology, prompts, transport selection,
  observe config, and self-modify config remain centralized in `wiring.json`.
  UIA property/pattern IDs correctly moved from wiring into Python constants
  (`SCAN_PROPERTY_IDS`, `SCAN_PATTERN_IDS`) — those were never operator-tunable
  and were pure prompt weight. (E1, high.)
- **Compact record contract.** `core_brain._RECORD_RULES` replaces verbose
  per-node schema prose with a tight `(required_keys, enum_constraints)` table
  covering all 8 record types. This is the elegant heart of the reduction: one
  table enforces the whole LLM I/O contract. (E1+E4, high.)
- **Fail-hard over fallback.** Removing automatic transport fallbacks means
  failures surface instead of silently degrading. For a self-evolving system,
  loud failure is safer than quiet wrong behavior. (E3, medium-high.)
- **Reintroduction ledger.** Every deletion has a documented, minimal
  re-add path. This is reversibility done right and matches the entity contract
  ("small, explicit, reversible, justified"). (E5, high.)

---

## 4. What the reduction got WRONG / left dangerous (E3 + E4)

### 4.1 Safety gate deleted, application is unconditional (CRITICAL)
Verified in `core_organism.run` (~line 88): when `current == "node_self_modify"`
and a `git_evolution_patch` is present, the loop **immediately** calls
`nodes.apply_evolution_patch`, then `nodes.commit_self_evolution`, then reloads
wiring — with **no enable flag, no dry-run, no human gate**. Combined with
`node_self_modify` having **no path allowlist/denylist** on file_writes/deletes
and `_run_evolution_commands` using `shell=True`, the organism can rewrite its
own source and run arbitrary shell commands autonomously. The README calls this
"unsafe-by-design" and intentional. As a *design stance* it is coherent; as a
*shipped default on a branch named `live-test-run`* it is the top risk.
(E3, high confidence — verified in code.)

### 4.2 Unrestricted `exec(code, ns)` (CRITICAL, inherited not introduced)
`core_nodes.build_capability_runtime` injects `subprocess`, `os`, `sys`,
`ctypes`, live `wiring`/`state` refs, and `python_executable` with no
`__builtins__` restriction, no fs/network sandbox, no resource limits. This
predates the reduction, but the reduction *removed* the execute preflight that
previously classified/blocked some code (README "Execute Firmware/Git Preflight"
section). So the reduction made an already-dangerous path slightly more
dangerous. (E3, high — verified.)

### 4.3 `validate_wiring` is largely theatrical (HIGH, correctness)
Verified `core_wiring.validate_wiring` (~line 82): ~30 config paths are checked
with `_require(cfg, path, object)`. Since every Python value is an `object`, the
`isinstance(cur, object)` check **always passes** — these are existence checks
only, not type checks. The README admits this ("many inner config paths are
checked for existence with `object`, which every Python value satisfies").
Additionally, edge *targets* are never validated against `topology.nodes`, so a
malformed edge routes to a nonexistent node and fails only at dispatch time.
(E4, high — verified.)

### 4.4 Unbounded recursive error recovery (MEDIUM)
`core_organism.run` re-enters itself on routable errors with no depth counter.
A persistently-failing node can drive unbounded recursion / stack growth.
(E4, medium — flagged by subagent, consistent with code shape at ~line 121.)

### 4.5 Machine-specific bloat survived the "bloat removal" (LOW but ironic)
`core_observation.DESKTOP_ICON_NAMES` hardcodes ~17 developer-specific desktop
icon names. A reduction pass whose stated purpose was removing bloat left
personal machine state embedded in a core module. (E2, medium.)

### 4.6 No file locking on shared runtime files (LOW-MEDIUM)
`core_stop_check`, `core_wiring.atomic_write_json`, and state writes have no
locking. `atomic_write_json` can also orphan `.tmp` files if `os.replace`
fails. Concurrent organisms (a documented future goal) would corrupt state.
(E4, medium.)

---

## 5. MoE self-critique (turning the experts on myself)

Applying the same MoE lens to my own review, so this report does not become the
next piece of unverified folklore:

- **E5 challenges E1's "core intact" claim:** Did I confirm the *runtime* works,
  or only that the *code shape* matches the README? Honest answer: I verified
  structure and contracts by reading source; I did NOT execute the organism (it
  requires Windows 11 + UIA + `XAI_API_KEY`; this host is Linux). So "the loop is
  intact" is a static-analysis claim, not a live-run claim. The README asserts a
  "117-tick golden run" but I could not reproduce it here. Confidence downgraded
  accordingly.
- **E3 challenges E2's "cut the right layer" praise:** Removing the execute
  preflight and the evolution gate IS cutting organism-relevant safety logic, not
  pure scaffolding. So "only scaffolding was cut" is slightly too generous — some
  guardrails were cut too. I corrected section 4.2 to reflect this.
- **E4 challenges the char/line numbers:** I trust them because my own
  `git diff --stat` (+3033/-4690, 31 files) is consistent with the README's
  table. That is corroboration, not independent measurement of "counted lines"
  (their tokenizer definition is unknown). Confidence: medium-high, not certain.
- **Bias check:** The branch README is persuasive and well-written, which risks
  anchoring me to its framing. I mitigated this by verifying the two most
  load-bearing claims (gate removal, validate_wiring no-op) directly in source
  rather than trusting prose. Both checked out.

Residual unknowns (not verified): actual token counts under the target
tokenizer; whether `apply_evolution_patch` downstream guards paths (subagent
saw the proposal side in `node_self_modify`, and I saw the application call site
in `core_organism`, but I did not fully read `core_nodes.apply_evolution_patch`
line-by-line — its `_evolution_target` does a ROOT-parent containment check,
which is partial protection, symlink-bypassable per subagent).

---

## 6. Recommendations (mutable-area only, per entity contract)

Ranked, all reversible, none touching the immutable kernel's intent:

1. **Re-add a one-line evolution gate** in `core_organism.run` before
   `apply_evolution_patch` (README already specifies this exact insertion
   point). Cheapest possible safety restoration. (E3)
2. **Fix `validate_wiring` types**: replace `object` with real expected types
   and validate edge targets exist in `topology.nodes`. Removes false
   confidence for ~30 config paths. (E4)
3. **Add a recursion/error-depth budget** to `run()` to bound the self-recursive
   error recovery. (E4)
4. **Externalize `DESKTOP_ICON_NAMES`** into `observe_config` or an ignored
   local file; remove machine-specific data from core. (E2)
5. **Keep README out of `stable_prefix`** permanently — encode the skip in
   `core_brain.STATIC_PREFIX_SUFFIXES` or a skip-name set so no future flag flip
   silently re-inflates prompt size. (E2/E5)
6. If a sandbox is ever wanted, add a single `validate_execute_code(code, state)`
   call before `exec` rather than a framework. (E3)

Note: recommendations 1-6 are proposals for the mutable/plugin area or precise
edits; I have NOT applied any of them, consistent with the read-only Analyst/
Critic steering roles.

---

## 7. Verdict

The reduction is a **competent, honest, and largely correct** ~50% code cut that
preserved the organism and documented every deletion with a re-add path — a
model example of reversible refactoring. Its weaknesses are (a) an admitted but
live risk of README re-inflating prompt size, and (b) the deliberate removal of
the last safety guardrails (evolution gate + execute preflight) on top of an
already-unsandboxed `exec`, shipped as the default on a "live" branch. The
architecture is sound; the safety posture is intentionally naked. Good
engineering, dangerous defaults.
---

## 8. RUN-READINESS + REDUNDANCY PASS (follow-up focus)

Reframing note: autonomous self-rewrite is the **intended core**, not a defect.
The earlier "nobody watching" framing is withdrawn. This section answers the
questions that actually matter: does it run, did the topology survive the cut,
and what is still reducible.

### 8.1 Will it run? (verified)

- `python3 -m py_compile *.py` -> all 26 files compile clean. Windows-only
  imports (ctypes/UIA) are deferred inside functions, so non-Windows compile
  passes; runtime still needs Windows 11 + UIA + `XAI_API_KEY`.
- All 10 topology nodes export `run(ctx)`. Contract satisfied.
- Both transports export `call(messages, cfg)`. Contract satisfied.
- Conclusion: structurally runnable. No import-graph breakage from the cut.

### 8.2 Did the topology change / stay coherent? (verified via script)

Ran a reachability + integrity check against `wiring.json`:
- 10 nodes, each has both `edges` and a `prompt`. No gaps.
- Every edge target is a real node or `halt`. Zero dangling targets.
- All nodes reachable from `cycle_start = node_observe`. Zero orphans.
- Every node is a target of some edge (no unreachable islands).

The branch topology is **identical in shape** to main's Phase-3 topology (same
10 organs, same signal names, same `topology_patch`/`escalate` -> self_modify,
same `frame`->observe fresh-scan edges). The reduction did NOT alter the graph;
it only compacted the code and prompts behind each node. Good — the organism's
nervous system is preserved.

### 8.3 Redundancy: the "functions A/B/C doing the same thing" you asked for

These are the concrete near-duplicate clusters still present after the ~50% cut.
All verified by reading the bodies, not just names.

**Cluster 1 — atomic JSON write (4 implementations of one idea):**
| Location | Notes |
|----------|-------|
| `core_wiring.atomic_write_json` (L102) | canonical: tmp + `os.replace`, pid+tid suffix, indent=2 |
| `core_brain.atomic_write_json` (L168) | pure passthrough -> `wiring.atomic_write_json` (dead wrapper) |
| `transport_file_proxy._atomic_json` (L9) | re-implements the same tmp+replace, `.tmp` suffix |
| (`core_nodes._atomic_write_text` L60) | text sibling of the same pattern |
Reduce: keep `core_wiring.atomic_write_json`, delete the `core_brain` wrapper,
call the canonical one from `transport_file_proxy`. Net: remove 2 bodies.

**Cluster 2 — `load_json` (2 impls):**
- `core_wiring.load_json` (L20) canonical.
- `core_brain.load_json` (L164) is a pure passthrough wrapper. Dead.
Reduce: delete the wrapper; callers import from `core_wiring`.

**Cluster 3 — `_git` subprocess helper (3 near-identical impls):**
| Location | Return | Diff |
|----------|--------|------|
| `core_nodes._git` (L104) | CompletedProcess | has `check=` flag (superset) |
| `core_brain.StablePrefix._git` (L49) | stdout str | prefix-specific error msg |
| `node_self_modify._git` (L15) | stdout str | identical to brain's minus msg |
Reduce: promote `core_nodes._git` to the single git runner; the two stdout-only
callers wrap it as `_git([...]).stdout`. Net: remove ~2 bodies + unify error text.

**Cluster 4 — runtime event logging (indirection chain):**
- `core_state.runtime_event` (L50) -> builds a throwaway
  `{"event_log_path": ...}` dict -> calls `core_brain.log_runtime_event` (L204).
- `core_organism` sometimes calls `state.runtime_event`, other paths call
  `brain.log_runtime_event` directly. Two entry points, one behavior.
Reduce: make `core_state.runtime_event` a thin alias or route all callers to
`brain.log_runtime_event(w, ...)` directly. The intermediate dict rebuild is
pointless churn.

**Cluster 5 — desktop action helpers duplicated as closures:**
`core_nodes.build_capability_runtime` defines `click/type_text/press_key/hotkey/
scroll/open_url` (L392-431) that are 1:1 thin wrappers over the identical
`core_desktop.Desktop` methods, adding only `_assert_duration_open(...)` +
`_record_action(...)`. Six wrappers repeat the same two-line decoration.
Reduce: a single decorator/loop over method names would collapse six near-
identical closures into a table. Behavior identical, ~5x less code.

**Cluster 6 — value coercion helpers (single-use micro-fns):**
`core_observation` has `_unwrap/_to_int/_to_str/_to_bool/_to_rect/_to_runtime_id`
plus `_cached/_current/_pattern`. Legitimate, but `_cached` and `_current`
differ only by which cache call they make and could be one function with a flag.
Low priority.

**Dead/vestigial:**
- `core_bus.observation_brief` computes `tree` then never uses it (subagent
  finding, confirmed relevant).
- `core_brain.atomic_write_json` / `load_json` wrappers (Clusters 1-2) are dead
  indirection kept only so `core_state`/others import from `core_brain`.

### 8.4 Estimated additional reduction available

Conservative, behavior-preserving: consolidating Clusters 1-5 removes roughly
8-12 function bodies and ~60-100 lines with zero topology or contract change.
This is the "second pass" the branch README itself hints at ("remaining
reduction should focus on code/wiring, excluding README"). None of it touches
the self-evolution contract or the organism graph.

Priority order (highest value, lowest risk first):
1. Delete `core_brain.load_json` + `atomic_write_json` wrappers (Clusters 1-2).
2. Unify the 3 `_git` helpers on `core_nodes._git` (Cluster 3).
3. Table-drive the 6 desktop wrapper closures (Cluster 5).
4. Collapse `runtime_event` indirection (Cluster 4).
5. Remove unused `tree` in `observation_brief`.

All are reversible and confined to code (no wiring/topology edits), consistent
with the entity contract and the read-only stance of this review.
---

## 9. OOP / abstraction as a reduction lever — deduction

Question posed: can OOP (abstract classes, etc.) cut maybe half the code
*without* removing functionality, and make future extension easier?

Honest answer up front: **the high-value OOP abstraction already exists**
(`BaseNode`, template-method pattern). A second, disciplined abstraction pass
can still remove meaningful code and — more importantly — lower the cost of
adding new nodes, but "another ~50%" is not realistic. Below is the evidence and
the design.

### 9.1 What already exists (and is good)
`core_node_base.BaseNode` is a clean template method:
`run() -> think() -> build_payload()/signal_from_data()/patch_from_record()`.
The 6 LLM nodes (planner, verify, frame_action, execute, reflect, self_modify*)
subclass it; each supplies only its `prompt_key`, `expected_record_type`, and
the three hooks. The transport call, record-contract check, and bus emit are
written once. This is exactly the abstraction the question is reaching for — it
is already in place. Any proposal must build on it, not reinvent it.

### 9.2 What the per-node code actually is (measured)
Node file sizes: satisfied 8, observe 11, error 13, scheduler 20,
frame_action 35, verify 42, planner 43, self_modify 79, reflect 80, execute 85
(total ~416 LOC across 10 nodes; base+bus = 293).

Reading the bodies, the remaining per-node lines are **not boilerplate** — they
are genuine domain logic: intent-list validation, root-obligation guards,
success/signal cross-checks, completed-step bookkeeping. You cannot delete that
by abstraction; you can only relocate it. So the "half the code" hope mostly
does not apply to node internals.

### 9.3 Where OOP genuinely removes code (real wins)

**Win A — repeated `next_signal` validation.** Every LLM node hand-writes
`sig = data.get("next_signal"); if sig not in {…}: raise`. The allowed set is
*already* declared in two places (`wiring.topology.edges[node]` and
`core_brain._RECORD_RULES`). This is triplicated truth. Lift validation into
`BaseNode.run`: after `signal_from_data`, validate the signal against the record
rule's enum automatically. Removes the check from ~5 nodes and kills a
redundant source of truth. (~10-15 LOC + one fewer place to get wrong.)

**Win B — `effective_goal` rewrite ritual.** 23 sites across the nodes do the
same shape: `state.get("effective_goal", goal) + f"\n\n[TAG] …"`. That is a
cross-cutting concern crying out for one helper:
`append_goal(state, ctx, tag, text)`. Put it on `BaseNode` (and expose a
free function for the mechanical nodes). Collapses 23 ad-hoc string builds into
one call each. (~15-25 LOC and uniform narrative formatting.)

**Win C — mechanical nodes have no shared base at all.** scheduler, observe,
satisfied, error are bare `def run(ctx)` functions that each re-fetch
`state = ctx.get("state", {})`, re-read `effective_goal`, and hand-build a
`bus.emit`. A tiny `MechanicalNode` base (or just shared helpers) would remove
the repeated preamble. Modest (~10-20 LOC) but it makes the two node *kinds*
symmetric.

**Win D — payload/evidence overlap.** verify and frame_action build nearly the
same `evidence` dict (`last_action`/`last_result`/`last_error`/`state`) and the
same `{goal, step, evidence, observation}` payload shape. A couple of shared
mixin methods (`step_payload(ctx)`, `action_evidence(ctx)`) remove the
duplication without hiding intent. (~15-20 LOC.)

Realistic total from A-D: on the order of **60-90 LOC** removed, plus the
elimination of 1-2 redundant sources of truth. That is a real win, but it is
~15-20% of node code, not 50%.

### 9.4 The bigger payoff is extension cost, not line count
The stronger argument for OOP here is **future-proofing**, which the question
also raised and which matters more than LOC:

- Today, adding a node = new file + subclass + register in `wiring.json`
  (topology + prompt) + often re-implement signal validation and goal-append.
- With Wins A-C, adding an LLM node becomes: subclass `BaseNode`, set
  `prompt_key`/`expected_record_type`, implement `build_payload` +
  `patch_from_record`, done. Signal validation and goal narrative come for free
  from the base. That is the "easier to extend" property, delivered.
- A registry/factory (`NODE_TYPES = {…}` or auto-subclass discovery) could even
  remove the trailing `def run(ctx): return XNode().run(ctx)` shim every node
  currently repeats — 10 identical two-line shims → one dispatcher. But note:
  that trades the current *fully data-driven dynamic import* (`_load_node`
  reads `node_*.py` by name) for a registry. Given the "system is wiring
  between nodes" axiom and the self-modify path that writes new `node_*.py`
  files at runtime, **keep the file-per-node dynamic import** — a registry would
  fight self-evolution. So: abstract the *shared behavior* (base class), but do
  NOT centralize *node existence* into a registry.

### 9.5 Risks / where OOP would make it worse
- **Deep inheritance chains.** More than one base layer (e.g.
  `BaseNode -> LLMNode -> StepNode -> VerifyNode`) would hurt readability and
  fight the fail-hard ethos. Cap at one base + optional mixins.
- **Hiding domain logic.** Moving validation into base methods is good; moving
  node-specific guards (planner's root-obligation amputation check) into a base
  would obscure intent. Keep domain rules in the node.
- **Abstracting the mechanical/LLM split too hard.** They differ fundamentally
  (LLM nodes call the brain; mechanical nodes do not). One shared base for
  *state access + emit + goal-append* is fine; forcing them under one `think()`
  contract is not.

### 9.6 Verdict on the idea
Directionally correct, magnitude overstated. The template-method base already
captured the big win; a focused second pass (Wins A-D + goal-append helper)
removes ~60-90 LOC, deletes redundant signal-validation truth, and materially
lowers the cost of adding nodes. Do it as mixins/one base layer, keep node
domain logic explicit, and **do not** replace the dynamic file-per-node loader
with a registry — that dynamic loader is what makes runtime self-evolution
possible, and it is the one thing the axioms say to protect.

Recommended sequence (each independently revertible, no topology change):
1. Add `BaseNode._validate_signal_against_rules` and call it in `run`. (Win A)
2. Add `append_goal(state, ctx, tag, text)` helper; migrate the 23 sites. (Win B)
3. Introduce `MechanicalNode` base / shared preamble for the 4 bare nodes. (Win C)
4. Extract `step_payload`/`action_evidence` mixin for verify+frame_action. (Win D)

I have not implemented these — this is the deduction you asked for. Say which
wins to take and I will apply them one commit at a time with the same
compile+import+topology verification used in the consolidation pass.
---

## 10. The real goal: a minimal OOP core that is an on-demand extension platform

Restated so we are aligned: the target is a **small resting core** that can
**re-grow any capability on demand** — including everything in the 5000+ LOC
main branch (multiple transports, forensics, datasheets, schema validation,
browser AI, etc.) — as **uniformly-shaped plug-ins the core discovers and
loads**, so the codebase stays at minimum size while reachable capability is
maximal. Extension (bringing back old features or adding new ones) must be
cheap and not touch the core.

Deduction: **this is achievable, and the codebase is already 80% of the way
there by accident.** The current design is a plugin architecture that has not
been named as one.

### 10.1 The seam already exists
Two loaders already do dynamic, name-addressed, duck-typed loading:
- `core_node_base._load_node(name, w)` — imports `<name>.py`, requires `run(ctx)`.
- `core_brain._load_transport_module(name, w)` — imports `<name>.py`, requires
  `call(messages, cfg)`.

Both resolve a **string from `wiring.json`** to a file to a required symbol.
That is exactly a plugin registry keyed by config. The only thing missing is
that (a) it is informal (duck-typed, not an interface), (b) it exists only for
nodes and transports — not for the other extension axes, and (c) capabilities
(execute helpers) are hard-wired in one dict instead of contributed by plugins.

### 10.2 Target architecture: 4 plugin kinds behind 1 loader

Define one tiny protocol layer and one loader, then express **every** feature —
core and reintroduced — as a plugin of one of four kinds:

```text
CORE (small, stable, never grows):
  core_loader     resolve name -> module -> validated interface (one impl)
  core_bus        Record / NodeOutput / signal validation (already exists)
  core_organism   the loop: wiring between nodes (already exists)
  core_wiring     config SSOT (already exists)
  BaseNode / BaseTransport / BaseCapability / BaseTool  (abstract contracts)

PLUGINS (optional, discovered via wiring, live in their own files):
  1. Node        exports run(ctx)            e.g. node_planner, node_verify
  2. Transport   exports call(messages,cfg)  e.g. transport_xai, transport_openai
  3. Capability  contributes exec helpers    e.g. cap_desktop, cap_browser
  4. Tool        operator/forensics command  e.g. tool_forensics, tool_graph
```

The core knows the four **base contracts** and the loader. It does not know how
many nodes, transports, capabilities, or tools exist — that is `wiring.json`.

### 10.3 What changes vs. today (small, surgical)

- **Formalize the contracts as ABCs**: `BaseNode` (exists), add `BaseTransport`,
  `BaseCapability`, `BaseTool`. Each is ~5-10 lines: one abstract method + a
  `name`/`provides` attribute. The loader validates against the ABC instead of
  `hasattr`.
- **Make capabilities pluggable**: today `build_capability_runtime` hard-codes
  the helper dict and imports `core_desktop` directly. Instead, each capability
  plugin exposes `provides() -> dict[str, callable]`, and the runtime is the
  **merge of all capability plugins named in `wiring.capabilities`**. Desktop
  becomes `cap_desktop`; a future browser becomes `cap_browser` — added by one
  wiring line, zero core change.
- **Make tools pluggable**: forensics/graph/event scripts (deleted from main)
  come back as `tool_*.py` exposing `run(args)`, invoked by an operator entry
  point, never imported by the runtime loop. They cost zero runtime prompt
  surface because the core never loads them during a cycle.
- **One loader** (`core_loader.load(kind, name, w)`) replaces the two ad-hoc
  loaders. Node and transport loading collapse into it. Net: less loader code,
  one place for the import+validate+error contract.

### 10.4 Why this hits BOTH goals at once

- **Minimum resting size**: the core is only loop + bus + wiring + loader + 4
  tiny ABCs. Everything else is optional files that are only read when
  `wiring.json` names them. A stripped organism can ship with 1 transport, the
  desktop capability, and the current nodes — nothing else on disk needs to
  exist.
- **On-demand main-branch parity**: every deleted feature maps to exactly one
  plugin kind, re-addable without touching core:
  | Main-branch feature | Comes back as | Core change |
  |---------------------|---------------|-------------|
  | transport_openai / opencode / browser_ai | Transport plugin | none |
  | export_brain_forensics / analyze_graph / check_events | Tool plugin | none |
  | browser DOM control | Capability plugin (`cap_browser`) | none |
  | per-node datasheets / write whitelist | `BaseNode` mixin + `wiring.contracts` | none (base gains one optional check) |
  | JSON-schema validation | stricter `validate_wiring` (already the SSOT) | in-place |
  | self-evolution enable gate | `BaseTool` preflight or one loop check | one line |

  Reintroduction is *additive*: drop a file, add a wiring line. That is the
  "bring it back the smart way" property, generalized to the whole system.

- **Cheap new features**: a brand-new organ = new `node_*.py` subclassing
  `BaseNode` + 2 wiring lines. A brand-new sense/actuator = new `cap_*.py`
  subclassing `BaseCapability` + 1 wiring line. The marginal cost of capability
  is one file and one config line, forever.

### 10.5 Critical constraint (do not break self-evolution)
The plugin loader **must stay file-per-plugin and name-addressed**, exactly like
today's `_load_node`. Self-modify writes new `node_*.py`/`cap_*.py` files at
runtime and adds wiring lines; a compile-time registry or entry-point system
would make the organism unable to grow itself. So: ABC contracts for *shape*,
dynamic file loading for *existence*. This is the one hard rule the axioms
("system is wiring between nodes") force.

### 10.6 Feasibility and size estimate (deduction, not measured build)
- New core code: `core_loader` (~30 LOC), 3 new ABCs (~30 LOC total),
  capability-merge change in `build_capability_runtime` (~20 LOC net after
  removing the hard-coded dict), fold two loaders into one (net negative).
- Node internals shrink via §9 wins A-D (~60-90 LOC).
- Net core change is roughly flat-to-smaller, while the *architecture* becomes
  open-ended. The resting codebase does not grow; capability becomes unbounded.
- "Rewrite the whole architecture" is NOT required — this is a **refactor along
  seams that already exist**. That is a feature, not a compromise: a full
  rewrite would risk the working organism; a seam-refactor preserves it.

### 10.7 Recommended build order (each a verifiable commit, no topology change)
1. Introduce `core_loader.load(kind, name, w)`; migrate `_load_node` and
   `_load_transport_module` onto it. (Proves the unified loader.)
2. Add `BaseTransport` ABC; make `transport_xai`/`transport_file_proxy` subclass
   it; loader validates against it.
3. Add `BaseCapability` ABC + `wiring.capabilities` list; move desktop helpers
   into `cap_desktop.py`; `build_capability_runtime` = merge of named caps.
4. Add `BaseTool` ABC + `tool_*` operator entry point (out of the runtime loop);
   reintroduce forensics as `tool_forensics.py` to prove main-branch parity.
5. Apply §9 node wins (signal validation + `append_goal` in `BaseNode`).

After step 4 the claim is provable end-to-end: a deleted main-branch feature
(forensics) is back as a plugin, the core never grew, and the runtime prompt
surface is unchanged.

### 10.8 Verdict
The goal is coherent and achievable **without a rewrite**, because the current
code is already a config-driven, dynamically-loaded plugin system in disguise.
Formalizing four plugin contracts behind one loader turns "we deleted features
to save tokens" into "features are optional plugins we load on demand" — minimum
resting size, maximum reachable capability, cheap extension, and full backward
reach to the 5000-LOC main branch. The only inviolable constraint is keeping
plugin *existence* dynamic and file-based so self-evolution can keep writing new
plugins at runtime.

This section is deduction/design only — no code written. If you approve, I will
execute build order 1-5, one commit at a time, each with the compile + import +
topology verification already established this session.
---

## 11. RESUME ANCHOR (read this first after compaction)

State as of this checkpoint:
- Branch: `live-test-run`. Last commit: `983d890` (consolidation pass, +149/-2274).
- Consolidation (§8) is DONE and committed. Do not redo it.
- OOP deduction (§9) and plugin-platform architecture (§10) are DESIGN ONLY,
  approved by the user to execute.

Hard constraints (non-negotiable):
- Keep plugin EXISTENCE dynamic + file-based (`_load_node` style). ABCs define
  shape only. A compile-time registry is FORBIDDEN — it breaks self-evolution.
- HOT SWAP MUST KEEP WORKING: `core_nodes.hot_swap_to_known_good`,
  `resolve_known_good`/`update_known_good_ref`, and the self_modify apply path in
  `core_organism.run` (~line 88) must remain functional after every step.
- Fail hard, no fallbacks, no defensive branching. System = wiring between nodes.
- After every edit: `python3 -m py_compile *.py`, import smoke test of pure-py
  core, and the topology reachability script (§8.2). No topology/contract change.

EXECUTE build order (from §10.7), one commit each, verify before commit:
1. `core_loader.load(kind, name, w)`; migrate `_load_node` +
   `_load_transport_module` onto it (fold two loaders into one).
2. `BaseTransport` ABC; `transport_xai` + `transport_file_proxy` subclass it;
   loader validates against ABC.
3. `BaseCapability` ABC + `wiring.capabilities` list; move desktop helpers into
   `cap_desktop.py`; `build_capability_runtime` = merge of named cap plugins.
4. `BaseTool` ABC + operator entry point OFF the runtime loop; reintroduce
   `tool_forensics.py` (parses runtime_events.jsonl) to prove main-branch parity.
5. §9 node wins: signal validation in `BaseNode.run`; `append_goal(state, ctx,
   tag, text)` helper; migrate the 23 effective_goal sites; optional
   `MechanicalNode` base for scheduler/observe/satisfied/error.

Verify hot-swap survives after steps 1-4 (loaders + self_modify path unchanged
in behavior). Keep README as living doc: after each step, update it to describe
what the plugin kind is and how to bring back / add features the smart way.
---

## 12. RECONCILIATION: fractal topology vision + plugin platform (post-compaction directive)

New directive from operator: build toward the **main-branch fractal topology
vision** (README Appendix B), NOT the legacy linear pipeline. Produce the
visionary topology. Still: no fallbacks, code reduction, OOP/unification. Also:
system is Windows-11-only; `transport_file_proxy` is the WSL2/PowerShell debug
endpoint (writes request to disk, operator-as-LLM answers).

### 12.1 The two designs are complementary, not competing
- §10 plugin platform = the **substrate** (how organs/senses/transports/tools
  are loaded and shaped).
- Appendix B fractal topology = the **behavior** the substrate must support
  (parallel one-to-many, barrier fan-in, node instances, recursive spawn,
  runtime rewiring).
- The plugin loader is what makes fractal cheap: `node_execute:browser` is the
  same `NodeExecute` class loaded once and *instanced* with param `browser`.

### 12.2 What the current code assumes (the linear constraint to break)
- `core_organism.next_node_for` returns ONE string; loop does `current = nxt`.
  Strictly sequential, single-successor.
- `core_bus.allowed_signals` reads `edges[node].keys()`; edge VALUE is assumed a
  single node name string.
- Node names are 1:1 with files (`node_execute.py` -> `node_execute`). No
  `name:instance` concept.
- `next_node_for` value must be a string; a list would break it today.

### 12.3 Fractal primitives to add (mapped to plugin substrate)
1. **Node instances (`node_execute:browser`)**: split `name:instance` at load.
   `core_loader` resolves the CLASS from `name`, passes `instance` as a param in
   ctx. One class, many wired instances — pure win for code reduction (the whole
   point: browser/editor/terminal executors are ONE class).
2. **One-to-many edges**: edge value may be a list of targets -> parallel
   dispatch. Loop must handle a *frontier* (set of active nodes), not one
   `current`.
3. **Barrier / fan-in**: a `NodeBarrier` mechanical node (or a join rule in the
   loop) waits for all inbound branches before firing its successor.
4. **Recursive spawn (`spawn_organism`)**: a Capability plugin `cap_spawn`
   exposing `spawn_organism(goal, duration)` -> runs `core_organism` as child
   process, returns child's `effective_goal`. Each node becomes a potential
   organism = the fractal claim. Depth gate via wiring
   (`fractal.max_recursion_depth`, default 3).
5. **Runtime topology patch**: reflect emits `topology_patch`; self_modify
   applies via existing `apply_evolution_patch` extended with topology ops;
   hot-swap on failure. Topology becomes evolvable substrate.

### 12.4 Ordering constraint / risk
The fractal loop (frontier + barrier) is the RISKY core change — it rewrites the
organism main loop. The plugin substrate (loader, ABCs, instances) is LOW risk
and is the prerequisite. So build substrate first, prove it linear, THEN turn on
fractal behavior. Each still one commit, each verified, each revertible.

### 12.5 REVISED build order (supersedes §10.7/§11 order)
Phase A — substrate (behavior-preserving, linear still works):
  A1. `core_loader.load(kind, name, w)` unify `_load_node` +
      `_load_transport_module`. Support `name:instance` split (instance flows
      into ctx; linear topology unaffected because current names have no ':').
  A2. `BaseTransport` ABC; xai + file_proxy subclass; loader validates.
  A3. `BaseCapability` ABC + `wiring.capabilities`; desktop -> `cap_desktop.py`;
      runtime = merge of named caps.
  A4. `BaseTool` ABC + operator entry point off the loop; `tool_forensics.py`.
  A5. §9 node wins: signal validation + `append_goal` in `BaseNode`.
Phase B — fractal behavior (the vision; changes the loop):
  B1. `core_bus`: allow list-valued edges; `allowed_signals`/`validate_signal`
      + `next_node_for` return list of successors.
  B2. `core_organism`: frontier-based loop (set of active nodes) replacing single
      `current`; sequential remains a frontier of size 1.
  B3. `NodeBarrier` mechanical node + join semantics for fan-in.
  B4. `cap_spawn.spawn_organism` capability (recursive child organism) + depth
      gate in wiring.
  B5. Extend `apply_evolution_patch` with topology ops so reflect can rewire
      mid-run (runtime topology patch).
  B6. Rewrite `wiring.json` topology from linear -> fractal (one-to-many execute
      by capability, barrier fan-in to reflect). THIS is "produce the visionary
      topology." Verify reachability under new list-edge semantics.

Verify after every step: `python3 -m py_compile *.py`, pure-py import smoke,
topology reachability (updated for list edges in Phase B). Hot-swap + self_modify
apply path must keep working through the whole sequence.

STARTING NOW: Phase A1. Pause for operator review after A1 (per instruction).
---

## 13. Deduction correction (operator directive: no questions, node+wiring only)

Operator clarified the axiom hard: the system is ONLY nodes + wiring, everything
hot-swappable, no branching, no questions. The file_proxy brain (me) is now part
of the system. Deduct and go; keep `wiring.json` prompts + contracts aligned.

Revising the Phase A plan where it fought the axiom:

- **A2 CANCELLED (BaseTransport ABC).** The transport contract is already
  complete and minimal: a module-level `call(messages, cfg) -> {content,
  reasoning, ...}`. Existence is checked by `core_loader` (export=`call`);
  return SHAPE is checked by `core_brain.call` (the `contract violation` raises).
  Adding an ABC would ADD lines and ceremony and fight the pattern that
  self-evolution uses (write a `.py` exporting `call`). That violates the code-
  reduction requirement and the no-ceremony axiom. The contract is documented in
  one line in `core_loader.KINDS`. Same reasoning applies to a `BaseTransport`-
  style ABC for tools: contracts, not class trees.
- **Capabilities are the real dedup (kept, promoted).** `node_execute` +
  instances (`:browser`/`:editor`/`:terminal`) collapse many executors into one
  class — that is genuine reduction and the fractal one-class-many-instances
  win. Capability sets are merged from wiring, not hard-coded.
- **§9 node wins kept** (signal validation + `append_goal`): real LOC removal.
- **Phase B (fractal) is the point**: frontier loop, list edges, barrier,
  spawn, runtime rewiring, then rewrite `wiring.json` into the visionary
  topology with aligned prompts/contracts.

Principle locked: prefer the FUNCTION/plugin contract enforced at the loader +
call site over class hierarchies. ABC only where it removes duplication
(BaseNode does; BaseTransport/BaseTool do not). Fewer moving parts wins.

Executing the rest of Phase A + Phase B autonomously, no gating questions.
---

## 14. A5 applied: goal-narrative unification (signal-guard removal REJECTED)

Added `core_bus.current_goal(state, ctx)` and `core_bus.append_goal(state, ctx,
note)` — single source for the `effective_goal` read (`effective_goal` else
`ctx.goal` else "") and the `base + "\n\n[TAG] ..."` append ritual. Migrated 12
sites across 8 nodes (satisfied, scheduler, error, frame_action, verify, reflect,
execute, self_modify). Proven byte-identical to the old inline expressions by
unit assertion; topology intact; all compile + import clean.

REJECTED (behavior-changing, not dead code): lifting the per-node `next_signal`
enum guards (planner `{step_ready,reflect}`, reflect's 6-signal set, verify's
signal↔success coupling) into `BaseNode`. Reason: `bus.validate_signal` checks
against `topology.edges[node]` which is a SUPERSET (it also allows `error`). The
node-local guards deliberately EXCLUDE `error` and, for verify, couple the
signal to `self._success`. Removing them would let an LLM emit `next_signal:
"error"` and pass — a behavior change, not a reduction. Per the §9 principle
(keep domain rules in the node; ABC only where it removes true duplication), the
guards stay. Enum ≠ redundant here because it encodes "the node may not
self-route to error."

Phase A substantive work is complete (A1 loader; A2 cancelled as ceremony; A5
goal helpers). Capability-extraction (old A3) folded into Phase B, where
`node_execute:instance` makes one-class-many-instances actually pay off.
Next: Phase B — fractal loop (list edges + frontier), barrier, spawn, runtime
rewiring, then rewrite wiring.json into the visionary topology with aligned
prompts/contracts.
---

## 15. CRITICAL FIX: kill narrative truncations + de-bloat goal helpers (operator directive)

Operator flagged two things, both correct:

1. **Truncations are a critical defect.** Every node narrates its interpretation
   of the goal into `effective_goal`; the next node reads it. That narrative is
   the meta-mechanism that non-deterministically breaks loops and moves the
   organism forward ("everyone knows how others interpret the goal"). Slicing
   those strings (`lesson[:100]`, `code[:120]`, `descs[:3]`, ...) LOPS OFF the
   interpretation mid-thought — corrupting exactly that mechanism. Removed ALL
   narrative truncations:
   - node_execute: `code[:120]`, `error[:80]` (+ removed misleading literal `...`)
   - node_frame_action: `notes[:200]`
   - node_reflect: `lesson[:100]`, `diagnosis[:100]`
   - node_verify: `desc[:100]` x2, `reasoning[:100]`
   - node_error: `error[:100]`
   - node_self_modify: `summary[:150]`
   - node_planner: `descs[:3]` (was DROPPING plan steps from the narrative)
   - transport_xai: HTTP error body `[:2000]` (full error now visible)
   Principle: if information is not wanted, FILTER at the source; never truncate
   the organism's own narrative. `truncation: "disabled"` in xai stays (that is
   the correct anti-truncation setting). `max_output_tokens` per-organ are wiring
   dials (operator's choice), not code truncation — left to wiring.

   KEPT (legitimate, not narrative data loss): cache/conv-id hash slices
   (`fingerprint[:24]`, md5`[:8]`, sha256`[:16]`), git commit SUBJECT `title[:60]`
   (full summary/rationale go in the commit BODY uncut), scan_stats
   `first_point_errors errors[:5]` (debug telemetry sample), git porcelain
   fixed-field parse (`row[:2]`, `row[3:]`).

2. **`current_goal`/`append_goal` were bloat.** A one-line expression wrapped in
   a named function + docstring is the ceremony we are removing. Deleted both
   helpers. Root cause of the repetition was the `ctx.get("goal","")` FALLBACK —
   which was defensive branching. Fixed at the source: seed
   `st.setdefault("effective_goal", st["goal"])` ONCE at organism start
   (core_organism), so `effective_goal` is always present. Every node now reads
   `state["effective_goal"]` directly — hard key access, no function, no
   fallback, no docstring. Non-defensive: if the seed is ever missing that is a
   real bug and should raise, not silently fall back.

This reverses part of A5 (§14): the helpers are gone, but the intent (single
source, no per-node fallback) is achieved more directly by seeding once. Net
LOC lower than A5. Behavior for the goal narrative is now FULL-FIDELITY
(previously lossy) — an intentional behavior improvement, not just a refactor.

Verified: py_compile all, core import smoke, no residual helper refs, no
narrative `[:N]`, `bus` still used in every touched node, check_topology exit 0.
---

## 16. LIVE RUN ATTEMPT (file_proxy, WSL2) — findings

Goal: "open shakira latest video on youtube and play it", 60s, transport
file_proxy, me as the LLM answering on-disk requests.

Hard reality confirmed: the system is Windows-11-only. `cycle_start` is
`node_observe`, which imports `core_desktop -> comtypes` (Windows UIA). On WSL2
that raises `ModuleNotFoundError: comtypes` at the first node. There is no
fallback (by design). So a true end-to-end run is impossible from WSL2; only
non-desktop nodes (planner) can execute.

Two REAL bugs surfaced before any desktop dependency (valuable):

1. **CONTRACT MISALIGNMENT (fixed): file_proxy transport missing `reasoning`.**
   `core_brain.think` hard-reads `cfg["reasoning"]` (line ~302). `transport_xai`
   config has a `reasoning` block; `transport_file_proxy` did NOT — so selecting
   file_proxy raised `KeyError: 'reasoning'` before any brain call. This is
   exactly the "prompts/contracts must stay aligned" class of defect. Fix: added
   the `reasoning` block to `model.transport_config.transport_file_proxy` in
   wiring.json (enabled:false, pattern:native — the anti-truncation/no-multi-pass
   setting). This is a wiring alignment fix, not code. KEPT.

2. **`fresh_observation` gate is correct and firing.** `think` refuses to call
   the brain unless a prior observation exists ("observe node must run before any
   brain call"). Starting at planner (to skip desktop) correctly hits this guard.
   Not a bug — a contract. To exercise a brain call off-Windows you must seed a
   fake `fresh_observation` with non-empty `desktop_tree_text`.

3. **ROBUSTNESS GAP (noted, NOT yet fixed): error-routing hot-loop.** When a node
   errors repeatedly, `core_organism`'s except-branch recursively re-calls `run`
   with `start_node=<error target>`. With a persistently failing node this
   becomes a TIGHT infinite loop (observed hundreds of identical
   `[ERROR NODE] ... KeyError: 'paths'` lines in ~seconds, hot-spinning CPU, only
   stopped by SIGKILL). The `KeyError: 'paths'` itself was triggered by a
   hand-seeded partial state in the harness (loader/resume read a dict lacking
   `paths`), so that specific key is a test artifact — but the UNBOUNDED,
   NO-BACKOFF error recursion is a genuine defect: a failure_streak cap should
   halt (or at least backoff) instead of spinning. Candidate fix for a later
   step: bound error-routing recursion depth / consecutive-error count in the
   loop and halt hard when exceeded (fail hard, not fail forever).

What WORKED: unified loader resolves transport by name; file_proxy config now
passes validate_wiring; reasoning fix lets `think` proceed to the observation
gate; topology coherent; all modules compile. What is UNPROVEN on this host:
the actual file_proxy request/response round-trip (blocked first by the
reasoning KeyError, then by the observation gate; a real round-trip needs a
seeded observation AND a clean state, or a Windows host).

Harness cleanup: transport restored to transport_xai; runtime_*.json removed;
only wiring.json (reasoning alignment) left modified, to be committed.
---

## 17. FIX: bound the error-routing hot-loop (§16 robustness gap)

The §16 defect: `core_organism.run`'s `except Exception` branch recursively
re-calls `run(start_node=<error target>)`. A node that fails on every entry
whose `error` edge leads back to a still-failing node recursed FOREVER
(unbounded stack + CPU hot-spin, only killable by SIGKILL). Wall-clock deadline
did not save it because each recursion was cheap.

Fix (fail hard, no backoff/ceremony — axiom-aligned):
- `error_streak` counter lives in STATE (persists across the recursive re-entry
  because re-entry loads state from disk with `reset=False`).
- Every SUCCESSFUL node completion resets `st["error_streak"] = 0` (main loop).
- The error branch increments `error_streak`, and when it reaches
  `topology.max_error_streak` it HALTS HARD (`_phase="halted"`, records the
  streak in `last_error`) instead of recursing. No backoff, no retry — loud stop.
- New wiring key `topology.max_error_streak` (default 5), added to
  `validate_wiring` required paths (contract alignment: code hard-reads
  `w["topology"]["max_error_streak"]`).

This preserves the existing two termination paths (halt signal; routing-failure
`except RuntimeError`) and adds a third: persistent-failure streak cap.

Verified:
- compile all, import smoke, check_topology exit 0, validate_wiring accepts.
- Behavioral test A: monkeypatched `call_node` to always raise + a self-looping
  `node_planner.error -> node_planner` edge (the exact previously-infinite
  shape). Result: halted at `error_streak == 5`, exactly 5 `call_node`
  invocations, no infinite loop.
- Behavioral test B: always-fail with the real topology halted via the existing
  routing-failure path (node_error has no error edge). Both paths intact.
