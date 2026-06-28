# Endgame-AI

> A brain-agnostic desktop operator. It observes a real Windows screen, decides what
> to do with any LLM "brain", and executes real mouse/keyboard actions — with no API
> keys, no frameworks, and no pip dependencies (Python standard library only).

This document is the single source of truth for the project's **vision**, **current
architecture**, **what works / what is broken**, and **what must be done to make it
real**. The appendix at the end is a self-contained **handover prompt** so any new
session — including a different AI — can resume the work by reading this file alone.

---

## 1. Vision

Endgame-AI aims to be a system that can operate an entire desktop the way a human does,
driven by a swappable AI brain:

```
Traditional agent:  human -> configures agent -> agent calls an API -> limited to that API
Endgame-AI:         human -> posts a goal -> system operates the WHOLE desktop -> any app, any AI
```

The brain is a **socket**. It can be:
- a local model in LM Studio (OpenAI-compatible HTTP),
- an external agent / human via a **file handoff** (`file_proxy`),
- or a browser-hosted AI (e.g. grok.com) that the system talks to **with its own hands**
  by typing into the browser and reading the reply off the screen (`browser_ai`).

The endgame behavior we are chasing: give the system a goal like *"use Opera to open
Grok and have a conversation with it"*; if opening Opera fails, it tries another way;
if it realizes Opera is not installed, it reasons *"I must install it"* and does so.
A system that **self-evolves** and **evolves its environment** — adapting like a person.

---

## 2. How it works

### 2.1 Graph engine

`engine.py` is an HTTP server and a graph walker. The topology, prompts, rules, and
limits live in `prompts/wiring.json` (the "brain policy"). Each node has a `type`
mapped to a bare script in `nodes/*.py`, executed in a namespace of helpers from
`runtime.py`. Nodes set `signals` and a `patch`; the engine routes the next node by
matching a signal to a wiring edge.

Default port is **9077** for slot 1 (`http_port_base + (slot-1)`). The relay
configuration (`wiring_relay.json`, slot 2) uses 9078.

Key HTTP routes (see `engine.py`):
- `GET  /health` — liveness + wiring summary + run status
- `GET  /state` — current run state (step, plan, memory, history, last_error)
- `GET  /wiring`, `POST /wiring` — read / hot-reload the wiring (validated)
- `POST /run` — autonomous loop
- `POST /step` — advance **exactly one node** (synchronous); the basis for stepped,
  observable operation
- `POST /pause`, `/resume`, `/stop`
- `GET  /events` — SSE event stream
- `GET  /` — the `wiring-editor.html` workbench (graph editor + live inspector)

### 2.2 The ROD two-call contract (Reason-Observe-Decide)

Every LLM decision is made with **two calls** to the same context (`call_node` in
`runtime.py`):

1. **Pass A (reason):** send `(system, user)`. The model reasons freely. The engine
   keeps `reasoning = reasoning_content or content`.
2. **Pass B (decide):** send the same `user` with `\n\nROD_REASONING_CONTENT:\n<reasoning>`
   appended. The model re-reasons from its own draft and must emit exactly one JSON
   object. The engine parses it; on failure it retries with a temperature bump
   (`llm_parse_retries`, default 2).

```
   (system,user) --PASS A--> brain --> reasoning_A
                                          |
        user + "ROD_REASONING_CONTENT:" + reasoning_A
                                          |
                       --PASS B--> brain --> {strict JSON record}
```

This mirrors how a reasoning model separates its private `<think>` stream
(`reasoning_content`) from its committed answer (`content`) — but externalized so it
works for non-reasoning models and for the file/browser brains too. It lets a small
(e.g. 4B) model think first, then commit clean JSON without format pressure during
reasoning.

### 2.3 Roles and their JSON records

