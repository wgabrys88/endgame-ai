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

**Evidence base (measured across sessions).** Every file was read. The file_proxy loop was run
end-to-end and physically opened Notepad. An AST scan classified all functions. xAI transport
fields were verified against live xAI docs. Numbers below are measured, not estimated:

- Total: **4528 LOC across 22 `.py` files** (`core_observation.py` 1066, `core_nodes.py` 762,
  `core_brain.py` 701, `core_desktop.py` 287, `core_organism.py` 273).
- **Section 0 (the OOP migration) is DONE** — see below for per-item measured deltas.
- The remaining plan (Sections 1–5) is observation quality, dead declarative surface, prompt
  policy, failure control, and 4B readiness. None are pure line-count work.

The OOP consolidation's **line-count payoff was modest and is now measured, not projected**:
`core_observation.py` went 1088→1066, total 4540→4528. Earlier drafts projected ~230–310 LOC of
dedup recovery; that estimate was wrong. Method bodies move into classes rather than being
deleted, and class scaffolding offsets removed parameter plumbing. The real payoff was
**structural** (state held once, one source of truth per concern, one enforced node contract),
not fewer lines.

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

## Section 0 — Finish the OOP migration — DONE (committed, smoke-tested)

The stalled procedural→OOP migration is finished. `Desktop`, `BaseNode`, `UiaVariant`, and
`UiaScanner` are real classes with no leftover pass-through scaffolding. Each item was verified
by re-running the observe→execute smoke test before commit.

- **0.1/0.2 — Desktop delegation collapsed** (`d293234`). Removed the dead `core_nodes`
  ctx-ignoring desktop wrappers and the `core_desktop` per-method module delegators; callers now
  use `get_desktop().<method>()`. The `get_desktop()` singleton accessor stays.
- **0.3 — `BaseNode` generalized and adopted** (`5a51b3a`). Added `build_payload(ctx)`,
  `evidence(ctx)`, and `request_config` hooks plus a shared `think()` helper; planner, verify,
  reflect, frame_action, and execute are now subclasses (execute overrides `run()` because its
  signal depends on runtime exec results). One record/one signal/one patch is enforced in one
  place. Verified with a full brain loop (Notepad opened).
- **0.4a — `UiaVariant`** (`0e8b1ed`). The scattered `_variant_*`/`_serialize_value` helpers are
  now `UiaVariant` staticmethods, reused by `core_desktop` (retiring the "make core_uia.py"
  idea — no new file).
- **0.4b — `UiaScanner`** (`05c185b`). The harvest pipeline (`_element_to_node`,
  `_harvest_subtree`, `_probe`, `_cache_request`, `_hit_cache_request`, `gather`) is folded into
  one class that holds `automation`/`scan_cfg`/`property_ids`/`pattern_ids`/`cache_request`/
  `hit_cache` as `self.*` instead of threading them through every call. `gather()` is now a thin
  delegate to `UiaScanner(...).scan()`. Smoke-tested: 393 raw / 124 filtered nodes, full
  `observe()` and the boot→observe→planner loop both intact.

**Measured deltas:** `core_observation.py` 1088→1066; total 4540→4528. The win is structural
(one source of truth per concern), not line count.

**Deliberately kept:** the per-element `try/except` in the harvest path. On a live desktop some
elements are always inaccessible/transient, so a single bad element is skipped, not fatal — this
is resilience, not a silent-degrade fallback. The scan still fails hard if `automation` or screen
metrics are unavailable. The genuine silent-degrade fallbacks to remove live in Section 3.

---

## Section 1 — Observation: cost and correctness bottleneck (functional priority)

### 1.1–1.3 DONE — focus machinery removed, whole-screen model unified

Direction changed after diagnosis. The original 1.1/1.2/1.3 (relevance ranking,
per-focused-window caps, focused-first early-stop) were all built on a focused-window concept
that was itself the bug. Evidence (tested): a freshly launched Notepad was MISSING from the next
verify tick's tree because `filter_gather` ranked `keyboard_focus` first, gated survival on
`require_interactive or keyboard_focus`, tagged `[FOCUSED]`, and computed `focused_window_id` —
so a window that was not foreground at the scan instant was discriminated against. Focus was also
load-bearing in two more places: `get_focused_title()` did COM round-trips (GetForegroundWindow →
ElementFromHandle → property) multiple times per tick, and `click_node` force-`SetForegroundWindow`
before every click, stealing foreground and mutating desktop state mid-plan.

Resolution: the organism now has NO focus concept. One flat whole-screen scan; every window and
element is present in one tree, ranked purely by content and on-screen position. Removed:
`keyboard_focus` field + `PID_HasKeyboardFocus` reads, the focus-first rank, the focus survival
gate, `[FOCUSED]`, `focused_window_id`, `focused_title` plumbing across observe/bus/brain/
self_modify, `Desktop.get_focused_title`/`_get_active_window`/`_get_window_title`/`focus_window`/
`clear_focus_cache`/`_focused_title_cache`, `_focus_node_window` + focus-before-click, the
`focus_window`/`get_focused_title` capability-runtime helpers, and execute's `body_delta` focus
capture. Prompts rewritten to the focus-free whole-screen contract; `focus_window` dropped from
execute's helper list.

Measured this session (quiet desktop): tree 7535→7525 bytes, action nodes 124→124, scan
4.471→4.388s (fewer COM round-trips), focused_title removed from output. LOC 4367→4192 (−175).
Correctness proof (tested): launch Notepad → observe → Notepad present in tree (previously
absent); full observe→plan→execute→verify loop runs with the new prompts. Remaining observation
variance is pure scan/harvest timing on a just-created window — a bounded/adaptive-scan lever,
tracked below, not a focus issue.

### 1.4 (open) Bound scan latency / harvest freshness
Observe took ~2.4s clean vs ~6.3s with a dense Chrome page; a just-launched window can miss a
single scan's harvest window. Add a probe-time budget or adaptive `step_px`, or a short settle/
re-probe for newly appeared top-level windows.
**Why:** unbounded scan time makes tick cost and file_proxy timeouts unpredictable, and a missed
harvest causes a false verify denial.
**Why not:** a hard budget can truncate a dense screen; early-stop must not drop windows.

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

Section 0 (OOP migration) is **done**. Remaining:

1. **1.1–1.3** observation relevance/caps/latency — the functional centerpiece; behavior change,
   measure tree-bytes/nodes/scan-seconds before and after each.
2. **2.1 / 2.2** dead declarative surface — low risk, quick clarity.
3. **3.1 / 3.2** reasoning-effort policy dedup + dead `global.reasoning_enabled` — the real
   silent-degrade fallbacks deferred out of Section 0.
4. **4.1** failure circuit breaker; **4.2** self_modify gating.
5. **5.3** minimal contract/topology/filter test harness (desktop-free).

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
