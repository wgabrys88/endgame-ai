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

### 2026-06-28 — Engine launch + anti-hang discipline (Mode B)
- HANG ROOT CAUSE (fixed): issuing Invoke-RestMethod with no/long timeout could block the
  operator side. Also Start-Process with -PassThru keeps the PS pipe open so the launching
  PS process doesn't return until the detached child is killed.
- DISCIPLINE NOW (mandatory): wrap EVERY powershell.exe call in WSL-side `timeout N`; give EVERY
  Invoke-RestMethod a short `-TimeoutSec` inside try/catch; poll /health in a bounded retry loop
  rather than one blocking call. The detached engine survives `timeout` killing its launcher.
- Engine start command (Windows): python.exe engine.py in REPO, detached, stdout->engine.log,
  stderr->engine.err.log. Confirmed HEALTH_OK on port 9077, run.paused=False.
- Python is C:\Program Files\Python313\python.exe. NOTE: do NOT rely on PS job $using:PWD — it
  resolves to Documents; always pass the repo path explicitly.
- .gitignore is an ALLOWLIST (`*` + `!` lines). Added `!RUNTIME-NOTES.md` so the log persists in
  git for cold handoff. Snapshots/comms/state.json/bus.json remain (correctly) ignored.
- Commits on size-shrinking: 0784ca4 (baseline+transport), a2a6ee3 (track scrubbed notes).
- NEXT: /step is synchronous on LLM nodes — it blocks until response.json is written. Must
  service Mode-A request CONCURRENTLY: fire /step in background, then read request.json, write
  response.json (>=2s think-time). First goal: "use Opera to open Grok and have a conversation".

### 2026-06-28 — FINDING #3: file_proxy transport is BROKEN (blocks the whole mission) [Mode B]
- First real /step sequence: goal_inbox -> moe_route (signal `self`, stays in-slot) -> planner (LLM).
- Serviced planner PASS A as Mode A (reasoning prose, 6-step plan sketch). Response consumed &
  archived OK (atomic write + matching id works; bridge proven end-to-end).
- BUT /state then showed: step=0, plan_steps=0, last_error="planner: too many values to unpack
  (expected 2)". Pass B was never issued.
- ROOT CAUSE (runtime.py): `llm()` (line 511) is typed `-> tuple[str,str]`. Both
  llm_openai_compatible (line 521) and llm_browser_ai return `(content, reasoning)`. BUT
  llm_file_proxy (line 564) returns a SINGLE str (`return content`). In call_node (line 798)
  `rod_content, rod_reasoning = llm(system, user, ...)` unpacks into 2 -> a multi-char string
  unpacks as too many values -> EVERY file_proxy LLM node fails on PASS A. file_proxy has never
  worked with the two-call ROD loop on this branch.
- MINIMAL FIX (proposed, not yet applied): make llm_file_proxy return a 2-tuple. It already
  archives response and computes `content`; also surface reasoning_content. Change:
    return content                 ->   return content, reasoning
  where reasoning is read from the SAME response (choices[0].message.reasoning_content),
  defaulting to "". This makes file_proxy consistent with the other two transports. One-line-ish,
  reversible, reduces nothing but UNBREAKS the mission. No new deps.
- Note: this is a genuine code FIX (mission allows targeted fixes), not growth. Awaiting human GO
  before editing runtime.py.
- Engine state after error: run.running=False, _resume_node=planner (so re-stepping retries planner
  cleanly once fixed). Helper _brain_respond.py created (gitignored) to write responses with the
  >=2s think-time rule; it auto-detects pass A vs B by presence of ROD_REASONING_CONTENT.

### 2026-06-28 — REGROUP: README rewritten from zero + handover prepared (Mode B)
- Confirmed llm_browser_ai (runtime.py:673) returns `content, ""` (a 2-tuple) despite a stale
  `-> str` annotation; llm_openai_compatible returns a 2-tuple too. So llm_file_proxy is the ONLY
  transport returning a bare string. Diagnosis in FINDING #3 is fully confirmed.
- Rewrote README.md from scratch: vision, architecture (graph engine, ROD two-call, roles,
  transports, observation/actions), file map, current status (works vs the file_proxy bug),
  roadmap to "make it real", how-to-run, conventions, and Appendix A = self-contained HANDOVER
  PROMPT for a fresh session/any AI, Appendix B = quick reference. Scrubbed: no username/hostname.
- PLAN AFTER THIS COMMIT (human will then compact session, launch LM Studio, paste handover):
  next session unbreaks file_proxy (return (content, reasoning)), then does REAL LM Studio runs
  (transport=openai) of the Opera->Grok handoff, then observation/verifier/prompt work.
- The file_proxy fix is documented but NOT yet applied to code (still gated). engine left with
  run.running=False, _resume_node=planner. Engine may be running on 9077 from earlier; safe to stop.
