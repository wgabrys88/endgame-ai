# endgame-ai

A local desktop organism. Python is the mechanical body (mouse, keyboard, subprocess, UIA
observation), LLM transports are the interchangeable mind, and `wiring.json` is the circuit
diagram: a fixed topology of organs routes one signal per node through
observe → plan → act → verify → recover. The organism can generate and run arbitrary code and
drive real input, which is what makes self-evolution possible — and what makes discipline
about observation quality, prompt shape, and failure bounds non-optional.

This document is not a feature tour. It is a **correction plan**: a ranked list of the things
in this system that do **not** compound with that vision, each stated as *what it is*, *why to
do it*, and *why not / the cost*. The goal is a system that works, works cheaply, and can be
driven by a small local model. The centerpiece is observation: nothing else compounds until
the organism sees cheaply and relevantly.

Evidence base: every file was read; the file_proxy loop was run end-to-end this session
(observe → plan → schedule → observe → execute), which physically opened Notepad on a real
desktop. xAI transport fields were verified against live xAI docs (2025). Claims below are
grounded in that, not assumed.

---

## How it runs (minimum operator knowledge)

```powershell
python core_organism.py --reset --max-ticks 5 "Open Notepad and write hello"   # fresh, staged
python core_organism.py --max-ticks 3                                           # resume +3 ticks
python -c "import core_stop_check as s; s.request_stop('halt')"                 # cooperative stop
```

- One completed node = one `tick`. On resume, `--max-ticks N` means N *additional* ticks.
- Transport is chosen by `wiring.json` `model.transport`. Fail-hard: no silent fallback.
- Boot starts at `node_observe` (full UIA scan) → planner → scheduler → observe → execute →
  verify → (reflect / self_modify) → satisfied → halt.
- Runtime artifacts are flat `runtime_*` files, all gitignored. `runtime_request.json` /
  `runtime_response.json` are the file_proxy brain channel.

**Transports are NOT unified, and should not be.** `transport_xai` posts to
`/v1/responses` with `input` + `text.format` + `reasoning.effort` (`none|low|medium|high`) and
uses `prompt_cache_key` for caching. `transport_openai` posts to `/v1/chat/completions` with
`messages` + `response_format`. `transport_file_proxy` writes/polls files. Each transport owns
its own request shape by design; `core_brain.think()` is the only unification point (one
`call(messages, cfg)` contract). Treat per-transport request code as intentionally specific.

---

## Reading this plan

Each item: **2 sentences of what**, then **Why** (2 sentences), then **Why not** (2 sentences).
Priority order within each section is highest-leverage first. Nothing here has been changed in
code yet — this is the plan, not a changelog.

---

## 1. Observation — the cost and correctness bottleneck (do this first)

### 1.1 Add goal/step-relevance ranking to `filter_gather`
Today the filter emits every actionable node with only crude ranking (focus, has-name,
on-screen), so an unrelated foreground app dominates the tree. This session a YouTube window
flooded the request from ~2.9KB to ~7KB with dozens of irrelevant video links.
**Why:** request size and node ambiguity are the single biggest driver of both cost and wrong
clicks; a small model degrades sharply as the tree grows. Ranking nodes by relevance to the
current step and keeping a top-N slice directly makes every downstream organ cheaper and
sharper.
**Why not:** relevance scoring can hide a node the plan actually needs, causing a false
"CANNOT"; it must be conservative and always keep the focused window fully, with the cap
applied to non-focused windows only.

### 1.2 Cap action nodes per non-focused window
The scan currently lets any window contribute up to `max_action_nodes` (240), so a busy
browser can consume the whole budget. A per-window cap for non-focused windows would reserve
the budget for the window the step is about.
**Why:** the focused window is almost always where the next action happens, and background
windows are usually noise; capping them preserves signal without a semantic model.
**Why not:** some goals span windows (drag from A to B), so the cap must be a soft reserve,
not a hard exclusion, or cross-window steps will silently lose their target.

### 1.3 Make scan latency predictable, not desktop-dependent
Observe took 2.38s on a clean desktop and 6.25s once a rich Chrome page was foreground; cost
scales with UI density because more probes hit deep subtrees. A budget (max probe time or
adaptive `step_px`) would bound worst-case tick latency.
**Why:** unbounded scan time makes tick cost and file_proxy timeouts unpredictable, which
hurts both automation and the future cheap-brain loop that pays per call.
**Why not:** a hard time budget can truncate a legitimately dense screen and drop the target
node, so it needs an early-stop that prioritizes the focused window before cutting.

