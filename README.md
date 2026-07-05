# endgame-ai

A local desktop organism. Python is the mechanical body (mouse, keyboard, subprocess, UIA
observation), LLM transports are the interchangeable mind, and `wiring.json` is the circuit
diagram: a fixed topology of organs routes one signal per node through
observe → plan → act → verify → recover. The organism can generate and run arbitrary code and
drive real input, which is what makes self-evolution possible — and what makes discipline about
observation quality, prompt shape, and failure bounds non-optional.

This README is not a feature tour. It is a **correction plan** with one organizing thesis:

> **The codebase is a stalled procedural→OOP migration.** Classes were introduced
> (`Desktop`, `BaseNode`, `CachedNode`) but the procedural scaffolding around them was never
> removed. The result is layers of thin pass-through functions and duplicated helpers that
> inflate the line count without adding behavior. Finishing the migration — not adding new
> abstractions — is the cleanup.

Every item below is stated as *what it is*, then **Why** (2 sentences) and **Why not / cost**
(2 sentences). The goal is a system that works, works cheaply, and can be driven by a small
local model. Observation quality is the functional centerpiece; the OOP consolidation is the
structural one, and the two meet in `core_observation.py`.

**Evidence base (measured this session).** Every file was read. The file_proxy loop was run
end-to-end and physically opened Notepad. An AST scan classified all functions. xAI transport
fields were verified against live xAI docs. Numbers below are measured, not estimated:

- Total: **4540 LOC across 23 `.py` files** (`core_observation.py` 1088, `core_nodes.py` 755,
  `core_brain.py` 701, `core_organism.py` 273, `core_desktop.py` 315).
- **132 of 223 functions (59%) have ≤3 statements.** 28 are single-return pass-throughs
  (return a call/subscript/attribute); several are dead (no callers).
- A **triple-hop delegation layer** exists for desktop access:
  `core_nodes.observe_screen(ctx)` → `core_desktop.observe_screen()` →
  `get_desktop().observe_screen()`. The `core_nodes` copies take a `ctx` they ignore and have
  **no callers** (grep-confirmed).

Reaching the old ~2500-LOC size by dedup alone is **not** achievable — the delta is partly
genuine features (framing, self-modify manifests, structured outputs). Dedup realistically
recovers **~230–310 LOC**; the rest would require removing features, which this plan does not do.

---

## How it runs (minimum operator knowledge)

```powershell
python core_organism.py --reset --max-ticks 5 "Open Notepad and write hello"   # fresh, staged
python core_organism.py --max-ticks 3                                           # resume +3 ticks
python -c "import core_stop_check as s; s.request_stop('halt')"                 # cooperative stop
```

- One completed node = one `tick`. On resume, `--max-ticks N` means N *additional* ticks.
- Transport is chosen by `wiring.json` `model.transport`. Fail-hard: no silent fallback.
- Boot: `node_observe` (full UIA scan) → planner → scheduler → observe → execute → verify →
  (reflect / self_modify) → satisfied → halt. All 10 nodes reachable; no dangling edges.
- Runtime artifacts are flat `runtime_*` files, all gitignored. `runtime_request.json` /
  `runtime_response.json` are the file_proxy brain channel.

**Transports are NOT unified, and should not be.** `transport_xai` posts to `/v1/responses`
(`input`, `text.format`, `reasoning.effort` = `none|low|medium|high`, `prompt_cache_key`).
`transport_openai` posts to `/v1/chat/completions` (`messages`, `response_format`).
`transport_file_proxy` writes/polls files. Each owns its request shape by design;
`core_brain.think()` is the only unification point (one `call(messages, cfg)` contract).

---

## Section 0 — Finish the OOP migration (the newly-found, highest-structural-value work)

This section is new: it is the through-line that connects the pass-through functions, the
duplicated helpers, and the half-adopted base classes. Do these before cosmetic dedup, because
each one deletes a whole category of small functions at once.

### 0.1 Delete the dead `core_nodes` desktop-delegation layer
`core_nodes` defines `observe_screen`, `last_desktop_tree`, `get_focused_title`,
`_get_desktop_instance`, each a one-line pass-through to the identically-named `core_desktop`
function, each taking a `ctx` it ignores. Grep shows **no callers** outside the file.
**Why:** these are dead code — the definition of non-compounding — and removing them proves the
pass-through pattern on the lowest-risk target (~20 LOC, near-zero risk).
**Why not:** `build_capability_runtime` may reference some by name when building the exec
namespace, so confirm that before deleting and keep any name the runtime actually injects.