| Role     | record_type | Schema (data) |
|----------|-------------|---------------|
| Planner  | `task`      | `{"steps":[{"description":"...","done_when":"..."}]}` |
| Act      | `action`    | `{"conclusion":"EXECUTE\|CANNOT","actions":[{"verb":"...","target":"...","value":"..."}]}` |
| Verifier | `verdict`   | `{"confirmed":true\|false,"evidence":"...","reason":"..."}` |
| Reflector| `diagnosis` | `{"diagnosis":"...","suggestion":"...","should_replan":...}` |

Only **Act** sees the SCREEN. `[ID]` tokens are click/write targets; `[W#]` tokens are
window focus tokens. The actor must never declare DONE — verification decides
completion.

### 2.4 Brain transports

`llm()` in `runtime.py` dispatches on `prompts/model.json` `transport`:
- `openai` — POST to an OpenAI-compatible server (LM Studio).
- `file_proxy` — write `comms/slot1_cognition/request.json` (status `pending`), poll for
  `response.json` with a matching `id`, archive both. Any external agent (or a human, or
  another AI) answers by writing the response. **This is how a non-LM-Studio brain plugs in.**
- `browser_ai` — drive a browser to a hosted AI and read the reply off-screen.

**Transport contract:** `llm()` must return a `(content, reasoning)` tuple.
`llm_openai_compatible` and `llm_browser_ai` honor this. See the bug in §4.

### 2.5 Observation and actions

`desktop.py` (Windows-only, `ctypes` + UI Automation, no dependencies) produces the
SCREEN: it probes the desktop, classifies elements, assigns `[ID]`/`[W#]` tokens, and
builds a textual snapshot. `actions.py` executes verbs (`launch`, `focus`, `click`,
`write`, `press`, `hotkey`, `open_url`, `scroll`, `wait`, `remember`).

`engine.py main()` hard-exits unless `sys.platform == "win32"` — the system **must run on
native Windows Python**, not from WSL.

---

## 3. File map

| File | Purpose |
|------|---------|
| `engine.py` | HTTP server, graph walker, route handlers (`/step`, `/run`, `/state`, ...) |
| `runtime.py` | Helpers: transports (`llm`, `llm_file_proxy`, ...), `call_node` ROD loop, wiring/state IO, ports, codebase tools |
| `desktop.py` | Windows UIA observation + input simulation (ctypes only) |
| `actions.py` | Verb executor |
| `colony.py` | Multi-slot process manager |
| `nodes/*.py` | Bare node scripts executed by the engine |
| `prompts/wiring.json` | Topology, rules, roles, prompts, limits (slot 1) |
| `prompts/wiring_relay.json` | Slot-2 relay topology |
| `prompts/model.json` | Active transport + LLM params |
| `prompts/wiring-schema.json` | Wiring validation schema |
| `wiring-editor.html` | Browser workbench (graph editor + runtime inspector) |
| `RUNTIME-NOTES.md` | Append-only session log (durable cold-handoff memory) |

---

## 4. Current status: what works, what is broken

### Verified working
- WSL2 ↔ Windows bridge via `powershell.exe`: file read/write round-trips, Windows
  Python (3.13.x), git operations.
- Engine boots and serves on port 9077; `/health`, `/state`, `/step` respond.
- `file_proxy` request/response envelope: the engine writes a well-formed `request.json`,
  consumes a matching `response.json`, and archives both. Stepping advances one node.
- Routing for the session goal: `goal_inbox -> moe_route (signal: self) -> planner`.

### KNOWN BUG (blocks file_proxy end-to-end) — fix pending
`llm()` is declared to return `tuple[str, str]`. `llm_openai_compatible` and
`llm_browser_ai` both return `(content, reasoning)`. **`llm_file_proxy` returns a bare
string.** In `call_node`, `rod_content, rod_reasoning = llm(...)` then tries to unpack a
string into two names and raises `ValueError: too many values to unpack (expected 2)`.

Effect: every `file_proxy` LLM node crashes on Pass A; Pass B is never issued; the plan
never forms. Observed live as `state.last_error = "planner: too many values to unpack
(expected 2)"`.

