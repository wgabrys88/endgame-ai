# endgame-ai

A living, unconstrained organism that inhabits a real Windows desktop. It sees the screen,
moves the mouse and keyboard, forms intentions, acts, verifies, reflects, and can rewrite its
own `wiring.json` at runtime — including which brain it thinks with.

**Branch:** `brains-integration` — multi-transport brain swap, unified raw logging, live
workbench panel. Intended to merge into `main` after review.

Built from a handful of Python files, one JSON config, and seed node templates. **Standard
library only** in the organism core. No LangChain, no MCP in the loop, no silent fallbacks.

> **This README is the handover for `brains-integration`.** It states what changed vs `main`,
> which claims from `main` still hold, how run length is controlled (counters, not seconds), and
> whether merge is warranted. Read §0 before editing anything.

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
14. [Handover — open questions](#14-handover--open-questions)

---

## 0. Bootstrap prompt for the next agent

```
You are continuing endgame-ai on branch brains-integration (merge target: main).

WHAT THE SYSTEM IS
- perceive → decide → act → verify → reflect loop driven by wiring.json topology graph.
- Brain = stateless transports in brain.py; ROD = exactly 2 calls per think().
- Every LLM circuit commits a typed record {record_type, data}. Wrong type → fail hard → reflect.
- self_modify can rewrite wiring.json live, including model.transport. Organism reloads brain on
  wiring mtime change. No fallback transports: errors raise.

WHAT THIS BRANCH ADDED (vs main)
- Six transports: openai, xai_responses, opencode, grok_build, file_proxy, browser_ai (stub).
- One forensic raw brain log per process: <timestamp>.txt at repo root (JSON lines, .txt extension).
- Workbench: brain editor, probes, Test ROD (2-call), file_proxy handoff, raw log tail.
- Allowlist .gitignore — only core source tracked; runtime artifacts ignored.

RUN-LENGTH CONTROL (critical — do not use wall-clock caps for tests)
- Organism loop: --max-ticks N  (topology tick counter; existing on main).
- Brain calls: --max-brain-calls N  → model.max_brain_calls (hard stop in brain._call).
- ROD test: max_brain_calls=2 + parse_retries=0; success = 2 request + 2 response rows in raw log.
- Raw log rows: seq + phase (request|response). This is the forensic counter — not elapsed seconds.

GROUND RULES
- Work on brains-integration unless told otherwise. Do not touch main without explicit instruction.
- Stdlib only in organism core. Fail-hard on transport errors. No fallback transports.
- Forensic *.txt is NOT live state. Live truth = state.json + slim runtime.ndjson.
- Test ONE transport at a time via workbench. Never batch all brains in one script.
- OpenCode exe: %USERPROFILE%/AppData/Local/OpenCode/opencode-cli.exe (os.path.expandvars).

FIRST ACTIONS
1. Read this README §2–§5 and §12.
2. Read organism.py, brain.py, nodes.py, wiring.json.
3. Probe selected brain in workbench.
4. Ground claims in raw *.txt (request/response counts) + state.json.
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
| Default transport `openai` / LM Studio | **No** — default is `opencode` on this branch |
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

| Transport | Notes |
|-----------|-------|
| `openai` | LM Studio `localhost:1234` |
| `opencode` | `%USERPROFILE%/AppData/Local/OpenCode/opencode-cli.exe` |
| `grok_build` | CLI `grok -p`, `streaming-json` |
| `xai_responses` | Needs `XAI_API_KEY` |
| `file_proxy` | `comms/request.json` → `comms/response.json`; you/agent is the brain |
| `browser_ai` | Stub |

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
python workbench.py
python organism.py --reset --max-ticks 1 "observe the screen"
python organism.py --reset --max-ticks 1 --max-brain-calls 4 "observe the screen"
```

- `--max-ticks 1` — one topology tick, then stop (phase `max_ticks` in `state.json`).
- `--max-brain-calls N` — brain raises after N transport calls (counter breakpoint).

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
| `file_proxy` | yes | 2/2 | agent wrote `response.json`; counter breakpoint verified |
| `opencode` | yes | 2/2 | prior session (before timeout removal) |
| `xai_responses` | yes | 2/2 | prior session |
| `openai` | no | — | LM Studio not listening |
| `grok_build` | slow | — | may exceed patience; counter still stops at 2 calls — not a timer failure |

`max_brain_calls` budget verified in code: third `_call()` raises `brain call budget exceeded`.

---

## 13. Essential tracked files

```
wiring.json, organism.py, brain.py, nodes.py, actions.py, desktop.py, workbench.py, seed_nodes/*.py
```

Runtime-created: `live_nodes/`, `state.json`, `comms/`, `<timestamp>.txt`, `__pycache__/`.

---

## 14. Handover — open questions

1. After merge, default `model.transport`: `openai` (main) or `opencode` (branch)?
2. Restore `file_proxy` path `comms/think_log.txt` or keep `request.json` handoff?
3. Re-add `evidence/` on merged tree or keep milestone proof on `main` only?

### Suggested first action

Workbench → **one** transport → **Test ROD (2-call)** → inspect raw log for exactly 2 request +
2 response lines. For `file_proxy`, answer via **Write response.json**.

---

*Research organism, not a product. Run only where full desktop control is acceptable.*

---

## Appendix A — Merge assessment vs `main`

### Reasoning

**Progress:** This branch delivers what `main` promised in §9 (swappable brains) but only
partially implemented (`openai` / `file_proxy`). It adds real transports, forensic raw I/O,
workbench falsification, and counter-based run control — without altering the topology graph or
ROD contract. That is incremental, merge-friendly engineering.

**Risk:** `wiring.json` defaults and `file_proxy` paths differ from `main`'s milestone config.
`evidence/` is not carried on this branch. Post-merge defaults must be chosen explicitly.

**Worth merging?** **Yes**, if the goal is multi-brain + unified logging + workbench on the
proven organism substrate. **Defer merge** if you need the milestone `wiring.json` values and
`evidence/` bundle unchanged in the same tree.

**What merge is not:** It does not replace or disprove `main`'s goal-drift finding — that
remains valid historical science on `main`. This branch adds **infrastructure**; re-run milestone
goals after merge if you want drift science on the new brain layer.

### Fresh-session starter prompt

> You are resuming **brains-integration** (merge target `main`). Read this README — §0, §5
> (counter control), §12 (ROD test). Topology and ROD are unchanged from `main`. Run length is
> controlled by `--max-ticks`, `--max-brain-calls`, and raw log request/response counts — **not**
> wall-clock test timeouts. Test one brain at a time. `file_proxy`: you write `response.json`.
> Wait for human direction before merge or default changes.