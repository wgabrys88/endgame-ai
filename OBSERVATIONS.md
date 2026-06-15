# OBSERVATIONS.md — LIVING SYSTEM PROMPT

You are continuing work on **endgame-ai**, a living organism that runs on Windows and does useful work by controlling the desktop (mouse, keyboard, screen reading) toward any long-running goal.

This file IS the prompt. Read it fully. Then act.

---

## IDENTITY

```
REPO:     github.com/wgabrys88/endgame-ai
BRANCH:   unify-rewrite (the only development branch — never use main)
PATH:     C:\Users\ewojgab\Downloads\endgame-ai
HEAD:     3b39409
LOC:      4,443 Python (target: under 2,000)
```

**What this is:** A self-evolving organism that decomposes any goal into parallel subtasks, assigns them to specialized workers based on expertise and fitness, executes them on the Windows desktop (keyboard, mouse, screen), verifies outcomes, and breeds better workers over time.

**What this is NOT:** An agent framework. Not a chatbot wrapper. Not a pipeline that runs once.

---

## YOUR WORKFLOW (mandatory for every session)

1. Read this file and the code (`*.py`, `prompts/`, `plugins/`)
2. Research the papers below (fetch abstracts, understand the math)
3. Deduce your own implementation plan based on current code vs. paper intent
4. Implement changes — no half-measures, no feature flags, no fallback paths
5. Compile check: `python -m py_compile *.py plugins/*.py`
6. **Rewrite this file** (not append) reflecting new state after each milestone
7. Commit and push: `git add -A && git commit -m "description" && git push origin unify-rewrite`
8. Repeat from step 3 until goal is achieved

**Rules:**
- Never create new .py files — merge inward, delete outward
- Net LOC must decrease or stay flat with each commit
- One LLM calling pattern only (`_call_circuit`)
- Prompts are code — evaluate and rewrite them as part of implementation
- No branching logic for "old vs new" — replace completely
- Update this file after every behavioral change
- Run from Windows PowerShell only (never WSL — deadlocks on file locks)
- Never commit `runtime/` or `sessions/`
- Use `git push origin unify-rewrite` (Windows credential via git.exe if in WSL)

---

## THE VISION

Five cheap local LLMs (nemotron on LM Studio, $0 cost) running in parallel. Each too stupid to solve complex problems alone. But wired together with deterministic math — softmax routing, pressure fields, evolutionary selection — they become a colony organism that:

1. **Decomposes** any goal into expertise-matched subtasks
2. **Claims** work to avoid duplication (bus coordination)
3. **Executes** on the real desktop (files, git, GUI, keyboard, mouse)
4. **Verifies** outcomes via screen observation and print evidence
5. **Breeds** better workers — the fittest personas get more slots
6. **Evolves** its own prompts and plugins under failure pressure
7. **Runs indefinitely** toward a long-term goal, replanning on every failure

The system must be **useful for any task**: writing code, managing files, browsing the web, filling forms, running builds, deploying software — anything a human does at a desktop.

---

## PAPERS — THE MATHEMATICAL FOUNDATION

You MUST research these papers, understand the equations, and ensure the code implements them faithfully. Do not approximate. Do not skip.

### 1. Mixture of Experts routing (Bause 2026)
- **Paper:** arxiv.org/abs/2605.25929
- **Equation:** `π_j = exp(β·C_j) / Σ_l exp(β·C_l)` where β=3.0, C=confidence=power
- **Intent:** Given an input (goal/task), route EXCLUSIVELY to the best expert. Winner-take-all or top-k with load balancing.
- **Current code:** `comms.softmax_route()` + `engine._moe_route()`
- **GAP:** Routing calculates weights but ALL workers grab the goal simultaneously. The gate result must ENFORCE exclusive assignment. Workers without assignment must stay idle or do maintenance.

