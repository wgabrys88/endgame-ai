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
