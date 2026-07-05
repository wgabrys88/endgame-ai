# endgame-ai

A local desktop organism: Python is the body, LLM transports are the mind, and a fixed
topology of organs routes signals through observe → plan → act → verify → recover loops.

This README is the operator guide for the stabilized flat layout (July 2026). The codebase
was reduced, observation was rewritten, runtime data was flattened to the repo root, and
the system was proven end-to-end — including resume, tick control, and two transport modes
that let the organism talk back to its operators.

---

## What changed (stabilization milestone)

- **Flat repo, zero subfolders.** Every source file and runtime artifact lives at the root.
  Filename prefixes replace directory grouping: `core_*`, `node_*`, `transport_*`,
  `runtime_*`.
- **Observation simplified.** `core_observation.py` gathers the full UIA hover-cache scan,
  then runs one `filter_gather()` pass for the LLM. No fallback rescans in the brain.
- **Topology starts at observe.** Boot flow: scan desktop → planner sees
  `fresh_observation` → scheduler picks a step → rescan → execute.
- **Transports proven.** `transport_file_proxy` writes `runtime_request.json` for human
  inspection; `transport_xai` calls the xAI API when `XAI_API_KEY` is set.
- **Resume works.** Without `--reset`, the organism loads `runtime_state.json` and continues
  from `next_node`. `--max-ticks N` adds N ticks to the saved tick count.
- **Git allowlist.** Only essential source files are tracked; all `runtime_*` artifacts are
  ignored by default.

---

## Quick start

```powershell
cd endgame-ai
python core_organism.py --reset "Your goal here"
```

Common flags:

| Flag | Effect |
|------|--------|
| `--reset` | Delete runtime state/log, start fresh |
| `--max-ticks N` | Stop after N node completions (on resume: N *additional* ticks) |
| `--start-node node_planner` | Override entry node (default: `node_observe` from wiring) |
| `--max-brain-calls N` | Cap LLM calls per run |

Resume a paused run:

```powershell
python core_organism.py --max-ticks 3
```

Stop all organism processes:

```powershell
python -c "import core_stop_check; core_stop_check.request_stop('operator halt')"
```

---

## File layout (flat tree)

```
wiring.json                 single config: topology, transports, prompts, scan settings

core_organism.py            main loop, tick budget, resume, pause/step chokepoint
core_brain.py               LLM chokepoint: think(), transport dispatch, JSON extract
core_bus.py                 signal bus: emit(), state patches, failure streak
core_nodes.py               node loader, execute namespace, self-modify git apply
core_desktop.py             Windows UIA actuators (click, type, focus, scroll)
core_observation.py         gather → filter_gather → observe artifact
core_stop_check.py          cooperative shutdown via runtime_stop.txt

node_planner.py             decompose goal into verifiable steps
node_scheduler.py           pick plan step by index
node_observe.py             desktop sensor node (wraps core_observation)
node_execute.py             generate and run Python actuator code
node_frame_action.py        ROD framing pass before retry execute
node_verify.py              judge step.done_when against fresh_observation
node_reflect.py             route failures: retry / replan / escalate / give_up
node_self_modify.py         git-native firmware patches
node_satisfied.py           halt gate
node_error.py               mechanical error router

transport_file_proxy.py     write runtime_request.json, poll runtime_response.json
transport_xai.py            xAI API / grok CLI
transport_openai.py         OpenAI-compatible HTTP (e.g. LM Studio)
transport_opencode.py       opencode-cli subprocess
transport_browser_ai.py     documented stub
```

Runtime artifacts (gitignored, flat at root):

```
runtime_state.json          full organism state (plan, observation, last_action, tick)
runtime_control.json        run | pause | step mode
runtime_log.ndjson          one JSON event per line
runtime_request.json        file_proxy outbound LLM request (inspect this)
runtime_response.json       file_proxy inbound LLM response (you write this)
runtime_observation_<ms>.json   raw gather artifact (~MB scale)
runtime_<name>.pid          registered process id
runtime_stop.txt            cooperative kill signal
runtime_raw_<timestamp>.txt     brain raw request/response log
```

---

## How the organism works

### Circuit model