**Fix (minimal, reversible, no new code paths):** make `llm_file_proxy` return
`(content, reasoning)` on its success path, where `reasoning` is the response's
`reasoning_content` (default `""`). This restores the transport contract. The stale
`-> str` annotation on `llm_browser_ai` is cosmetic (it already returns a tuple) and can
be corrected in passing.

---

## 5. What must be done to make it real (roadmap)

Confirm each item against live behavior; do not assume.

1. **Unbreak `file_proxy`** (the bug in §4). Prerequisite for any non-LM-Studio brain.
2. **Run with LM Studio** (`transport: openai`) to drive real plan → observe → act →
   verify loops on actual Windows, including the Opera→Grok handoff goal.
3. **Observation quality.** The SCREEN from `desktop.py` is large and flat. Restructure
   and de-noise so a small model gets hierarchy and signal, not a wall of probes.
4. **Verifier freshness.** Confirm whether the `verify` node judges against a *fresh*
   observation or a stale one; if stale, make it re-observe before judging.
5. **Prompts for small models.** Make role prompts short, direct, and meta so Pass B's
   reasoning is leveraged. Run a bake-off of several public computer-control-agent prompts
   adapted to the ROD loop; keep what measurably wins.
6. **Self-evolution loop.** Strengthen the `reflect`/`self_modify` path so failures lead to
   real adaptation (retry → replan → rewire), and ultimately to environment changes
   (e.g. installing a missing app) — the endgame behavior.
7. **Code reduction.** Favor fewer moving parts. Remove dead/duplicate logic as it is
   positively identified (verify before deleting).

---

## 6. How to run

Prerequisites: Windows 10/11, Python 3.10+ (3.13 verified). For `openai` transport, LM
Studio with a model loaded. For `browser_ai`, a browser (Opera) for grok.com.

```powershell
cd <repo>            # the endgame-ai checkout on the Windows filesystem
python engine.py     # serves http://127.0.0.1:9077/
```

Post a goal (autonomous):
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/run `
  -ContentType 'application/json' -Body '{"goal":"open notepad and type hello world"}'
```

Step one node at a time (observable):
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/step `
  -ContentType 'application/json' -Body '{"goal":"<goal>"}'
Invoke-RestMethod http://127.0.0.1:9077/state
```

Switch transport in `prompts/model.json`: `"transport": "openai" | "file_proxy" | "browser_ai"`.

---

## 7. Conventions

- Zero third-party dependencies. Standard library only.
- Work on a non-`main` branch; commit on every increment; never force-push or run
  destructive git.
- Keep changes small, explicit, reversible, and justified. Prefer reduction over growth.
- `RUNTIME-NOTES.md` is append-only durable memory; keep it free of personal identifiers.

---

## Appendix A — Handover prompt for a new session

> Copy-paste everything in this block into a fresh session (any AI). It is self-contained.

