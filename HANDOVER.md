# endgame-ai — Final Handover Document (MoE Analysis)

**Generated:** 2026-06-13  
**Branch under analysis:** `colony/nemotron-run` (currently checked out)  
**Model in production:** `nvidia-nemotron-3-nano-4b@q6_k_xl` via LM Studio  
**Status:** 6-slot colony paused/stopped; runtime artifacts preserved for forensic analysis.  

> **Instructions to the next agent:** Read this document, then read the files it points to. Do not assume the code matches the docs; the docs were written from runtime evidence cross-referenced with source. Verify everything.

---

## 1. Executive Summary

This is a **Windows-based breeding reactor**: six parallel LLM agents ("fuel rods") running against LM Studio, coordinated through a JSON message bus, with plugin hot-swap, self-evolution (reflector/mutator), and a dedicated GUI slot. The system has been hardened over several iterations and is currently targeting the `colony/nemotron-run` branch for autonomous Nemotron experiments.

### What works reliably
- Boot: `python tui.py` spawns 6 rods via `reactor.py`.
- LM Studio host discovery, model-profile switching, and per-slot load balancing.
- Message bus (`runtime/comms/messages.json`) separates chat from work events (`events_bus.jsonl`).
- Role enforcement: only slot 6 / `gui_operator` can emit `desktop_*` code.
- Archive plugin preserves per-agent logs before the rolling window evicts them.
- Fission (progress credit) occurs when verifier + fission_judge both approve.

### What does NOT work reliably
- **Planner code quality:** the LLM generates Python with undefined variables, wrong Path usage, wrong git branch typos (`collony/nemotron-run`), and wrong `done_when` phrasing.
- **Verifier/fission pipeline:** many plans execute, but verifier denies them for trivial path/evidence mismatches; fission_judge is then strict and often denies.
- **Stagnation loops:** after a failure, the math stack (stagnation → PID → Lorenz) quickly saturates, triggering reflector/mutator loops that rarely produce actionable plans.
- **Prompt bloat:** planner prompts are 1.6K–2.2K tokens; the full goal text, bus, and history are repeated every cycle.
- **Self-evolution safety:** reflector/mutator can append rules to `prompts/*.txt` and `prompts/personalities/*.txt` without diff review.

### Bottom line for the next agent
The colony runs but is **credit-starved**: work happens, errors get logged, but fission credit is rare because the verifier is too literal and the planner is too sloppy. The highest-leverage fix is a **pre-actor code repair layer** plus a **standardized evidence format** so the verifier can parse output deterministically.

---

## 2. System Architecture (as observed in code + runtime)

### Process tree

```text
tui.py  ──► reactor.py  ──► main.py × 6 (slots n1–n6)
                │
                └─ math thread per rod (Stagnation, Lorenz, PID)
```

- `tui.py`: Spectrogram TUI, CHAT/EVENTS panels, pause toggle (Space), quit (q).
- `reactor.py`: Spawns slots, load-balances across `ENDGAME_LMS_HOSTS`, respawns dead rods.
- `main.py`: Parses args, loads personality from `prompts/personalities/<ENDGAME_PERSONALITY>.txt`, starts `engine.run()`.
- `engine.py`: Main loop, plugin hot-loader, scheduler chain, snapshot save.
- `agents.py`: All agent logic — scheduler, planner, actor, verifier, reflector, fission_judge, mutator.
- `actions.py`: `run_python()` subprocess runner + GUI verbs (click, write, focus, etc.).
- `llm.py`: LM Studio API client, host failover, model profiles.
- `comms.py`: Message bus, mentions, inject drain.
- `log.py`: JSONL event logs, rolling trim, pause gate.

### Data flow

```text
Planner LLM ──► plan (sequence[].code)
      │
      ▼
Actor ──► run_python(code) in subprocess
      │
      ▼
Verifier LLM ──► confirmed / denied
      │
      ▼
FissionJudge LLM ──► credit / deny
      │
      ▼
Fission ──► board["completed"].append(done_when), power += 1/elapsed
```

### Math stack (runs every 5 s)

1. **StagnationAgent** — computes `stagnation ∈ [0,1]` from plan progress history + consecutive failures.
2. **LorenzAgent** — chaotic oscillator; `energy` is magnitude; `wing_crossed` true when trajectory crosses an axis.
3. **PidAgent** — PID controller on stagnation; output feeds the scheduler.

The scheduler uses these to decide: reflect, mutator, replan (wing cross), execute active step, or verify.

### Roster (slot → personality → role)