### 2. Pressure Fields (Rodriguez 2026)
- **Paper:** arxiv.org/abs/2601.08129
- **Equation:** `P = Σ w_j·φ_j(signals)`, decay `f(t+1) = f(t)·e^(-λ)`
- **Intent:** Environmental pressure drives behavioral adaptation. High pressure = change strategy.
- **Current code:** `engine._update_pressure()` — stagnation = failures×0.6 + time_pressure×0.4
- **STATUS:** ✅ Working. Drives escalation and mutation triggers.

### 3. MAP-Elites evolutionary selection (Mouret 2015)
- **Paper:** arxiv.org/abs/1504.04909
- **Equation:** `archive[niche] = (solution, fitness)` — replace if `new_fitness > current`
- **Intent:** Maintain a DIVERSE archive of high-quality solutions across behavioral niches. Mutate solutions to explore. The "solution" being evolved should be the BEHAVIOR (personality prompt), not just a fixed label.
- **Current code:** `reactor.Breeder`
- **GAP:** Solution space is only 5 fixed persona names. True MAP-Elites requires evolving the personality PROMPTS themselves as solutions. The mutator currently patches plugins but never creates new behavioral variants.

### 4. ReAct reasoning loop (Yao 2022)
- **Paper:** arxiv.org/abs/2210.03629
- **Equation:** `thought → action → observation → repeat`
- **Intent:** Interleave reasoning with environment interaction. Each cycle produces observable evidence.
- **Current code:** `planner(think) → actor(act) → observer(see) → verifier(judge)`
- **STATUS:** ✅ Working end-to-end. Most faithful implementation.

---

## ARCHITECTURE (current)

```
tui.py → reactor.py → 5× main.py (slots)
  slot 1 = comms_operator (MoE router, deterministic, no LLM)
  slots 2-5 = workers (breedable personas)

Per worker pipeline (ReAct):
  scheduler → planner → actor → verifier → fission_judge → [reflector → mutator]

Bus: runtime/comms/messages.json (blackboard, all slots read/write)
Pressure: per-cycle stagnation/velocity tracking
Breeding: reactor reads evolve messages, maintains MAP-Elites archive
Desktop: observer.py (UIA screen reading) + actions.py (keyboard/mouse/exec)
```

---

## WHAT MUST CHANGE — THE ARCHITECTURAL REWRITE

The code is 4,443 LOC. Target is under 2,000. This requires OoO (Out-of-Order) programming: eliminate branching, eliminate defensive fallbacks, let the event-driven loop handle everything.

### Critical Fixes (in order)

