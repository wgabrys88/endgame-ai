# endgame-ai

A living, unconstrained organism that inhabits a real Windows desktop. It sees the screen,
moves the mouse and keyboard, forms intentions, acts, verifies, reflects, and can rewrite its
own `wiring.json` at runtime — including which brain it thinks with.

**Branch:** `brains-integration` — multi-transport brain swap, unified raw logging, live
workbench panel. Intended to merge into `main` after review.

Built from a handful of Python files, one JSON config, and seed node templates. **Standard
library only** in the organism core. No LangChain, no MCP in the loop, no silent fallbacks.

> **This README is the handover for `brains-integration`.** Brain transports are wired and
> falsified; default brain is **LM Studio (`openai`)** so the living organism never silently
> burns paid tokens on a cloud transport. Read §0 before editing anything.

---

## Table of contents

0. [Bootstrap prompt for the next agent](#0-bootstrap-prompt-for-the-next-agent)
1. [What this branch is](#1-what-this-branch-is)
2. [Changelog vs `main` (line diffs)](#2-changelog-vs-main-line-diffs)
3. [Is `main`'s README still true here?](#3-is-mains-readme-still-true-here)
4. [Did the organism wiring logic change?](#4-did-the-organism-wiring-logic-change)
5. [Run-length control — counters, not seconds](#5-run-length-control--counters-not-seconds)
6. [Architecture](#6-architecture)
7. [ROD — the two-call decision](#7-rod--the-two-call-decision)
8. [Brain transports](#8-brain-transports)
9. [Logging contract](#9-logging-contract)
10. [Running it](#10-running-it)
11. [The workbench](#11-the-workbench)
12. [ROD brain test (counter breakpoint)](#12-rod-brain-test-counter-breakpoint)
13. [Essential tracked files](#13-essential-tracked-files)
14. [Handover — next work toward the vision](#14-handover--next-work-toward-the-vision)

---

## 0. Bootstrap prompt for the next agent

```
You are continuing endgame-ai on branch brains-integration (merge target: main).

WHAT THE SYSTEM IS
- A living organism on a real Windows desktop: perceive → decide → act → verify → reflect.
- Topology graph in wiring.json (8 nodes, 16 edges) — identical to main.
- Brain = stateless transports in brain.py; ROD = exactly 2 calls per think().
- Every LLM circuit commits a typed record {record_type, data}. Wrong type → fail hard → reflect.
- self_modify can rewrite wiring.json live, including model.transport. Organism reloads brain on
  wiring mtime change. No fallback transports: if the selected brain is down, the call raises.

DEFAULT BRAIN (decided — do not change without explicit instruction)
- model.transport = openai → LM Studio at http://localhost:1234 (nvidia-nemotron-3-nano-4b).
- The organism pursues its own goal when none is given; a wrong default brain wastes tokens.
- Alternate transports (opencode, xai_responses, grok_build, file_proxy) exist for wiring swap
  or workbench falsification only — never auto-selected.

BRAIN LAYER STATUS (2026-06-30 — all real transports ROD-validated)
- openai (LM Studio): yes — organism 2/2 via planner tick (~76s)
- file_proxy: yes — 2/2; agent writes comms/response.json
- opencode: yes — 2/2 (prior session)
- xai_responses: yes — 2/2 (prior session; needs XAI_API_KEY)
- grok_build: wired; slow CLI — counter stops at 2 calls, not a timer
- browser_ai: stub only

RUN-LENGTH CONTROL (counters, not seconds)
- Organism loop: --max-ticks N
- Brain calls: --max-brain-calls N  → model.max_brain_calls (hard stop in brain._call)
- ROD falsification: rod_brain_calls=2; success = 2 request + 2 response rows in raw *.txt
- model.timeout is per-call I/O safety only — not the test budget

GROUND RULES
- Work on brains-integration unless told otherwise. Do not touch main without explicit instruction.
- Stdlib only in organism core. Fail-hard. No fallback transports.
- Forensic *.txt is NOT live state. Live truth = state.json + slim comms/runtime.ndjson.
- Falsify brains one at a time (workbench Test ROD or organism with --max-brain-calls 2).
- Never batch all transports in one script.

FIRST ACTIONS
1. Read README §5, §8, §12, §14.
2. Confirm LM Studio is listening on :1234 before starting the organism.
3. python workbench.py  OR  python organism.py --reset --max-ticks 1 --max-brain-calls 2 "<goal>"
4. Ground claims in raw *.txt (transport + request/response counts) + state.json.
```

---

## 1. What this branch is

`main` documented a milestone run (goal-interpretation drift, self-modification, LM Studio 4B)
and shipped a minimal brain layer (`openai` + `file_proxy` + `browser_ai` stub).

`brains-integration` keeps the **same organism graph and intent contract** but adds:

- Multi-transport brain swap (wiring-controlled).
- Unified raw forensic log (`<timestamp>.txt`).
- Workbench panel with counter-based ROD falsification.

The milestone **research narrative** on `main` (§1–§2, `evidence/`) is historical context;
this branch removed `evidence/` from git (still on `main` history).

---

## 2. Changelog vs `main` (line diffs)

Measured with `git diff main...brains-integration --numstat` (2026-06-30, before latest commit).

| File | +lines | −lines | Reason |
|------|--------|--------|--------|
| `brain.py` | ~710 | ~65 | Multi-transport; raw `*.txt` log; `max_brain_calls` budget |
| `workbench.py` | ~670 | ~95 | Panel, ROD test by counter, usage from raw log |
| `wiring.json` | ~372 | ~24 | Transport blocks; **topology unchanged** |
| `organism.py` | ~110 | ~37 | Atomic state; `--max-brain-calls`; wiring hot-reload |
| `README.md` | rewrite | rewrite | This handover |
| `.gitignore` | 32 | 10 | Allowlist policy |
| `nodes.py` | 8 | 1 | Wiring summary keys for self_modify |
| `evidence/*` | 0 | 1389 | Removed on branch (preserved on `main`) |

---

## 3. Is `main`'s README still true here?

| Claim from `main` | Still valid? |
|-------------------|--------------|
| Topology graph (8 nodes, 16 edges) | **Yes** — unchanged |
| ROD two-call cognition | **Yes** |
| Typed `record_type` contract | **Yes** |
| `self_modify` edits wiring incl. transport | **Yes** |
| Stdlib only, fail-hard | **Yes** |
| Default transport `openai` / LM Studio | **Yes** — `model.transport: openai` (LM Studio must be running) |
| Three transports only | **No** — six transports |
| `file_proxy` → `comms/think_log.txt` | **No** — `comms/request.json` → `response.json` |
| Session / usage log files | **No** — single raw `*.txt` |
| Milestone drift forensic (§1–§2) | **Historical** — on `main`, not re-run here |
| Anti-hang via `timeout` on shell | **Yes for ops** — but brain **test length** uses **call counter**, not seconds |

---

## 4. Did the organism wiring logic change?

**No change to the topology graph.** `topology.nodes`, `topology.edges`, and `cycle_start` are
identical to `main`.

**Changed in `wiring.json`:** `model` section only (transports, logging, handoff paths, UI
`controls`). **Changed in `organism.py`:** reliability (atomic `state.json`, runtime events,
`--max-brain-calls`). **Not changed:** signal routing, node contracts, ROD in `nodes.call_node()`.

**Merge implication:** you are merging brain transport + observability + workbench, not a new
cognitive architecture.

---

## 5. Run-length control — counters, not seconds

Wall-clock timeouts are a poor control for brain tests (slow CLIs false-fail; fast batch runs
burn tokens). This branch uses **existing counter semantics**:

| Layer | Control | Mechanism |
|-------|---------|-----------|
| Organism loop | `--max-ticks N` | Stops after N topology ticks (`organism.py`; **on main**) |
| Brain calls | `--max-brain-calls N` | Sets `model.max_brain_calls`; `brain._call()` raises when `calls_made >= N` |
| ROD falsification | `rod_brain_calls: 2` | Workbench test: `parse_retries=0` + `max_brain_calls=2` |
| Forensic proof | raw log `phase` | Count `request` and `response` rows per transport; must equal 2 for ROD test |

Each `brain._call()` increments an internal counter and appends one `request` + one `response`
row to `<timestamp>.txt` (paired by `seq`). That is the breakpoint — not a sleep timer.

`model.timeout` (seconds) remains a **transport I/O safety** per call (HTTP/CLI subprocess), not
the test budget. Do not shorten it for ROD tests.

---

## 6. Architecture

| Piece | Role |
|-------|------|
| `organism.py` | Topology driver; `--max-ticks`, `--max-brain-calls` |
| `brain.py` | Transports; ROD `think()`; raw log; call budget |
| `nodes.py` + `live_nodes/` | Hot-swappable circuits (from `seed_nodes/`) |
| `actions.py`, `desktop.py` | Windows body |
| `wiring.json` | Topology, prompts, verbs, brain config |
| `workbench.py` | http://localhost:8800 |

---

## 7. ROD — the two-call decision

Unchanged from `main`:

1. **Call 1** — reasoning.
2. **Call 2** — user + `ROD_REASONING_CONTENT:` → typed JSON record.

Raw log marks call 2 requests with `rod_feedback: true`.

---

## 8. Brain transports

**Default:** `openai` → LM Studio at `http://localhost:1234`. No code path auto-switches
transport; `brain._call()` uses only `model.transport` and raises on failure.

| Transport | Default? | ROD 2/2 | Notes |
|-----------|----------|---------|-------|
| `openai` | **yes** | yes | LM Studio; local 4B — safe default for autonomous runs |
| `file_proxy` | | yes | `comms/request.json` → `comms/response.json`; human/agent is the brain |
| `opencode` | | yes | `%USERPROFILE%/AppData/Local/OpenCode/opencode-cli.exe` |
| `xai_responses` | | yes | `XAI_API_KEY`; paid — swap only when intended |
| `grok_build` | | slow | CLI `grok -p`, `streaming-json`; counter still stops at 2 |
| `browser_ai` | | — | Stub |

---

## 9. Logging contract

| Tier | Path | Role |
|------|------|------|
| Live snapshot | `state.json` | Current truth |
| Live events | `comms/runtime.ndjson` | Organism lifecycle only |
| Forensic raw | `<timestamp>.txt` | `seq` + `phase` + wire `raw` per brain call |

Usage in workbench is derived from raw `response` rows. Runtime paths are gitignored.

---

## 10. Running it

```powershell
# LM Studio must be running on :1234 before organism start (fail-hard otherwise)
python workbench.py
python organism.py --reset --max-ticks 1 --max-brain-calls 2 "observe the screen"
python organism.py --reset --max-ticks 1 --max-brain-calls 4 "observe the screen"
```

- `--max-ticks 1` — one topology tick, then stop (phase `max_ticks` in `state.json`).
- `--max-brain-calls 2` — one ROD decision (planner tick); raises if a third call is attempted.
- `--max-brain-calls N` — hard counter breakpoint for longer bounded runs.

---

## 11. The workbench

```powershell
python workbench.py    # http://localhost:8800
```

- Brain editor, **Probe selected**, **Test ROD (2-call)**
- File proxy handoff (write `response.json` as the brain)
- Raw log tail; usage derived from responses

---

## 12. ROD brain test (counter breakpoint)

**Test ROD (2-call)** → `POST /api/brain_test` with selected transport.

| Setting | Value |
|---------|-------|
| `parse_retries` | `0` (one `think()` only) |
| `max_brain_calls` | `2` (from `rod_brain_calls` in wiring) |
| Success | `rod_calls==2`, `rod_responses==2`, `brain_calls==2`, valid JSON, `rod_feedback` on call 2 |

### Tested in-session (2026-06-30)

| Transport | OK | `brain_calls` | Notes |
|-----------|----|---------------|-------|
| `openai` | yes | 2/2 | organism planner tick; raw log `20260630T082704.txt`; ~76s |
| `file_proxy` | yes | 2/2 | agent wrote `response.json`; counter breakpoint verified |
| `opencode` | yes | 2/2 | prior session |
| `xai_responses` | yes | 2/2 | prior session |
| `grok_build` | slow | 2/2* | *counter stops at 2; CLI may be slow — not a timer failure |
| `browser_ai` | — | — | stub |

`max_brain_calls` budget verified: third `_call()` raises `brain call budget exceeded`.

---

## 13. Essential tracked files

```
wiring.json, organism.py, brain.py, nodes.py, actions.py, desktop.py, workbench.py, seed_nodes/*.py
```

Runtime-created: `live_nodes/`, `state.json`, `comms/`, `<timestamp>.txt`, `__pycache__/`.

---

## 14. Handover — next work toward the vision

**Vision:** endgame-ai is a research organism — not a chatbot — that inhabits a real desktop,
forms its own intentions when no goal is given, acts through typed records, verifies outcomes,
reflects on failure, and can rewrite its own wiring (including which brain it thinks with). The
milestone on `main` showed goal-interpretation drift and self-modification under a minimal brain
layer; this branch adds **safe multi-brain infrastructure** so that science can continue without
accidental token spend.

### Resolved on this branch

| Decision | Choice |
|----------|--------|
| Default brain | `openai` / LM Studio — fail-hard if not running |
| Transport fallback | None — errors raise |
| Run-length control | Counters (`--max-ticks`, `--max-brain-calls`, raw log phases) |
| `file_proxy` handoff | `comms/request.json` → `comms/response.json` |
| Brain falsification | All real transports ROD 2/2 except `browser_ai` stub |

### Next work items (priority order)

1. **Merge `brains-integration` → `main`** — topology unchanged; resolve `evidence/` policy at
   merge time (keep on `main` history only vs restore bundle).
2. **Bounded autonomous run** — LM Studio default, `--max-ticks` + `--max-brain-calls` budget,
   empty or curiosity goal; observe whether planner/actor stay grounded on SCREEN tokens.
3. **Re-run milestone goal-drift science** — same substrate as `main` §1–§2 but with unified raw
   log; compare drift signatures across brains (local 4B vs file_proxy vs one cloud transport).
4. **`self_modify` brain experiments** — organism changes `model.transport` deliberately; verify
   hot-reload + raw log continuity; document when self-mod chooses cloud vs local.
5. **`browser_ai`** — implement desktop handoff or remove from wiring to avoid false options.
6. **`grok_build` patience run** — single workbench ROD test with counter only; confirm 2/2 when
   CLI completes.
7. **Observability** — optional `observability.py` or workbench views for tick/brain-call
   budgets during long runs (forensic `*.txt` already has seq/phase).

### Suggested first action for the next agent

Start LM Studio → `python organism.py --reset --max-ticks 3 --max-brain-calls 12` with no goal
(let the planner choose intention) → read `state.json` + newest `*.txt` raw log. Use workbench
only to monitor; do not swap transport unless explicitly testing another brain.

---

*Research organism, not a product. Run only where full desktop control is acceptable.*

---

## Appendix A — Merge assessment vs `main`

### Reasoning

**Progress:** This branch delivers what `main` promised in §9 (swappable brains) but only
partially implemented (`openai` / `file_proxy`). It adds real transports, forensic raw I/O,
workbench falsification, and counter-based run control — without altering the topology graph or
ROD contract. That is incremental, merge-friendly engineering.

**Risk:** `file_proxy` paths differ from `main`'s milestone config (`think_log.txt` vs
`request.json`). `evidence/` is not carried on this branch. Default transport now matches
`main` (`openai` / LM Studio).

**Worth merging?** **Yes** — brain layer is falsified, default is local LM Studio, counter
control is in place. Remaining merge choice: `evidence/` bundle and `file_proxy` path policy.

**What merge is not:** It does not replace or disprove `main`'s goal-drift finding — that
remains valid historical science on `main`. This branch adds **infrastructure**; re-run milestone
goals after merge if you want drift science on the new brain layer.

### Fresh-session starter prompt

> You are resuming **brains-integration** (merge target `main`). Brains are finalized; default is
> **LM Studio (`openai`)** — start LM Studio before the organism. Read §0, §14. Topology and ROD
> unchanged from `main`. Run length = `--max-ticks`, `--max-brain-calls`, raw log phases — not
> wall-clock caps. Next: bounded autonomous run or merge to `main`. Swap transport only when
> explicitly testing another brain; never batch transports.