| Slot | Personality | Primary function | Git authorized? | GUI authorized? |
|------|-------------|------------------|-----------------|-----------------|
| n1 | `git_expert` | git status/diff/commit/push | **YES** | NO |
| n2 | `implementor` | write plugins under `plugins/` | NO | NO |
| n3 | `doc_inspector` | write `runtime/comms/report.md` | NO | NO |
| n4 | `comms_operator` | bus orchestration, beacons | NO | NO |
| n5 | `quality_critic` | `py_compile` audits, `quality.json` | NO | NO |
| n6 | `gui_operator` | desktop observation & GUI actions | NO | **YES** |

### Branch targeting

- Current checkout: `colony/nemotron-run`.
- `config.TARGET_BRANCH = "colony/nemotron-run"` (override with `ENDGAME_TARGET_BRANCH`).
- `git_expert.txt` explicitly says push only to `colony/nemotron-run`; never to `reactor-personalities`, `colony/dev`, or `main`.
- **Observation:** despite this, event logs show `git push origin collony/nemotron-run` (typo) and attempts to commit runtime files. The prompt is not enough; code-level guardrails are needed.

---

## 3. Runtime Forensics (what actually happened)

### Session under analysis
- **Start:** 2026-06-13 09:00:15 UTC (from `events-child-n1.jsonl`)
- **End:** around 2026-06-13 09:22 UTC (last events)
- **Duration:** ~22 minutes
- **Total events per rod:** n1=411, n2=420, n3=382, n4=412, n5=360, n6=422
- **Fissions achieved:** n1=0, n2=1, n3=1, n4=3, n5=2, n6=4
- **Overall:** 11 fissions in ~22 min ≈ 0.5 fissions/min

### Event phase distribution (typical rod)

| Phase | Typical count | Meaning |
|-------|---------------|---------|
| `math` | 250–265 | Background math stack; most frequent event |
| `planner.pending` | 12–28 | Planner about to be called |
| `plan` | 12–22 | Planner produced a plan |
| `actor` | 7–17 | Actor ran Python code |
| `token_usage` | 16–27 | LLM call completed |
| `verify` | 2–7 | Verifier ran |
| `fission_judge` | 1–5 | Fission judge ran |
| `fission` | 1–4 | Progress credit granted |
| `observe` | 3–13 | Desktop observation (mostly n6) |
| `plugin.*` | 20–40 | Hot-loaded plugins (archive, telemetry, web_sentinel, etc.) |

### Failure taxonomy (real examples from logs)

#### A. Planner syntax errors (plan rejected before actor)

```text
n1: SyntaxError: invalid syntax (line 9)
n2: SyntaxError: unexpected character after line continuation character
n3: SyntaxError: invalid syntax (line 1)
n5: SyntaxError: unexpected character after line continuation character
```

**Root cause:** Nemotron emits malformed Python (line continuations, unescaped backslashes, Unicode quotes). The `python_code.validate_python()` check catches it, but only **after** the LLM call is paid for.

#### B. Actor runtime errors (most common)

```text
n1: AttributeError: 'str' object has no attribute 'write_text'
n1: FileNotFoundError: [Errno 2] No such file or directory: 'comms\quality.json'
n1: subprocess.CalledProcessError: git push origin collony/nemotron-run
n2: FileNotFoundError: plugins/report.py
n2: NameError: name 'pc' is not defined
n3: FileNotFoundError: ...\runtime\comms\runtime\comms\report.md
n4: NameError: name 'runtime' is not defined
n5: TypeError: unsupported operand type(s) for +: 'dict' and 'dict'
n5: TypeError: Path.mkdir() missing 1 required positional argument: 'self'
n6: KeyError: 'title'
```

**Cross-reference with code:**
- `actions.run_python()` prepends imports (`from colony_env import ...`) and runs the code in a subprocess with `BASE_DIR` as cwd.
- `colony_env.py` exposes `BASE_DIR`, `COMMS_DIR`, `PLUGINS_DIR`, etc.
- The planner **knows** these are pre-imported (`prompts/planner.txt` line 7), but Nemotron still invents names like `runtime`, `pc`, or uses `Path.mkdir()` as a static method.

#### C. Verifier denials (credit starvation)

Common denial reasons from the logs:

1. **Path mismatch:** output says "wrote report.md" but `done_when` says `runtime/comms/report.md`.
2. **No explicit artifact evidence:** output says "ok" or "clean" but does not echo the file path/size.
3. **Git no-op:** `done_when = "git commit successful"` but `git status` shows nothing to commit.
4. **Desktop observation-only:** output describes the screen but does not show the DONE_WHEN outcome.