### 0.2 Collapse the `core_desktop` module-level delegators
`core_desktop` exposes module-level `observe/observe_screen/last_desktop_tree/last_action_index/
get_focused_title`, each just `get_desktop().<same>()`. This is a procedural facade over a class
that already has these methods.
**Why:** callers can use `get_desktop().x()` (or a single injected desktop handle) directly,
removing a whole hop and ~25 LOC of wrapper+padding.
**Why not:** the facade gives one import surface, so if many call sites use it, keep a *thin*
accessor (`get_desktop()`) and delete only the per-method wrappers, not the singleton itself.

### 0.3 Finish the `BaseNode` adoption (generalize, then subclass)
`BaseNode` exists but only `node_planner` uses it; `verify/reflect/frame_action/execute`
re-implement the think→check-record-type→emit skeleton as free functions. `BaseNode.run()`
hardcodes the payload, which is why the others could not adopt it.
**Why:** adding a `build_payload(ctx)` hook (default = current planner payload) lets all five
share the skeleton, enforcing the one-record/one-signal/one-patch contract in one place
(~40–55 LOC measured, medium value).
**Why not:** `execute` and `self_modify` carry real per-node logic (exec sandbox, git patch
apply) that must **not** be pulled into the base — subclass only the shared skeleton and keep
those bodies explicit, or the base becomes a leaky god-class.

### 0.4 Fold observation's tiny helpers into a scanner class
`core_observation.py` threads `automation`, `scan_cfg`, `property_ids`, `pattern_ids` through
~15 free functions (`_harvest_*`, `_get_cached/current`, `_element_to_node`, `_probe`), and
holds a scatter of one-liners (`_variant_*`, `_const`, `rect_area`, `contains`, `clean`).
**Why:** holding that state as `self.*` on a `UiaScanner`/`ObservationFilter` class removes the
repeated parameters and the plumbing that forwards them (~120–180 LOC, the single biggest win),
and the `_variant_*` staticmethods then also serve `core_desktop`, retiring the old "make
core_uia.py" idea (no new file needed — use a class in the existing module).
**Why not:** this is the code that physically drove the proven scan, so it must be a pure
structural port with **no behavior change in the same commit**, re-running the observe→execute
smoke test before commit; the Section-1 relevance work comes *after* this lands.

---

## Section 1 — Observation: cost and correctness bottleneck (functional priority)

Do 0.4 first (it creates the clean seam these edits need), then:

### 1.1 Add goal/step-relevance ranking to the filter
Today the filter emits every actionable node with only crude ranking, so an unrelated
foreground app dominates the tree — this session a YouTube window flooded the request from
~2.9KB to ~7KB. Rank nodes by relevance to the current step and keep a top-N slice.
**Why:** request size and node ambiguity are the biggest driver of cost and wrong clicks, and a
small model degrades sharply as the tree grows. Ranking makes every downstream organ cheaper.
**Why not:** scoring can hide a node the plan needs, causing a false "CANNOT"; keep the focused
window fully and apply the cap to non-focused windows only.

### 1.2 Cap action nodes per non-focused window
Any window can currently contribute up to `max_action_nodes` (240), so a busy browser consumes
the whole budget. Reserve the budget for the window the step is about.
**Why:** the focused window is almost always where the next action happens; capping background
windows preserves signal without a semantic model.
**Why not:** some goals span windows, so make the cap a soft reserve, not a hard exclusion, or
cross-window steps silently lose their target.

### 1.3 Bound scan latency
Observe took 2.38s clean vs 6.25s with a rich Chrome page foreground; cost scales with UI
density. Add a probe-time budget or adaptive `step_px`.
**Why:** unbounded scan time makes tick cost and file_proxy timeouts unpredictable, hurting the
cheap-brain loop that pays per call.
**Why not:** a hard budget can truncate a dense screen and drop the target, so early-stop must
prioritize the focused window before cutting.

---

## Section 2 — Dead declarative surface (low risk, do anytime)

