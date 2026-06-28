# RUNTIME-NOTES.md — endgame-ai autonomous evolution session

> Durable, append-only log of this session. Written so a COLD HANDOFF (future session,
> the human, or a different AI provider) can resume by reading THIS FILE ALONE.
> Newest entries appended at the bottom. Do not rewrite history; only append.

---

## 0. MISSION (carry this verbatim)

- **Who/where:** Operator runs in WSL2; endgame-ai runs natively on **Windows 11**.
  ALL execution (file IO, Python, git) happens on Windows via `powershell.exe`.
  NEVER test in WSL-simulated mode.
- **Branch:** work ONLY on `size-shrinking`. Never touch `main`. No force-push, no
  destructive git.
- **Transport:** `file_proxy`. Engine writes `comms/slot1_cognition/request.json`;
  the operator (acting as the LLM brain) writes `response.json` with the matching id.
- **Two modes:**
  - **Mode A (brain):** stateless request→response. Honor ROD two-call (Call 1 reasons;
    Call 2 sees ROD_REASONING_CONTENT and emits exactly one JSON record). Wait >=2s
    before each response. A `wiring_patch` emitted in self_modify rewrites the system
    LIVE (hot-reload).
  - **Mode B (operator):** drive one cycle at a time via `POST /step`; observe; forensically
    cross-reference prompts/code/wiring/logs; decide changes.
- **Double step-gate:**
  1. System step — advance the engine one node via `POST /step`.
  2. Me step — on every finding/realization/proposed change, STOP and report concisely to
     the human, then WAIT for "go" before implementing.
- **Safety:** real desktop control ONLY via endgame-ai. NEVER close/target the chat window
  (kills the session). Snapshot/commit wiring before each run so self-modifications are
  recoverable.
- **Session goal:** browser-AI handoff — Mode A uses Opera to open Grok and converse with
  it as the brain. Step through; evaluate every right/wrong/wasted decision.
- **Endgame vision:** wiring that makes the system truly self-evolving and
  environment-evolving. Benchmark: goal "use Opera to open Grok and talk to it" → opening
  Opera fails → tries another way → finally reasons "Opera isn't installed, I must install
  it" → and does.
- **Likely fix areas (confirm live, do NOT assume):**
  1. Observation SCREEN output is messy/flat/no hierarchy — restructure + de-noise.
  2. Verifier freshness — does verify get a FRESH SCREEN before judging? Fix if not.
  3. 4B-model prompts — short, direct, meta so pass-2 reasoning is leveraged. Bake-off of
     ~10 public computer-control-agent prompts (gather via curl; no open web search).
- `max_attempts`: leave at 7 for the first observation run; propose 7→2 as a Mode B finding.

---

## 1. EVENT LOG

### 2026-06-28 — Bridge sanity-check (Mode B)
- `powershell.exe` reachable from WSL2 at `/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe`.
  WARNING: PS default CWD is a `\\wsl.localhost\<distro>\...` UNC path — ALWAYS `cd 'REPO'` first.
- Windows Python: **3.13.7**. Repo: `%USERPROFILE%\Downloads\endgame-ai` (referred to as REPO below).
- Git: on branch `size-shrinking`, working tree clean.
- Key files present: engine.py, runtime.py, desktop.py, actions.py; prompts/ has model.json,
  model_relay.json, wiring-schema.json, wiring.json, wiring_relay.json.
- Created this file. Next: verify PS read-back of this file, then verify `POST /step` + the
  request/response round-trip before any goal run.

### 2026-06-28 — Topology + transport (Mode B)
- Routes confirmed in engine.py: `POST /step` -> `step_once(goal,state,node_id)` advances ONE
  node and is SYNCHRONOUS (on an LLM node it blocks until response.json is written). So Mode-A
  servicing must run CONCURRENTLY with the /step call (background /step, foreground response).
- `POST /run` = autonomous loop (NOT used; we step). GET /state /wiring /health /bus /events(SSE).
- **PORT = 9077** for slot 1: http_port = base(9077) + (slot-1). README's 9078 = slot 2 (relay).
- file_proxy paths (model.json): comms/slot1_cognition/request.json|response.json, archive/, poll 1000ms.
- ACTION: flipped prompts/model.json transport "openai" -> "file_proxy".
- SAFETY VETO (from human): if Mode A ever emits an action that would close/kill THIS chat
  terminal window, Mode B must NOT execute it. Everything else proceeds; desktop control is wanted.
- Next: commit baseline on size-shrinking, start engine on Windows (port 9077), one /step with goal
  "use Opera to open Grok and have a conversation with it", service first request as Mode A, report.