**Cross-reference with code:** `agents.VerifierAgent._missing_artifacts()` uses regex on `done_when` to extract paths and checks disk. If the path regex fails, it denies before even calling the LLM. The LLM verifier prompt (`prompts/verifier.txt`) then demands exact path evidence.

#### D. Fission judge blocks

```text
n4 fission_blocked: "messages.json ... identical to a previously completed milestone with no new value"
n6 fission_blocked: "repeated GUI focus and typing actions but only program manager actions are visible"
```

**Cross-reference with code:** `agents.FissionJudgeAgent` uses the reflector prompt in `FISSION_REVIEW` mode. It sees `COMPLETED` list + similarity hint. It is correctly preventing duplicate credit, but because the colony keeps retrying the same small wins, progress stalls.

### Token usage summary (from event logs)

| Agent | Planner calls | Planner total tokens | Avg prompt/planner | Avg latency (ms) |
|-------|---------------|----------------------|--------------------|------------------|
| n1 | 19 | 37,289 | ~1,963 | 53,386 |
| n2 | 22 | 45,752 | ~2,080 | 45,183 |
| n3 | 18 | 39,433 | ~2,191 | 64,042 |
| n4 | 17 | 32,707 | ~1,924 | 50,778 |
| n5 | 12 | 23,263 | ~1,939 | 81,449 |
| n6 | 15 | 24,838 | ~1,656 | 39,034 |

**Observation:** Planner prompts are large because the context includes the full personality goal text, bus history, desktop dump (when GUI mode is on), and recent history. Reducing prompt size is high leverage.

### LM Studio log cross-check

- File analyzed: `C:\Users\px-wjt\.lmstudio\server-logs\2026-06\2026-06-13.1.log`
- Actual prompt truncations (`truncated > 0`): **0**
- Task cancellations: **30**, all clustered when the test harness killed the process tree.
- Context capacity: `n_ctx_seq = 9984`.
- Conclusion: **LM Studio is not truncating prompts.** Client-side timeouts/locks were removed because they hurt reliability; LM Studio's own queue is the correct backpressure.

---

## 4. Code-Path Analysis (MoE per subsystem)

### 4.1 Planner → Actor pipeline

**Files:** `engine.py:282-297`, `agents.py:PlannerAgent:460-510`, `agents.py:ActorAgent:512-540`, `actions.py:run_python:285-329`

**Expert opinion:** The planner has too much freedom. It outputs raw Python in `sequence[].code`, and the actor concatenates all steps into one script. Variable scope persists across steps (intentional), but this also means an undefined name in step 2 fails the whole plan.

**Evidence:**
- `n2` plan with 2 steps failed on `NameError: name 'pc' is not defined`.
- `n3` failed with `TypeError: Path.mkdir() missing 1 required positional argument: 'self'`.

**Recommended intervention:**
1. Add a **static repair step** between planner and actor:
   - Inject missing imports for names used but not defined.
   - Rewrite bare `runtime/comms/...` strings into `COMMS_DIR / "..."`.
   - Ensure `Path.mkdir()` is called on an instance.
2. Or, switch to a **structured action DSL** (verb + args) and compile to Python, rather than asking the LLM to write Python directly.

### 4.2 Verifier → FissionJudge pipeline

**Files:** `agents.py:VerifierAgent:543-584`, `agents.py:FissionJudgeAgent:586-644`, `agents.py:_missing_artifacts:143-151`

**Expert opinion:** The verifier is doing two jobs: artifact existence check (regex + disk) and LLM-based evidence review. The regex check is brittle; the LLM check is literal.

**Evidence:**
- `n1` denied because output said `comms\quality.json` instead of `runtime/comms/quality.json`.
- `n3` confirmed only when output literally said `wrote runtime\comms\report.md`.

**Recommended intervention:**
1. Standardize actor output format, e.g.:
   ```python
   print(f"ARTIFACT: {path} size={path.stat().st_size}")
   ```
2. Make `_missing_artifacts()` resolve paths relative to `BASE_DIR` more robustly (strip leading `runtime/comms/` vs `COMMS_DIR` confusion).
3. Give the verifier a deterministic pre-check before invoking the LLM.

### 4.3 Scheduler / math stack

**Files:** `agents.py:SchedulerAgent:288-423`, `agents.py:StagnationAgent:175-205`, `agents.py:LorenzAgent:208-237`, `agents.py:PidAgent:240-267`

**Expert opinion:** The math stack is sensitive. A single failure raises `consecutive_failures`, which quickly drives stagnation to 1.0 and PID output above the reflect threshold. This triggers reflector/mutator, but those agents rarely fix the root cause (bad planner code).

**Evidence:**
- After most actor errors, stagnation goes to 1.0 within 1–2 math cycles.
- Reflector is called, often suggests a rule, but the next planner still makes similar errors.