Each **node** is one organ on a bus. A node runs, returns exactly one **signal** (a pin
name), and one **state patch**. The Python body in `core_organism.py` looks up the signal
in `wiring.json` topology edges and dispatches the next node. LLM-backed nodes call
`core_brain.think()` with a typed JSON record (`record_type` + `data` + optional
`reasoning`).

There are no hidden fallbacks. Missing topology edges, missing transports, or absent
`fresh_observation` all fail hard with `RuntimeError`.

### Topology (default)

```
node_observe ──initial_screen──► node_planner ──step_ready──► node_scheduler
     ▲                                    │
     │                                    └──plan_complete──► node_satisfied ──► halt
     │
     └──step_ready (loop)──────────────────────────────────────────────┘
          (scheduler advances step, then observe rescan before execute)

node_observe ──screen_ready──► node_execute ──verify──► node_verify
                                    ├──frame──► node_frame_action ──► execute
                                    ├──reflect──► node_reflect
                                    └──self_modify──► node_self_modify

node_verify ──step_confirmed──► node_scheduler (next step)
            ──step_denied────► node_reflect

node_reflect ──retry──► node_observe
             ──replan──► node_planner
             ──escalate──► node_self_modify
             ──give_up──► node_satisfied
```

Cycle always boots at `node_observe` (`cycle_start` in wiring). First pass emits
`initial_screen` (no plan yet) → planner. Later passes emit `screen_ready` → execute.

### Observation pipeline

1. **gather** — sinusoidal hover-cache UIA scan harvests elements, properties, patterns.
2. **filter_gather** — dedupe, build `desktop_tree`, `action_index`, `desktop_tree_text`.
3. **observe** — write `runtime_observation_<ms>.json`, patch state with
   `fresh_observation`.

The LLM sees `desktop_tree_text` (semantic, id-based tree). Actuators use `action_index`
coordinates and `click_node(id)` helpers from the execute namespace.

### Execute namespace

`node_execute` runs LLM-generated Python with helpers: `pyautogui`/`pag` facade,
`click_node`, `type_text`, `focus_window`, `open_url`, stdlib modules, etc. Code must set
`result` to a JSON-serializable value. Conclusions: `EXECUTE`, `CANNOT`, `FRAME`,
`SELF_MODIFY`.

---

## Transport modes

Set `model.transport` in `wiring.json` to the module name (matches filename without path).

### transport_file_proxy (inspect / manual loop)

1. Organism writes `runtime_request.json` with `messages` and payload.
2. Operator reads `messages[1].content` — contains goal, state, `fresh_observation`.
3. Operator writes `runtime_response.json`:

```json
{
  "content": "{\"record_type\":\"plan\",\"data\":{\"next_signal\":\"step_ready\",\"intent\":[...]},\"reasoning\":\"...\"}",
  "reasoning": ""
}
```

4. Organism polls until `content` is non-empty, then continues.

This mode is how we proved the pipeline: observe → planner request lands on disk for
human review before the model answers.

### transport_xai (live API)

Requires `XAI_API_KEY` in the environment. Uses structured outputs per `record_type`.
Reasoning effort is set per organ in wiring (`plan` medium, `execution` low,
`verification` none, etc.).

Switch transports by editing `wiring.json`:

```json
"transport": "transport_file_proxy"
```

or

```json
"transport": "transport_xai"
```

---

## Tick control and resume

Each completed node increments `tick` in `runtime_state.json`. Use ticks to bound cost
and inspect intermediate artifacts.

Examples from stabilization testing:

```powershell
# Fresh run, 5 ticks: observe → planner → scheduler → observe → execute
python core_organism.py --reset --max-ticks 5 "Open Notepad and write an essay..."

# Resume 2 more ticks: verify → scheduler (or reflect, etc.)
python core_organism.py --max-ticks 2
```

On resume, `--max-ticks 2` means *two additional* node executions from the saved tick
count, not a total of 2.

Inspect progress:

```powershell
Get-Content runtime_log.ndjson -Tail 10
```

Key state fields: `tick`, `current_step`, `last_signal`, `next_node`, `plan`, `last_action`,
`last_verification`, `fresh_observation` (inside state after observe).

---

## Wiring.json

Single source of truth:

- `topology.nodes` / `topology.edges` — organ graph (IDs match `node_*.py` filenames)
- `prompts.node_*` — system prompts per LLM organ
- `model.transport` / `model.transport_config` — brain adapter selection
- `observe_config.hover_cache` — scan pattern, step_px, filter limits
- `paths` — runtime artifact filenames (all flat `runtime_*`)