### 1.4 Unify the UIA layer (`core_uia.py`) — remove duplicate COM init
`core_desktop.py` and `core_observation.py` each define their own UIA loader and their own
`_variant_*` coercers, and **each calls `comtypes.CoInitialize()` at import**. One shared UIA
module would hold the loader, constants, and variant helpers.
**Why:** duplicate COM initialization and duplicated coercion logic are exactly the "creation
over unification" the project rejects; a single module removes ~two dozen redundant refs and
one class of drift bugs.
**Why not:** merging touches the two hottest files and risks a regression in the scan that this
session proved works, so it must be a pure move-and-import refactor with the scan re-run before
commit.

---

## 2. Code quality & bloat — unify, delete, don't create

### 2.1 Fold the five LLM nodes into `BaseNode` subclasses
`node_execute`, `node_verify`, `node_reflect`, `node_frame_action`, and `node_self_modify` each
re-implement the same shape (build payload → `brain.think()` → check `record_type` → map signal
→ build patch) as free functions. Only planner uses `BaseNode` today.
**Why:** the repeated boilerplate is the project's stated anti-pattern, and a richer base class
would make the contract (one record, one signal, one patch) enforced in one place.
**Why not:** execute and self_modify have real per-node logic (code exec sandbox, git patch
application) that does not fit a thin base, so over-abstracting would trade duplication for a
leaky superclass — subclass only the shared skeleton, keep node-specific bodies explicit.

### 2.2 Delete dead / aspirational surface
`transport_grok_cli` has config in `wiring.json` but **no module file** (grok CLI lives inside
`transport_xai` as `mode="cli"`); `transport_browser_ai.py` is a fail-hard stub. Both read as
real options but cannot run.
**Why:** dead config forces every reader (human or self-modify) to reconcile options that do
nothing, adding declarative surface with zero behavior — the definition of non-compounding.
**Why not:** the browser stub may be a deliberate roadmap marker, so delete `grok_cli` config
outright but keep `browser_ai` only if it is documented in one line as "not implemented."

### 2.3 Remove dead LLM contract for mechanical nodes
`core_brain._RECORD_DATA_SCHEMAS` defines `schedule` and `satisfied` record schemas, and
`wiring.json` has prompts for both, yet `node_scheduler` and `node_satisfied` are mechanical and
never call the brain. This implies an LLM path that does not exist.
**Why:** removing the unused schemas and prompts shrinks the contract to what actually executes,
so the declarative layer stops describing phantom behavior.
**Why not:** a future variant might make scheduling LLM-driven, so if kept, they must be marked
"reserved, mechanical today" rather than left looking active.

---

## 3. Prompts & LLM integration — cheap, cache-friendly, unambiguous

### 3.1 Move reasoning-effort policy fully into wiring (kill the code copy)
`core_brain.think()` hardcodes a `default_effort_map` (plan=medium, execution=low, …) that
duplicates `model.organs.*.reasoning_effort` in `wiring.json`. When an organ key is absent, the
code default silently shadows the config.
**Why:** effort is a tuning knob that belongs in the mutable brain, not the mechanical body;
one source of truth prevents a wiring edit from being silently ignored.
**Why not:** a wiring omission would then send no effort at all, so the code should fall back to
a single named default (e.g. "low") rather than a full shadow map.

### 3.2 Retire the dead `global.reasoning_enabled` flag
`model.global.reasoning_enabled` is `true`, but `_effective_reasoning_config` reads
`reasoning.enabled` from each transport's own config first, where file_proxy/openai/opencode set
`false`. The global flag therefore changes nothing for those transports.
**Why:** a config value that looks authoritative but is a no-op is a trap for both operators and
the self-modify organ; removing it makes reasoning state legible per transport.
**Why not:** if any tooling reads the global flag as a display hint, it should be replaced by a
derived read-only summary rather than deleted blind.

### 3.3 Decide the stable-prefix / cache posture per transport
`StablePrefix` renders the whole checked-out source as a fixed leading block so providers can
cache it, but it is disabled (`enabled=false`). xAI docs confirm caching is automatic on shared
starting messages and that `prompt_cache_key` (already set by `transport_xai`) pins routing.
**Why:** for a paid large-context provider the stable prefix plus a stable key is real money
saved on repeated ticks; leaving it off forgoes automatic cache hits the API offers for free.
**Why not:** for a 4B local model the same prefix is pure context bloat that pushes out the
observation, so this must be a per-transport switch (on for xai, off for local), never global.

### 3.4 Keep prompts computer-use-shaped (they already are — protect this)
The planner and execute prompts state the body truth (full Python, helpers are conveniences),
enumerate the record contract, and forbid self-declared success (verify owns truth from
observation). This session the execute organ correctly chose `subprocess` over clicking a
non-existent node.
**Why:** these prompts steer away from agent theater and match the semantic id-based tree the
brain receives, which is exactly what a small model needs to stay grounded.
**Why not:** every added rule spends tokens a 4B can ill afford, so prompt edits should trim or
sharpen, not accumulate — measure before adding a sentence.