**Recommended intervention:**
1. Lower `STAGNATION_FAILURE_WEIGHT` or cap stagnation until multiple failures occur.
2. Make reflector **read the event log** and diagnose the exact error pattern, not just the trigger.
3. Distinguish "transient LLM slop" from "real bug"; do not escalate to mutator for syntax errors that will be fixed by a retry/repair step.

### 4.4 Self-evolution (reflector / mutator / personality evolution)

**Files:** `agents.py:ReflectorAgent:647-691`, `agents.py:MutatorAgent:1051-1105`, `agents.py:_apply_mutation:1005-1023`, `agents.py:_apply_personality_evolution:1026-1043`

**Expert opinion:** Reflector can append `RULE:` blocks to `prompts/planner.txt` and `EVOLVE:` lines to personality files. Mutator can write new plugins under `plugins/`. There is no diff review or rollback.

**Evidence:**
- `planner.txt` already contains appended rules like `RULE: continue_development` and `RULE: find_or_initiate_comms_quality`.
- `lessons.jsonl` contains a lesson `find_or_initiate_comms_quality` with score 5.
- `git_expert.txt` has an `EVOLVE:` line.

**Recommended intervention:**
1. Add a **sandbox diff-review step**: before writing any tracked file, emit the proposed diff to the bus and require human approval or a second LLM review.
2. Version-control prompt files so mutations can be reverted.
3. Make mutator target the **root cause** of failures (e.g., write a `path_utils.py` plugin) rather than generic fixes.

### 4.5 Message bus

**Files:** `comms.py`, `engine.py:248-251`, `agents.py:_render_field("bus"):879-880`

**Expert opinion:** Bus works. Chat is retained in `messages.json`; work events roll in `events_bus.jsonl`. Mentions are parsed with word boundary (`@grok` requires space after). Inbox (`pending_for`) is shown to the planner.

**Evidence:**
- `messages.json` contains beacons and one human message: "read your own source code and begin mutations and reflections to correct your problems..."
- No bus-related errors in logs.

**Recommended intervention:**
1. Human input is currently a special case. Treat `@Human` as a first-class peer with its own inbox.
2. Add a `bus_request` delegation ledger so rods do not duplicate work.

### 4.6 GUI subsystem

**Files:** `desktop.py`, `observer.py`, `actions.py:64-198`, `agents.py:_contains_desktop_call:96-98`

**Expert opinion:** GUI role enforcement works. Non-n6 planners that emit `desktop_*` are rejected. n6 successfully performs observations and actions.

**Evidence:**
- n6 achieved 4 fissions by focusing Program Manager and clicking UI elements.
- Fission judge correctly denied duplicate GUI observations.

**Recommended intervention:**
1. n6 still struggles with `KeyError: 'title'` when the element book changes. Make `desktop_*` helpers defensive.
2. Add a fallback in `observe_screen()` when UIA scan fails.

---

## 5. Unified Agent Architecture Vision

The long-term goal (stated in `AGENTS.md`) is to replace the hard-coded 6-slot roster with a **single event bus + generic agents**:

```text
Bus (messages.json)
  ├─ Human peer
  ├─ Grok peer
  ├─ GUI peer
  └─ N agent peers (personality + inbox)
         └─ Planner → Actor → Verifier → FissionJudge
```

### What needs to change

| Current | Target |
|---------|--------|
| `reactor.py` spawns 6 fixed slots | `reactor.py` spawns N generic `Agent` instances from a roster dict |
| `agents.py` has one class per role | One `Agent` dataclass; behavior driven by `Personality` + inbox |
| `prompts/personalities/*.txt` static files | `Personality` object loaded from file + runtime mutations |
| Scheduler picks role by slot | Scheduler picks next role from the agent's own pipeline state |
| `@Human` special-cased in TUI | `@Human` is a peer with inbox and reply rights |

### Why this matters
- Reduces code duplication.
- Allows dynamic scaling (spawn more agents for specific tasks).
- Makes human/Grok/specialist agents truly peers.

### Immediate stepping stone
Before the full rewrite, extract an `AgentConfig` dataclass and make `engine.py` parameterize the pipeline by personality. This unblocks experiments without breaking the current 6-slot setup.

---

## 6. Prioritized Action Plan for the Next Agent

### P0 — Stop credit starvation
1. **Add deterministic actor evidence.** Modify `actions.run_python()` or the planner post-processing to require output lines like:
   ```text
   ARTIFACT: runtime/comms/report.md size=1234
   ```