**1. MoE must ENFORCE routing, not just calculate it**
- Human goal → ONLY comms_operator receives it
- comms_operator decomposes into subtasks via LLM (it currently doesn't use LLM — it should for decomposition)
- Each subtask routed to ONE worker via softmax gate
- Workers only plan goals explicitly assigned to them
- Unassigned workers do maintenance (self-improvement, cleanup)

**2. Workers must CLAIM and COORDINATE**
- Before planning, worker reads bus for other workers' claims
- Posts claim: "I am working on [subtask]"
- Planner prompt instructs: "filter through your expertise, avoid duplicating others"
- Natural stagger: personality-based delay (0-2s) so first worker's claim is visible to others

**3. MAP-Elites must evolve PROMPTS, not just swap labels**
- The "solution" in the archive should be the personality prompt TEXT
- Mutator creates variations of personality prompts under pressure
- Fission credit → store the winning prompt in archive[niche]
- On respawn → select best prompt from archive for that niche
- This gives genuine behavioral diversity and evolution

**4. Fission must flow (the fitness signal)**
- Fission = verified novel progress. It's the ONLY fitness signal for breeding.
- Judge must credit any confirmed work with evidence (loosened — done)
- "retain" evolve message → reactor archives it → breeding activates
- Without fissions, the organism cannot evolve. This is the heartbeat.

**5. Code unification — OoO event-driven**
- One event loop, one message format, one LLM call pattern
- Eliminate: duplicate state tracking, defensive try/except chains, fallback paths
- Every action is an event. Every response is an event. The loop processes events.
- Target: each file under 200 LOC. Total system under 2,000 LOC.

**6. Prompts are code — evaluate and evolve them**
- `prompts/*.txt` are not static config — they're executable behavior
- The planner prompt determines what the LLM does. A bad prompt = a bug.
- Evaluate prompt quality by fission rate (confirmed work / total cycles)
- Under pressure: mutator rewrites prompts (not just plugins)
- Store winning prompts in MAP-Elites archive as the "solution"

---

## CAPABILITIES (what the system can do NOW)

- **exec**: Run any Python code in the worker process (files, git, subprocess, network)
- **read_file / write_file**: Direct filesystem access
- **GUI**: Open applications, click elements, type text (via win32.py UIA bindings)
- **Screen reading**: Observe active window, read UI elements, parse text
- **Git**: Commit, push, branch, diff (via subprocess)
- **Bus communication**: Workers coordinate via shared blackboard
- **Self-modification**: Mutator can patch plugins and (should) evolve prompts
- **Breeding**: Fittest workers get more slots over time (when fission flows)

This means the system can do ANY desktop task: code, browse, fill forms, manage files, deploy, test, write documents, control other applications.

---

## RUN COMMANDS

```powershell
# Always from Windows PowerShell (never WSL)
cd C:\Users\ewojgab\Downloads\endgame-ai

# Clean runtime
python -c "import log; log.cleanup_runtime(deep=True)"

# Run with local LLM (LM Studio must be running at 192.168.16.31:1234)
python tui.py --model-profile nemotron_parallel "your goal here"

# Run with Kiro CLI backend (ACP mode)
python tui.py --backend acp "your goal here"

# Compile check (do this after every change)
python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py llm.py
```

---

## FILE MAP

```
main.py        69   entry point per worker slot
engine.py     320   main loop + pressure + MoE gate + plugins
agents.py     672   all pipeline agents (scheduler/planner/actor/verifier/fission/reflector/mutator)
reactor.py    237   5 slots + MAP-Elites breeder + respawn
tui.py        300   terminal UI for colony display
comms.py      721   blackboard bus + softmax routing + message protocol
llm.py        250   LM Studio HTTP + ACP backend + lock guard
log.py        123   JSONL event logging + session management
config.py     250   all constants, personas, profiles, thresholds
actions.py    362   desktop verbs (exec, read, write, GUI)
observer.py   401   Windows UIA screen observation
win32.py      366   ctypes UIA bindings
acp_client.py 252   Kiro CLI sequential prompting backend
python_code.py 41   syntax validation
plugins/       81   4 hot-swappable runtime plugins
prompts/       ~20  circuit hints + personality system prompts
```

---

## DONE (this session, 2026-06-15)

- Codebase slimmed from 6,175 → 4,443 LOC (-28%)
- fission_log.py restored from mutator corruption
- Fission judge loosened (credit confirmed work)
- Mutator validation: trial exec() catches broken imports
- WSL lock guard (skip fcntl on /mnt/ paths)
- Worker personalities made self-directed when idle
- Planner prompt: print() evidence requirement emphasized
- Verifier prompt: pragmatic (accept any evidence)

---

## NEXT MILESTONE

The system must complete ONE full cycle in a live run:
1. Human posts goal
2. comms_operator decomposes and routes subtasks (NOT broadcast)
3. Each worker plans its OWN subtask (not duplicate)
4. Workers execute, verify, earn fission credit
5. Reactor archives fitness → breeding activates
6. On next goal: fitter workers get priority

**When this works, the organism is alive.**

Then: reduce to under 2,000 LOC via OoO unification.
Then: evolve prompts as MAP-Elites solutions.
Then: long-running autonomous operation toward any goal.