---

## 4. Topology & failure control

### 4.1 Add a failure circuit breaker (highest topology risk)
`node_reflect` computes a `failure_streak` count but only uses `count >= 2` to upgrade
retry/replan → `frame`; it **never forces `give_up`**. A failing self-modify can loop
escalate → self_modify → error → reflect → escalate, bounded only by `--max-ticks`.
**Why:** an unconstrained organism that can rewrite itself must have an internal stop, or a weak
patch loop will burn brain calls and possibly thrash the repository until the tick budget ends.
**Why not:** a breaker that trips too early kills legitimate multi-attempt recovery, so it
should force `give_up` (or block re-escalation) only after a bounded streak on the *same*
failure signature, which the code already computes.

### 4.2 Gate `self_modify` behind a high-reasoning transport
Producing a correct full-file `git_evolution_patch` that compiles and preserves the bus contract
is a strong-model task; a 4B here is the main driver of the 4.1 loop. The topology already
routes escalate → self_modify, but nothing checks the brain's capability.
**Why:** matching the hardest organ to the strongest brain (and keeping cheap organs on the
local model) is how the architecture raises its ceiling without one big model.
**Why not:** a hard gate removes self-evolution when only a local model is available, so it
should degrade to "propose patch, do not apply" rather than refuse, feeding the future
AI-approves-AI review loop (Appendix note below).

### 4.3 Keep fail-hard routing (protect this)
Missing transport, missing topology edge, and missing `fresh_observation` all raise; the loop
routes exceptions to `node_error`, which reflects or replans. Reachability was verified: all 10
nodes reachable, no dangling edges, error edges on every node except the terminal `satisfied`
and `error`.
**Why:** loud, legible failure is worth more than silent recovery in a system that touches a
real desktop, and the graph is provably well-formed today.
**Why not:** fail-hard plus the missing breaker (4.1) is what enables the runaway loop, so the
breaker is the required complement — do not soften fail-hard to compensate.

---

## 5. 4B local model — the cheap-brain target

### 5.1 Use the 4B as actuator/verifier, not planner/self-modifier
The local nemotron reliably drives mechanical organs and simple single-app steps (launch, type,
click a clearly labelled node) — the exact shapes proven this session. It is unreliable for
branching plans, long horizons, and full-file self-modification.
**Why:** splitting organs across transports (cheap model for execute/verify, stronger for
plan/self_modify) is already supported by wiring and is the realistic path to "works cheap."
**Why not:** running two brains adds latency and orchestration, so for simple linear goals a
single 4B across all organs is fine — escalate to a split only when a goal needs planning depth.

### 5.2 Success for the 4B is gated by observation, not parameters
On a clean tree the 4B can pick the right node; on the 7KB flooded tree it will likely click the
wrong one. The ceiling moves with Section 1, not with model size.
**Why:** this reframes "the model is too small" as "the input is too noisy," which is a fixable
engineering problem rather than a hardware one.
**Why not:** observation fixes cannot make a 4B plan a ten-step branching task, so do not expect
Section 1 to remove the need for a stronger planner on hard goals.

---

## 6. System readiness — what works, what blocks cheap operation

### 6.1 Proven working (do not regress)
End-to-end file_proxy control works: this session the loop observed, planned, scheduled, and
executed real code that opened Notepad, with the organism's own `body_delta` confirming the
focus change. Resume, tick control, cooperative stop, and the self-evolution guardrails
(path allowlist, compile+JSON validation before and after write, snapshot rollback) all hold.
**Why:** these are the load-bearing behaviors; every item above assumes they keep working, so
any refactor must re-run the observe→execute path before commit.
**Why not:** "proven" here means one goal on one desktop, not a test suite, so treat it as a
smoke test and add regression coverage before large refactors (see 6.2).

### 6.2 Missing automated tests (readiness gap)
There is no test harness; correctness is verified by running the organism and reading logs.
The topology, the bus contract, and `filter_gather` output shape are all testable without a
live desktop.
**Why:** the refactors in Sections 1–4 are risky precisely because nothing catches a regression,
and topology/contract tests are cheap and desktop-free.
**Why not:** UIA scan and real actuation are hard to test without Windows in CI, so aim for
contract/topology/filter unit tests now and leave desktop actuation as manual smoke tests.