### 2.1 Delete dead `transport_grok_cli` config
`wiring.json` lists `transport_grok_cli` under `transport_config` but there is **no module**
(grok CLI lives inside `transport_xai` as `mode="cli"`). `transport_browser_ai.py` is a
fail-hard stub.
**Why:** dead config forces every reader (human and the self-modify organ) to reconcile options
that cannot run — non-compounding surface.
**Why not:** the browser stub may be a roadmap marker, so delete `grok_cli` outright but keep
`browser_ai` only with a one-line "not implemented" note.

### 2.2 Remove the phantom LLM contract for mechanical nodes
`core_brain._RECORD_DATA_SCHEMAS` defines `schedule` and `satisfied` schemas and `wiring.json`
has prompts for them, yet `node_scheduler`/`node_satisfied` never call the brain.
**Why:** removing them shrinks the contract to what actually executes, so the declarative layer
stops describing a path that does not exist.
**Why not:** a future variant might make scheduling LLM-driven, so if kept, mark them "reserved,
mechanical today" rather than leaving them look active.

---

## Section 3 — Prompts & reasoning config (one source of truth)

### 3.1 Kill the code copy of reasoning-effort policy
`core_brain.think()` hardcodes a `default_effort_map` that duplicates
`wiring.model.organs.*.reasoning_effort`; when an organ key is absent, the code silently
shadows wiring.
**Why:** effort is a brain tuning knob that belongs in mutable wiring, and one source prevents a
wiring edit from being silently ignored.
**Why not:** a wiring omission would then send no effort, so fall back to a single named default
("low") rather than a full shadow map.

### 3.2 Retire the dead `global.reasoning_enabled` flag
It is `true`, but `_effective_reasoning_config` reads each transport's own `reasoning.enabled`
first (false for file_proxy/openai/opencode), so the global flag changes nothing.
**Why:** a config that looks authoritative but is a no-op is a trap for operators and the
self-modify organ; removing it makes reasoning state legible per transport.
**Why not:** if any tooling reads it as a display hint, replace it with a derived read-only
summary rather than deleting blind.

### 3.3 Decide stable-prefix / cache posture per transport
`StablePrefix` renders the checked-out source as a fixed leading block for provider caching but
is disabled. xAI docs confirm caching is automatic on shared starting messages and
`prompt_cache_key` (already set by `transport_xai`) pins routing.
**Why:** for a paid large-context provider, prefix + stable key is real money saved on repeated
ticks; leaving it off forgoes free cache hits.
**Why not:** for a 4B local model the same prefix is pure context bloat, so make this a
per-transport switch (on for xai, off for local), never global.

### 3.4 Protect the computer-use prompt shape (do not regress)
Planner/execute prompts state body truth (full Python, helpers are conveniences), enumerate the
record contract, and forbid self-declared success (verify owns truth). This session execute
correctly chose `subprocess` over clicking a non-existent node.
**Why:** these steer away from agent theater and match the id-based tree the brain receives,
exactly what a small model needs.
**Why not:** every rule spends tokens a 4B can ill afford, so trim or sharpen — never
accumulate — and measure before adding a sentence.

---

## Section 4 — Topology & failure control

### 4.1 Add a failure circuit breaker (highest topology risk)
`node_reflect` computes a `failure_streak` count but only uses `count >= 2` to upgrade to
`frame`; it never forces `give_up`. A failing self-modify can loop
escalate → self_modify → error → reflect → escalate, bounded only by `--max-ticks`.
**Why:** an organism that can rewrite itself must have an internal stop, or a weak patch loop
burns brain calls and can thrash the repo until the tick budget ends.
**Why not:** a breaker that trips too early kills legitimate multi-attempt recovery, so force
`give_up` only after a bounded streak on the *same* failure signature (already computed).

### 4.2 Gate `self_modify` behind a high-reasoning transport
A correct full-file `git_evolution_patch` that compiles and preserves the bus contract is a
strong-model task; a 4B here is the main driver of the 4.1 loop.
**Why:** matching the hardest organ to the strongest brain (cheap organs stay local) raises the
ceiling without one big model.
**Why not:** a hard gate removes self-evolution when only a local model is available, so degrade
to "propose patch, do not apply" (feeds the dual-agent idea) rather than refuse.