```
You are operating the Endgame-AI project on my behalf. Read README.md and RUNTIME-NOTES.md
in the repo first; they are the source of truth.

ENVIRONMENT
- You are in WSL2; Endgame-AI runs and is evaluated on NATIVE Windows 11.
- Do EVERYTHING on Windows via powershell.exe: file IO, Python, git. Never test in a
  WSL-simulated mode. engine.py hard-exits unless sys.platform == "win32".
- Repo lives on the Windows filesystem (under the user's Downloads). Python is Windows
  Python 3.13 (e.g. "C:\Program Files\Python313\python.exe"). Always `cd` to the repo path
  explicitly; PowerShell's default CWD from WSL is a \\wsl.localhost UNC path.

ANTI-HANG DISCIPLINE (mandatory)
- Wrap every powershell.exe call in a WSL-side `timeout N`.
- Give every Invoke-RestMethod a short `-TimeoutSec` inside try/catch.
- Run the engine detached (Start-Process, redirect stdout/stderr to logs); poll /health in
  a bounded retry loop. The detached engine survives `timeout` killing its launcher.

GIT
- Work only on the non-main branch `size-shrinking`. Never touch main. No force-push, no
  destructive git. Commit on every increment with a clear message.
- .gitignore is an allowlist (`*` then `!` lines). Only source files + README.md +
  RUNTIME-NOTES.md are tracked. Keep runtime artifacts (comms/, state.json, bus.json,
  snapshots, scratch helpers) untracked.

OPERATING MODEL (two modes + double step-gate)
- Mode A (the brain): with transport=file_proxy, the engine writes
  comms/slot1_cognition/request.json; you write response.json with the matching id.
  Honor the ROD two-call contract: Pass A (no ROD_REASONING_CONTENT in the user message) =
  reasoning prose; Pass B (user contains ROD_REASONING_CONTENT) = exactly one strict JSON
  record for the role. Wait >=2s before each response. A wiring_patch emitted in self_modify
  rewrites the system LIVE (hot-reload).
- Mode B (the operator): drive ONE node at a time via POST /step; observe; cross-reference
  prompts/code/wiring/logs; decide changes.
- Double step-gate: (1) advance the engine one node via /step; (2) on every finding,
  realization, or proposed change, STOP and report concisely, then WAIT for the human's "go"
  before implementing. Append every realization to RUNTIME-NOTES.md so a cold handoff works.

SAFETY
- Real desktop control is approved, but ONLY through the Endgame-AI system.
- HARD VETO: never let an action (Mode A verb) close or target the chat/terminal window that
  hosts the session — that would kill it. Refuse to write any response that would do so.
- Snapshot/commit wiring before runs so self-modifications are recoverable.

PORTS / TRANSPORT
- Engine serves on 9077 (slot 1). Set prompts/model.json "transport" to "file_proxy" when you
  are the brain, "openai" for LM Studio, "browser_ai" for grok.com.

SESSION GOAL
- Drive the browser-AI handoff: the system uses Opera to open Grok and converse with it as a
  brain. Step through it; evaluate every right/wrong/wasted decision. The larger aim is a
  wiring that makes the system self-evolving and environment-evolving (e.g. if Opera is not
  installed, it reasons that it must install it, and does).

KNOWN STARTING BUG (fix first if not already done)
- runtime.py llm() must return (content, reasoning). llm_file_proxy returns a bare string,
  which makes call_node's `rod_content, rod_reasoning = llm(...)` raise "too many values to
  unpack (expected 2)" and breaks every file_proxy LLM node. Fix: return (content, reasoning)
  on the success path (reasoning = response reasoning_content, default ""). Verify with
  py_compile, commit, then re-step the planner.

ROADMAP (see README §5): unbreak file_proxy -> real LM Studio runs -> improve observation
structure -> verify verifier freshness -> tune small-model prompts via a bake-off ->
strengthen reflect/self_modify for true self-evolution -> reduce code.

START SEQUENCE
1. Read README.md and RUNTIME-NOTES.md.
2. Confirm branch is size-shrinking and the WSL2<->Windows bridge works (a trivial PS file
   round-trip).
3. Continue from the latest RUNTIME-NOTES.md entry. Report the first finding and wait for go.
```

## Appendix B — Quick reference

- Engine: `python engine.py` on Windows, port 9077.
- One step: `POST /step` with `{"goal":"..."}` (omit goal after the first step).
- State: `GET /state`. Health: `GET /health`. Wiring: `GET/POST /wiring`.
- file_proxy I/O: `comms/slot1_cognition/request.json` (engine writes) /
  `response.json` (brain writes), archived under `comms/slot1_cognition/archive/`.
- Response shape the brain writes:
  `{"id":"<request id>","status":"complete","choices":[{"message":{"content":"<text or JSON>","reasoning_content":""}}]}`
- ROD: Pass A = reasoning prose; Pass B (user has `ROD_REASONING_CONTENT`) = strict JSON record.