Prompt and topology keys use the same prefixed names as modules (`node_planner`, not
`planner`).

---

## Self-modify (firmware evolution)

`node_self_modify` receives runtime evidence, git context, and workspace manifest. It
returns a `git_evolution_patch` record with `file_writes`, `wiring_patches`, and optional
validation commands. `core_nodes` validates, applies, commits, and optionally pushes.

Blocked paths: anything under `runtime_*`, `.git`, `__pycache__`. Core files can be
rewritten but not deleted.

---

## Requirements

- Windows 10+ (UIA desktop automation)
- Python 3.11+ with `comtypes` (observation/actuation)
- For xAI transport: `XAI_API_KEY` environment variable
- For file_proxy: no API key; operator supplies `runtime_response.json`

---

## Operator checklist

1. Set goal and transport in `wiring.json` (or pass goal on CLI).
2. `--reset` for a clean run, or omit for resume.
3. Watch `runtime_log.ndjson` and `runtime_state.json`.
4. For file_proxy: inspect `runtime_request.json`, write `runtime_response.json`.
5. Use `--max-ticks` to stage work across sessions.
6. Read `runtime_observation_<ms>.json` when debugging scan quality.

The system now talks to its operators through concrete files and a predictable topology.
That is the stabilization milestone: less code, flat layout, observable loop, resumable
runs, and a body that acts on what it actually sees.

---

# Appendix A — file_proxy behavioral analysis log

This appendix is a running, evidence-based log of the organism's behavior when driven
through the `transport_file_proxy` brain, with a coding agent acting as the "brain."
It is built incrementally across sessions. It contains **no API keys or sensitive data**.

## A.0 Two-persona + approval-gate protocol

The operator runs the loop under a strict split:

- **Mode A (brain persona).** Reads only `runtime_request.json`. Its entire world is that
  file's contents (goal, state, `desktop_tree_text`). It answers by producing one typed
  record. It never works around a blocker by reaching outside the file protocol; if the
  endgame-ai body cannot do the task, Mode A honestly returns `CANNOT` / `give_up`.
  endgame-ai is its only body and only sensor.
- **Mode B (operator/observer).** Watches how the system frames requests and consumes
  responses. Tunes the *system* (prompts, wiring, code, scan speed), never the brain loop.

**Approval gate (proposal → review → consume):**

1. Mode A writes its answer to `runtime_response_proposal.json` (endgame-ai does NOT poll this).
2. Mode B reviews the proposal, records findings here.
3. On approval, Mode B promotes it to `runtime_response.json`, which endgame-ai consumes.

This mirrors Claude-Code-style human approval. It also demonstrates a future capability:

> **Future feature (NOT YET IMPLEMENTED — do not build until requested):** dual-agent
> file_proxy. A cheap/local brain (e.g. LM Studio nemotron) writes response *proposals*;
> a higher-reasoning model approves or rejects them before they are consumed. AI approves
> AI. Implement only on explicit request.

## A.1 Experiment: goal = "open notepad and write hello"

Transport switched to `transport_file_proxy`; file_proxy `timeout` raised to 86400s so the
manual review cycle does not error the brain loop. Runs use `--max-ticks` to stage the loop.

Findings are appended below as they are observed.

### A.1.1 Run 1 — boot + planner (ticks 0→2) — TESTED

Command: `core_organism.py --reset --max-ticks 2 "open notepad and write hello"`
Transport: `transport_file_proxy`. Run in background so the blocking poll can be serviced.

Timeline (from `runtime_log.ndjson`):
- tick 0: `node_observe` starts.
- tick 1 (+2.44s): observe completes → `initial_screen` → `node_planner`.
- planner blocks writing `runtime_request.json`, polling for `runtime_response.json`.
- operator promotes reviewed proposal → response.
- tick 2: planner completes → `step_ready` → `node_scheduler`, then `max_ticks`, clean exit.

**Scan performance (observe):** `elapsed_s = 2.382`. 96 probe points, 80 skipped by hit-dedup
(`saturated_hits`/already-indexed), 16 harvested, 230 subtree nodes seen, **89 unique nodes**,
80 with text. Verdict: the sinusoidal hover-cache scan at `step_px=96` is fast (~2.4s) on a
1920-wide desktop and the dedup is doing real work (83% of probes skipped). No speed problem
observed at this resolution.