2. **Pre-actor static repair.** In `agents.py` before actor runs, parse the combined code and:
   - Replace bare relative path strings with `COMMS_DIR / ...` or `PLUGINS_DIR / ...`.
   - Ensure `Path(...)` instances are used correctly.
   - Inject `from pathlib import Path` if needed (though it is pre-imported, the LLM forgets).
3. **Verifier pre-check.** Before LLM verifier, check for `ARTIFACT:` lines that match `done_when` paths.

### P1 — Reduce prompt bloat
1. Move the static parts of the personality goal into the **system prompt** and keep the user context to facts only.
2. Compress bus context: only show inbox + 3 most relevant messages, not 10.
3. Cache the personality text and only include diffs in context.

### P2 — Harden self-evolution
1. **Diff-review gate:** Before `_apply_mutation` or `_apply_personality_evolution` writes a tracked file, emit a bus post with the proposed change and a 60-second human-approval window.
2. **Mutation quality filter:** The existing `_reject_mutation()` is too lenient; expand vague-rule detection.
3. **Rollback:** Keep a `.bak` of `planner.txt` and personality files before mutation.

### P3 — Stabilize the math stack
1. Reduce `STAGNATION_FAILURE_WEIGHT` from 0.08 to 0.04 and `STAGNATION_FAILURE_CAP` from 0.35 to 0.25.
2. Require 2 consecutive failures before stagnation can hit 1.0.
3. Distinguish syntax errors (retry/repair) from runtime errors (mutator).

### P4 — Code quality for planner
1. Add few-shot examples of correct Nemotron plans to `prompts/planner.txt`.
2. Add a "plan repair" LLM call when `python_code.validate_python()` fails.
3. Consider switching to a DSL for common actions (write_file, git_commit, bus_post) instead of raw Python.

### P5 — Long-run validation
1. Run `python test_reactor_full.py 600 --model=nemotron` and collect fission/artifact data.
2. After the run, analyze `C:\Users\px-wjt\.lmstudio\server-logs\` for queue depth and cancel events.
3. Update this handover with the new data.

---

## 7. Quick Reference

### Entry points

```bash
# Run the full colony (starts paused; Space for LIVE; q to quit)
python tui.py

# Run tests
python test_reactor.py 120 --model=nemotron
python test_reactor_collab.py 300 --model=nemotron
python test_reactor_full.py 360 --model=nemotron

# Compile check
python -m compileall -q .

# Post to bus
python comms.py post human "@n1 check git status"
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENDGAME_LMS_HOSTS` | `http://localhost:1234,http://192.168.16.31:1234` | LM Studio endpoints |
| `ENDGAME_LMS_MODEL` | `gemma` | Preferred model id substring |
| `ENDGAME_TARGET_BRANCH` | `colony/nemotron-run` | Branch for git_expert |
| `ENDGAME_REACTOR_SLOTS` | `6` | Number of rods |
| `ENDGAME_LMS_MAX_SLOTS_PER_HOST` | `3` | Spawn cap per host |

### Key files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Human/agent technical map |
| `GROK.md` | Grok Build handoff guide |
| `config.py` | All constants, model profiles |
| `engine.py` | Main loop, plugin loader |
| `agents.py` | All agent logic |
| `actions.py` | Python runner, GUI verbs |
| `llm.py` | LM Studio client |
| `comms.py` | Message bus |
| `prompts/personalities/*.txt` | 6 base personalities |
| `runtime/comms/messages.json` | Chat/beacon log |
| `runtime/comms/events_bus.jsonl` | Rolling work events |
| `events-child-n*.jsonl` | Per-rod detailed logs |
| `snapshot.json` | Last saved board state |

### Known dangerous patterns to watch for

1. `git push origin collony/nemotron-run` — typo from LLM.
2. `Path.mkdir('dir')` — should be `Path('dir').mkdir(...)`.
3. `COMMS_DIR / 'runtime/comms/report.md'` — double-nested path.
4. `subprocess.run([...], check=True)` with no `cwd=BASE_DIR`.
5. Plans with `done_when = "git commit successful"` when there are no changes to commit.
6. Runtime artifacts (`events*.jsonl`, `snapshot.json`, `runtime/`) being staged by git_expert.

---

## 8. Conclusion

The colony is a functioning, self-evolving system with clear separation of concerns and a working bus. Its bottleneck is **not** the LLM backend or the concurrency model; it is **planner code quality** and **verifier literalism**. The next agent should focus on:

1. A pre-actor code repair / DSL layer.
2. Standardized artifact evidence.
3. Prompt compression.
4. Self-evolution safety gates.

Do that, and the fission rate will rise significantly without changing the core architecture.

---

**End of handover.**