### 6.3 Blockers to cheap, unattended operation
Cheap unattended runs are blocked by three things in order: noisy/oversized observation (Sec 1),
the missing failure breaker (4.1), and unbounded scan latency (1.3). Until these land, cost and
runaway risk are both unbounded.
**Why:** "works cheap" is a function of tokens-per-tick and ticks-per-goal, and all three
blockers inflate one or both.
**Why not:** none of these block *attended* experimentation today, so continue gathering data
via file_proxy while the fixes are staged rather than pausing use.

---

## Appendix — file_proxy behavioral log & future dual-agent brain

**Two-persona + approval gate (used this session).** The operator ran the loop under a strict
split: **Mode A (brain)** reads only `runtime_request.json` and answers by producing one typed
record; it never works around a blocker outside the file protocol — if the body cannot do the
task it returns `CANNOT` / `give_up`. **Mode B (operator)** reviews and tunes the system, never
the brain loop. Mode A wrote each answer to `runtime_response_proposal.json`; Mode B reviewed it,
then promoted it to `runtime_response.json` (the only file the organism polls). The gate worked:
the organism never saw un-approved proposals.

**Measured this session (file_proxy, goal "open notepad and write hello"):**
- Observe scan: 2.38s clean desktop, 89 unique nodes, 96 probes with 80 deduped.
- Planner request: 2 messages, ~2.9KB semantic id-based tree, no coords/hwnd leaked to brain.
- Execute request under a busy desktop: tree ballooned to ~7KB (YouTube noise) — the core
  evidence behind Section 1.
- Execute result: `subprocess.Popen(['notepad.exe'])` ran clean; Notepad opened; `body_delta`
  showed focus `Program Manager` → `Untitled - Notepad`.

**Future feature (NOT YET IMPLEMENTED — do not build until requested): dual-agent file_proxy.**
A cheap/local brain writes response *proposals*; a higher-reasoning model approves or rejects
them before they are consumed — AI approving AI, mirroring human approval in coding agents. This
composes directly with item 4.2 (propose-don't-apply self_modify) and the approval gate above.

**Verification notes.** xAI request fields used by `transport_xai` (`input`, `text.format`,
`reasoning.effort`, `prompt_cache_key`, `tools[web_search]`) match current xAI docs;
`temperature`/`truncation` are sent but not documented for that endpoint. Reading
`runtime_state.json` with Windows Python requires `encoding="utf-8"` for ad-hoc inspection; the
organism itself always uses utf-8. No API keys or sensitive data are recorded in this document.

---

## Appendix — Session bootstrap prompt (portable, no prior context assumed)

Copy the block below to start any future session (with any agent). It carries the methodology
and high-signal facts; it assumes zero memory of past sessions.

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
7. Audit your prior turns; name any violation of 1–6 in one line and correct.
User supplies hypotheses and intent; assistant supplies execution, measurement, reporting.
The experiment decides.

## Vision
endgame-ai is a living, unconstrained desktop organism, NOT a traditional computer-control
agent. Python is the mechanical body (mouse/keyboard/subprocess/UIA); it can generate and run
arbitrary code and drive real input, which enables self-evolution — the core innovation.
Brains are stateless and pluggable via wiring.json model.transport: xAI /v1/responses
(docs.x.ai), a local OpenAI-compatible /chat/completions (LM Studio nemotron 4B, enough for
reliable control), or file_proxy.

## file_proxy = you as the brain (two-persona rule, non-negotiable)
file_proxy writes runtime_request.json and polls runtime_response.json. A coding agent that
runs continuously and answers those files becomes the organism's brain. Hold two personas:
- Mode A (brain): knows ONLY the request file contents. It answers with one typed record and
  NEVER works around a blocker outside the protocol — endgame-ai is its only body/sensor. If
  the body cannot do it, Mode A returns CANNOT / give_up. Do not leak your context into Mode A.
- Mode B (operator): observes Mode A, tunes the SYSTEM (prompts/wiring/code), never the loop.
Approval gate: Mode A writes runtime_response_proposal.json; Mode B reviews, then promotes it
to runtime_response.json (the only file the organism polls).

## Environment
WSL2 on Windows 11; drive Windows via powershell.exe. Repo: C:\Users\<user>\Downloads\endgame-ai
(WSL: /mnt/c/Users/<user>/Downloads/endgame-ai). Windows Python: "C:\Program Files\Python313\python.exe".
Read runtime_state.json with encoding="utf-8". Run the organism in the background so the
blocking file_proxy poll can be serviced. Never commit API keys or sensitive data.

## First actions
1. Recursive listing of the repo (no exclusions except .git contents), max depth.
2. Read every file end to end (.py .json .md .txt configs).
3. Read this README's correction plan (Sections 1–6) before proposing changes; it is the
   grounded task list. Verify, don't assume — re-run the observe→execute smoke test after any
   refactor. Keep changes small, unify over create, keep prompts token-cheap for the 4B.
```