**Request quality (what Mode A sees):** `runtime_request.json` = 2 messages.
- system = planner prompt (clear, computer-use-appropriate, enumerates record contract + rules).
- user = compact JSON: goal, `state_brief`, and `fresh_observation` with a **2857-char**
  `desktop_tree_text`. The tree is semantic and id-based (`(e_...) Role Name [action]`),
  exactly what a computer-use agent needs. No raw coordinates/hwnd leak into the brain view
  (they live in the body-side `action_index`). This is a strong request shape.

**Observations / notes for tuning:**
- The tree included a Task Manager window with ~40 telemetry `Edit`/`Button` nodes (CPU/mem/net).
  This is noise for a "open notepad" goal and inflates the tree. Not harmful here, but a busier
  desktop could crowd out signal. Candidate future tuning: rank/trim by relevance to goal, or
  cap per-window action nodes. (Do not change yet — measuring first.)
- `focused_title` was "Program Manager" (the desktop shell) — correct baseline; Notepad absent.
- Persona wall held: the plan was derived only from the request contents.

**Risk flagged (untested):** step 2's `done_when` needs Notepad's typed document text to appear
in `desktop_tree_text`. Whether the UIA scan surfaces Notepad edit-area content is unverified;
the verify node will decide. Watching this in the next runs.

### A.1.2 Run 2 — resume: scheduler → observe → execute (ticks 2→5) — TESTED

Command: `core_organism.py --max-ticks 3` (resume; 3 additional ticks from tick 2).

Timeline:
- tick 3: `node_scheduler` (mechanical, no brain call) → `step_ready` → `node_observe`.
- tick 4: observe rescan (**+6.25s**) → `screen_ready` → `node_execute` (blocks on file proxy).
- operator services the execute request.
- tick 5: execute runs the code → `verify` → `node_verify`, then `max_ticks`.

**RESULT: real action succeeded.** Mode A (execute persona) returned `conclusion=EXECUTE`
with `subprocess.Popen(['notepad.exe'])`. The body ran it with no exception. Ground truth:
`Get-Process notepad` shows `Untitled - Notepad` running; organism `body_delta` reports
`focused_before="Program Manager"` → `focused_after="Untitled - Notepad"`, `focused_changed=true`.
The organism opened Notepad on the real desktop through the file-proxy brain loop. Feature proven:
observe→plan→schedule→observe→execute all driven by an external coding agent as the brain.

**Scan speed regression under load:** run 1 observe = 2.38s; run 2 observe = **6.25s**. Between
runs, a Chrome/YouTube window came to the foreground. The scan cost scales with on-screen UI
density because more probe points hit rich subtrees (fewer dedup skips). Not a defect, but a
measured sensitivity: **scan latency is a function of desktop complexity, not a constant.**

**Request bloat under load (important):** the execute request's `desktop_tree_text` grew from
~2.9KB to **~7KB**, dominated by a full YouTube page dump — dozens of `Hyperlink`/`TabItem`
nodes (video titles, sidebar tabs) completely irrelevant to "open notepad". The `action_index`
was likewise flooded with YouTube links. This is the noise problem flagged in A.1.1, now clearly
reproduced. For a computer-use agent this is a real quality risk: signal (the target app) can be
buried under an unrelated foreground app, and token cost rises. **Candidate tuning (measure before
changing):**
- rank action nodes by relevance to the current step/goal, keep top-N;
- lower per-window action-node cap for non-focused windows;
- optionally drop deep browser content subtrees when the step targets a different app.

**Prompt suitability (computer-use):** the execute system prompt is well-suited — it states the
body truth (full Python, not just helpers), lists helpers + allowed stdlib, and the `result_rule`
correctly prevents the brain from self-declaring success (verify owns truth from observation).
Mode A correctly reached for `subprocess` (OS launch) instead of clicking a non-existent Notepad
node — evidence the "helpers are conveniences, not limits" framing steers away from agent theater.

**Approval-gate behavior:** proposal→review→promote worked cleanly both times. The organism only
ever consumed the promoted `runtime_response.json`; `runtime_response_proposal.json` was invisible
to it (not the polled path). This validates the dual-file design and the future dual-agent idea.