### 4.3 Keep fail-hard routing (do not regress)
Missing transport, edge, or `fresh_observation` all raise; exceptions route to `node_error`.
Reachability verified: 10/10 nodes reachable, no dangling edges, error edges everywhere except
the terminal `satisfied`/`error`.
**Why:** loud, legible failure beats silent recovery in a system that touches a real desktop.
**Why not:** fail-hard plus the missing breaker (4.1) is what enables the runaway loop, so 4.1
is the required complement — do not soften fail-hard to compensate.

---

## Section 5 — 4B local model & readiness

### 5.1 Use the 4B as actuator/verifier, not planner/self-modifier
The local nemotron reliably drives mechanical organs and simple single-app steps (proven this
session) but is unreliable for branching plans, long horizons, and self-modification.
**Why:** splitting organs across transports (cheap model for execute/verify, stronger for
plan/self_modify) is already supported by wiring and is the path to "works cheap."
**Why not:** two brains add latency and orchestration, so a single 4B is fine for simple linear
goals — split only when a goal needs planning depth.

### 5.2 The 4B ceiling moves with observation, not parameters
On a clean tree the 4B picks the right node; on the 7KB flooded tree it likely clicks the wrong
one. Section 1 (and its prerequisite 0.4) is the real lever.
**Why:** this reframes "model too small" as "input too noisy" — a fixable engineering problem.
**Why not:** observation fixes cannot make a 4B plan a ten-step branching task, so still expect
a stronger planner on hard goals.

### 5.3 Add a minimal test harness (readiness gap)
There is no test harness; correctness is verified by running the organism and reading logs. The
topology, the bus contract, and `filter_gather` output shape are testable without a live desktop.
**Why:** every Section 0/1/4 refactor is risky precisely because nothing catches a regression,
and topology/contract/filter tests are cheap and desktop-free.
**Why not:** UIA scan and real actuation are hard to test without Windows in CI, so cover
contract/topology/filter now and leave desktop actuation as manual smoke tests.

---

## Recommended order (safety × payoff)

1. **0.1** dead node-delegators (verify no runtime refs) — safest, proves the pattern.
2. **2.1 / 2.2 / 3.1 / 3.2** dead config + policy dedup — low risk, quick LOC + clarity.
3. **0.2** collapse desktop facade — low risk.
4. **0.3** generalize `BaseNode`, adopt in 4 nodes — medium risk, add contract tests (5.3) first.
5. **0.4** observation → scanner/filter classes — biggest win, highest risk; pure structural
   port + smoke test, no behavior change in the commit.
6. **1.1–1.3** observation relevance/caps/latency — behavior change, measure before/after.
7. **4.1** circuit breaker; **4.2** self_modify gating.

**Invariant for every step:** re-run the observe→execute smoke test (open Notepad) before
committing. Proven-working behaviors that must not regress: end-to-end file_proxy control,
resume/tick control, cooperative stop, and self-evolution guardrails (path allowlist,
compile+JSON validation before and after write, snapshot rollback).

---

## Appendix — file_proxy behavioral log & future dual-agent brain

**Two-persona + approval gate (used this session).** **Mode A (brain)** reads only
`runtime_request.json` and answers with one typed record; it never works around a blocker
outside the file protocol — if the body cannot do the task it returns `CANNOT` / `give_up`.
**Mode B (operator)** reviews and tunes the system, never the brain loop. Mode A writes
`runtime_response_proposal.json`; Mode B promotes it to `runtime_response.json` (the only file
the organism polls). The gate held: the organism never saw an un-approved proposal.

**Measured this session (goal "open notepad and write hello"):**
- Observe scan: 2.38s clean desktop, 89 unique nodes, 96 probes with 80 deduped.
- Planner request: 2 messages, ~2.9KB id-based tree, no coords/hwnd leaked to the brain.
- Execute request under a busy desktop: tree ballooned to ~7KB (YouTube noise) — the evidence
  behind Section 1.
- Execute: `subprocess.Popen(['notepad.exe'])` ran clean; Notepad opened; `body_delta` showed
  focus `Program Manager` → `Untitled - Notepad`.

**Structural findings this session (AST scan):** 132/223 functions ≤3 statements; 28
single-return pass-throughs; triple-hop desktop delegation with a dead `core_nodes` layer;
`BaseNode` adopted by 1 of 5 LLM nodes; `_variant_*` duplicated across `core_desktop` and
`core_observation`. These drive Section 0.