**Inspection footnote:** reading `runtime_state.json` with Windows Python without
`encoding='utf-8'` raises `UnicodeDecodeError` (cp1252 default). Organism code itself always uses
`encoding="utf-8"`, so this only affects ad-hoc operator inspection commands — use utf-8 explicitly.

---

# Appendix B — Multi-expert architecture review

Read-only analysis. Claims are marked **[verified]** (checked against source/runtime this
session) or **[reasoned]** (inference from the code, not executed). No code was changed.

## B.1 Systems Architect — body/brain boundary

**The boundary is mostly clean and genuinely well-drawn.** `wiring.json` owns topology,
prompts, transport selection, scan params, and reasoning effort; the Python body owns
mechanism (bus, node loader, desktop actuators, observation). Nodes emit exactly one
`(signal, patch)`; the loop routes only the signal via `topology.edges`. This is a real
declarative circuit, not a config veneer.

**Where it leaks [verified]:**

1. **Reasoning-effort policy is duplicated in two places.** `core_brain.think()` hardcodes a
   `default_effort_map` (plan=medium, execution=low, …) *and* `wiring.json` has
   `model.organs.*.reasoning_effort` with the same values. The Python map is a body-side copy
   of a brain-side policy. If someone tunes wiring, the code default silently shadows it when
   the organ key is absent. This is a body/brain leak: policy living in mechanism.

2. **`global.reasoning_enabled: true` is effectively dead for most transports [verified].**
   `_effective_reasoning_config` reads `reasoning.enabled` from the *transport* cfg first;
   file_proxy/openai/opencode all set `enabled=false`, so the global `true` never takes effect
   there. Only `transport_xai` has `enabled=true`. The global flag is a misleading no-op.

3. **`schedule` and `satisfied` record schemas exist in `core_brain._RECORD_DATA_SCHEMAS`
   [verified]** but `node_scheduler` and `node_satisfied` are mechanical (they never call the
   brain). Prompts for them also exist in wiring. Dead contract surface — harmless but it
   implies an LLM path that does not run.

**Duplicated / dead code [verified]:**

- **UIA loader duplicated.** `core_desktop._load_uia_module()` and
  `core_observation.load_uia()` are near-identical, and **both call `comtypes.CoInitialize()`
  at import time**. Two modules initializing COM and building the UIA typelib is redundant and
  a candidate for a single shared module (e.g. `core_uia.py`). This is the single strongest
  "unify, don't duplicate" target in the codebase.
- **`_variant_*` helpers duplicated.** `_variant_str` exists in both files; `core_observation`
  additionally has `_variant_int/rect/bool/runtime_id`. All variant coercion belongs in one
  place. (Counts this session: 2 refs in core_desktop, 23 in core_observation.)
- **`transport_grok_cli` config has no module [verified].** wiring lists it under
  `transport_config`, but there is no `transport_grok_cli.py`; grok CLI actually lives as
  `mode="cli"` inside `transport_xai.py`. Aspirational/dead config; selecting it fails hard.
- **`transport_browser_ai.py` is a documented fail-hard stub [verified].** Legitimate as a
  placeholder, but it is dead until implemented.

**OOP note (per project convention):** nodes are the natural class hierarchy, but only the
LLM nodes use `BaseNode`. `node_execute`, `node_verify`, `node_reflect`, `node_frame_action`,
`node_self_modify` each re-implement the same shape (build payload → `brain.think()` →
check record_type → map signal → build patch) as free functions. That is the second big
unification target: a richer `BaseNode` (or a couple of subclasses) could absorb the
payload/verify/patch boilerplate the five LLM nodes repeat.

## B.2 LLM Integration — reasoning loop, prompt assembly, KV-cache

**Two-pass loop [verified].** `think()` supports `single_pass`, `native`, and `two_pass`.
`two_pass` calls the transport twice: pass 1 harvests reasoning (via `<think>` tags or a
reasoning field), then injects it back as `REASONING_FEEDBACK` for pass 2 which commits JSON.
For the current live transport (xai) `pattern=native` (single call, provider-native
reasoning). file_proxy/openai are `two_pass` but `enabled=false`, so they run single_pass.
The machinery is sound; the risk is cost — `two_pass` doubles calls, and for a local 4B model
the injected reasoning text is often low-value, so two_pass there mostly buys latency.

**Prompt assembly [verified].** `_messages()` builds `[system, user]`. System = optional
stable-prefix + `DYNAMIC NODE PROMPT:` + node prompt. User = one JSON blob (goal, state_brief,
fresh_observation). This is clean and computer-use-appropriate: the observation is a compact,
id-based semantic tree; body-only data (coords/hwnd) never reaches the brain. Confirmed in
Appendix A: requests are well-shaped.

**KV-cache friendliness — mixed [verified/reasoned].** The design *intends* cache reuse:
`StablePrefix` renders the whole checked-out source as a stable leading block so providers can
cache it, and `think()` sets `prompt_cache_key` (conv id) for xai. **But `stable_prefix` is
disabled** (`enabled=false, include_in_request=false`), so today no large static prefix is
sent. More importantly, the *dynamic* portion (fresh_observation) is injected **inside the
system message region conceptually but as the user turn**, and it changes every tick — that is
correct. The genuine cache hazard [reasoned]: the system prompt begins with a fixed
`DYNAMIC NODE PROMPT:` marker but the node prompt *varies per organ*, so cross-organ cache
reuse is limited to the stable prefix (currently off). Net: cache-friendliness is architected
but effectively dormant. Turning the stable prefix on would help large-context providers and
hurt a small local model (context bloat) — a per-transport decision, not global.

## B.3 Graph Engine — topology trace

**[verified] via BFS over `wiring.topology`:**
- All 10 nodes reachable from `cycle_start=node_observe`. No unreachable nodes.
- No dangling edge targets (every non-`halt` destination is a declared node).
- Every node has an `error` edge **except** `node_satisfied` and `node_error` — correct by
  design (satisfied only `halt`s; error is the terminal router with `planner`/`reflect`/`halt`).
- The loop has proper cycles: reflect→observe (retry), reflect→planner (replan),
  reflect→frame_action→execute, verify→scheduler→observe→execute.

**Dead ends: none. Missing error paths: none structurally.**

**What happens when self_modify fails repeatedly [verified — this is the main graph risk]:**
`node_self_modify` returns `modified` and hands a `git_evolution_patch` to the loop.
`core_organism` applies it; on exception it hot-swaps to known-good and **re-raises**
(`core_organism.py:212`). The outer handler routes the exception to `node_error`, which — when
a `current_step` exists — emits `reflect`. `node_reflect` can `escalate` again to
`node_self_modify` on mechanical markers. **There is no circuit breaker on this cycle.**
`node_reflect` tracks a `failure_streak` count but only uses `count >= 2` to upgrade
retry/replan → `frame`; it **never forces `give_up`** on a high streak. So a persistently
failing self-modify can loop escalate → self_modify → error → reflect → escalate…, bounded
only by `--max-ticks` / `max_brain_calls`, not by any internal safety valve. On a local 4B
model producing weak patches, this is the most likely runaway.

**Duplicate edges: none.** Signals are unique per node.

## B.4 Top 5 architectural weaknesses

1. **No self-modify / failure circuit breaker [verified].** `failure_streak` is computed but
   never terminates a loop. escalate↔self_modify↔error↔reflect can spin until tick budget
   exhausts. A streak threshold that forces `give_up` (or blocks re-escalation) is missing.
2. **COM/UIA duplicated across `core_desktop` and `core_observation` [verified].** Two loaders,
   two `CoInitialize()`, duplicated `_variant_*`. Unify into one UIA module.
3. **Observation request bloat under busy desktops [verified in Appendix A].** Tree grew
   2.9KB→7KB, flooded by an unrelated YouTube window. No goal-relevance ranking or per-window
   cap for non-focused windows. Directly degrades small-model performance and cost.
4. **Policy duplicated between code and wiring [verified].** reasoning-effort map hardcoded in
   `core_brain` shadows `model.organs`; `global.reasoning_enabled` is a dead flag for most
   transports. Config that looks authoritative but isn't.
5. **LLM-node boilerplate not unified [verified].** Five nodes repeat the same
   payload→think→validate→patch structure as free functions instead of `BaseNode` subclasses,
   against the project's stated OOP/unification preference.

## B.5 Top 5 things done right

1. **True single-signal bus + declarative topology [verified].** Nodes are chips, wiring is the
   circuit. Routing logic is data, not branching code. This is the core strength.