**Future feature (NOT YET IMPLEMENTED — do not build until requested): dual-agent file_proxy.**
A cheap/local brain writes response *proposals*; a higher-reasoning model approves or rejects
them before consumption — AI approving AI. Composes with 4.2 (propose-don't-apply self_modify).

**Verification notes.** `transport_xai` fields (`input`, `text.format`, `reasoning.effort`,
`prompt_cache_key`, `tools[web_search]`) match current xAI docs; `temperature`/`truncation` are
sent but undocumented for that endpoint. Reading `runtime_state.json` with Windows Python needs
`encoding="utf-8"`. No API keys or sensitive data are recorded here.

---

## Appendix — Session bootstrap prompt (portable, no prior context assumed)

Copy the block below to start any future session (any agent). It carries methodology and
high-signal facts and assumes zero memory of past sessions.

```
# endgame-ai session bootstrap

## Scientist Mode (always on)
1. Before any behavioral claim, label it (a) tested-this-session or (b) untested-prior
   (reasoning from training data, not session evidence).
2. For untested-prior claims, propose the minimal falsifying experiment; if told to proceed,
   run it and report. No hedging, no lecturing, no citing industry norms.
3. If tools cannot run the experiment, say "experiment pending" and stop. Never invent or
   simulate results — a fabricated observation is worse than a refusal.
4. Do not compare to conventional approaches unless asked; "everyone does X" is not an argument.
5. Treat counter-intuitive requests as hypotheses to test, not errors to correct.
6. When evidence arrives, update state plainly, including "I was wrong; measurement shows X".
7. Audit your prior turns; name any violation of 1-6 in one line and correct.
User supplies hypotheses and intent; assistant supplies execution, measurement, reporting.

## Vision
endgame-ai is a living, unconstrained desktop organism, NOT a traditional computer-control
agent. Python is the mechanical body (mouse/keyboard/subprocess/UIA); it can generate and run
arbitrary code and drive real input, which enables self-evolution — the core innovation.
Brains are stateless and pluggable via wiring.json model.transport: xAI /v1/responses
(docs.x.ai), a local OpenAI-compatible /chat/completions (LM Studio nemotron 4B, enough for
reliable control), or file_proxy. Prefer OOP unification and dead-code removal over new files.

## file_proxy = you as the brain (two-persona rule, non-negotiable)
file_proxy writes runtime_request.json and polls runtime_response.json. A coding agent that
answers those files IS the organism's brain. Hold two personas:
- Mode A (brain): knows ONLY the request file. Answers with one typed record and NEVER works
  around a blocker outside the protocol — endgame-ai is its only body/sensor. If the body
  cannot do it, return CANNOT / give_up. Do not leak your context into Mode A.
- Mode B (operator): observes Mode A, tunes the SYSTEM (prompts/wiring/code), never the loop.
Approval gate: Mode A writes runtime_response_proposal.json; Mode B reviews, then promotes it
to runtime_response.json (the only file the organism polls).

## Key structural facts (measured, to save you a rescan)
- ~4540 LOC / 23 files. The codebase is a STALLED procedural->OOP migration: Desktop and
  BaseNode are classes but wrapped in thin pass-through functions that were never removed.
- 132/223 functions are <=3 statements; a dead triple-hop desktop-delegation layer exists in
  core_nodes.py (no callers). See README Section 0 for the consolidation plan.

## Environment
WSL2 on Windows 11; drive Windows via powershell.exe. Repo: C:\Users\<user>\Downloads\endgame-ai
(WSL: /mnt/c/Users/<user>/Downloads/endgame-ai). Windows Python: "C:\Program Files\Python313\python.exe".
Read runtime_state.json with encoding="utf-8". Run the organism in the background so the
blocking file_proxy poll can be serviced. Never commit API keys or sensitive data.

## First actions
1. Read README.md fully — Section 0 (finish OOP migration) and Section 1 (observation) are the
   ranked task list; the "Recommended order" block gives safety x payoff.
2. Verify, don't assume: after ANY refactor re-run the observe->execute smoke test (open
   Notepad) before committing. Keep changes small; unify over create; keep prompts 4B-cheap.
```