2. **Fail-hard, no hidden fallbacks [verified].** Missing transport, missing edge, missing
   fresh_observation all raise. Behavior is legible; failures are loud, not silently patched.
3. **Body/brain observation firewall [verified].** The brain sees a semantic id-based tree;
   coordinates/hwnds stay body-side in `action_index`. Proven in Appendix A requests.
4. **Self-evolution with real guardrails [verified].** `_evolution_target` blocks
   runtime_/.git/__pycache__, enforces evolvable suffixes, forbids deleting core files,
   validates Python (`compile`) and JSON before *and* after write, snapshots + rolls back,
   and requires `read_files` grounding. For an "unconstrained" organism this is a
   surprisingly disciplined mutation boundary.
5. **Transport pluggability [verified].** One `call(messages, cfg)` contract; swapping brains
   (local nemotron ↔ xai ↔ file_proxy ↔ coding-agent) is a single wiring edit. The file_proxy
   experiment in Appendix A is the payoff.

## B.6 If I could rewrite ONE component

**The observation filter (`core_observation.filter_gather`) — or rather, split it into a
`BaseObserver` OOP surface with a relevance-ranking stage.** Reasons: (a) it is the single
biggest lever on small-model success — the request quality/bloat findings in Appendix A all
originate here; (b) it currently emits *everything actionable* with only crude ranking
(focus/name/offscreen), so an unrelated foreground app dominates the tree; (c) it duplicates
UIA/variant plumbing with `core_desktop`. A rewrite would: unify the UIA layer, add a
goal/step-aware relevance scorer, cap non-focused-window nodes, and expose it as a small class
hierarchy so alternative observers (e.g. accessibility-only, or OCR-assisted) can be swapped
via wiring — matching the transport pattern. This compounds value: every downstream node gets
cheaper and sharper input.

## B.7 Realistic ceiling for a 4B local model running this system

**[reasoned, with one live datapoint].** The 4B nemotron (OpenAI-compatible transport) can
plausibly drive the *mechanical* organs and simple, single-app steps reliably: launch an app,
type text, click a clearly-labelled node — the kind of step this session executed correctly
(a coding agent stood in as brain, but the record shapes are trivial for a 4B). The ceiling:

- **Planning depth:** fine for 2–4 step linear goals; unreliable for goals needing branching,
  recovery reasoning, or long horizons.
- **Observation grounding:** degrades sharply as the tree grows (the 7KB YouTube-flooded tree
  would likely cause a 4B to click the wrong node). Ceiling is set by observation quality
  (B.6), not the model alone.
- **Self-modify:** effectively out of reach. Producing a correct full-file `git_evolution_patch`
  that compiles and preserves the bus contract is a strong-model task; a 4B here is the main
  driver of the B.4#1 runaway loop. Recommend gating self_modify behind a higher-reasoning
  transport (which the future dual-agent idea in Appendix A enables).
- **Verification:** `verification` runs at `reasoning_effort=none` by design; a 4B can do
  boolean done_when checks against a compact tree, but will over-confirm on ambiguous trees.

Net ceiling: a 4B is a solid *actuator/verifier* brain for well-scoped desktop tasks with a
clean observation, and a poor *planner/self-modifier*. The architecture already supports
splitting these across transports per organ — that is the way to raise the ceiling without a
bigger single model.

## B.8 Declarative rule system: diminishing returns or compounding value?

**Compounding — but two specific rules are already in diminishing-returns territory.**
The declarative core (single-signal bus + topology + per-organ prompts/effort) compounds:
adding an organ or rerouting behavior is a wiring edit, transports swap freely, and the whole
system stayed legible enough that a full multi-expert audit fits in one file. That is the
compounding-value signature.

The diminishing-returns edges [verified]: the reasoning-effort map duplicated in code vs
wiring, the dead `global.reasoning_enabled`, dead `schedule`/`satisfied` schemas+prompts, and
aspirational transport configs (`grok_cli`, `browser_ai`) add declarative surface that must be
read and reconciled but changes no behavior. These are where "more config" stopped paying.
Trimming them (and unifying the code duplication in B.4#2 and B.4#5) would push the whole
system back onto the compounding curve. The rule *system* is healthy; a few *rules* are
barnacles.
