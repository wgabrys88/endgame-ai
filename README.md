# endgame-ai

Self-regulating Windows desktop automation. Pure Python 3.13, zero dependencies, raw ctypes.

Three mathematical pipelines (Lorenz chaos, PID controller, Jacobian sensitivity) govern behavior. LLMs provide intelligence. Python provides working memory. Mathematics provides controlled chaos.

---

## Current State (math-pulse branch, 2026-06-09)

Working system. Proven on both cloud (ACP/Claude) and local (LM Studio/gemma-4-e2b-it 2B).

### Proven Results

| Goal | ACP (Claude) | LM Studio (2B) |
|------|-------------|-----------------|
| write hello world to output.txt | 9 events, EXIT=0 | 20 events, EXIT=0 (self-corrected) |
| describe screen to output.txt | 9 events, 607b | 21 events, EXIT=1 (planner format) |
| open notepad type hello | opens notepad | OPENED NOTEPAD (first time, via win+r) |
| emit done | 5 events | 16 events, EXIT=1 (meta-goal limit) |

### Self-Evolution Proven

LM Studio "write hello world" run demonstrated the full adaptation loop:
1. Planner produced bad step → actor typed to nowhere
2. Verifier DENIED (evidence: output.txt not found)
3. Deny cleared plan → forced replan
4. 2B replanned with "write_file output.txt hello world"
5. Direct-execute caught it → wrote file → success
6. Verifier CONFIRMED (evidence: output.txt exists, 11 bytes)

---

## Architecture

```
observe(full screen) → math.decide_next_role() → dispatch → direct-execute OR LLM → loop
                              │
              ┌───────────────┼───────────────────┐
              │               │                   │
         Lorenz fork     PID pressure      Jacobian
         (chaos replan)  (reflector gate)  (verb tracking)
```

The **blackboard** (`Board`) holds all truth. `CONTEXT_POLICY` controls what each role sees.

Math decides WHO acts. LLMs decide WHAT to do. Python parses and executes when possible (direct-execute). Each LLM has a `recipient` field to request who goes next. Math can override via Lorenz fork or PID-triggered reflection.

### Roles

| Role | Purpose | When Called |
|------|---------|-------------|
| Planner | Generates multi-step plan | Once per plan (not per step) |
| Actor | Executes one action per step | When instruction is ambiguous |
| Verifier | Confirms goal complete | When plan exhausted |
| Reflector | Diagnoses loops, writes lessons, mutates prompts | When PID > 0.5 |

### Direct-Execute

When a planner step starts with a known verb and Python can parse the arguments, the actor LLM is skipped entirely. Python executes the action directly. This saves 1 LLM call + 1 observe cycle per step and eliminates actor confusion (2B confusing write vs write_file).

### Evidence Field

Verifier context includes an EVIDENCE section. Python checks the filesystem for filenames mentioned in the goal and reports existence + size. This solved the verify-deny loop that affected both backends.

### Full-Screen Probe

Observer probes the entire desktop (0,0 → screen_w, screen_h). All visible windows are rendered to the LLM in tree format. The 2B sees complete context and makes correct decisions (uses win+r, finds correct targets).

---

## Usage

```
python main.py "goal" --backend acp --event-budget 20
python main.py "goal" --backend lmstudio --event-budget 20
python analyze_run.py events.jsonl
python tui.py events.jsonl
```

Cleanup between runs:
```
del events.jsonl snapshot.json output.txt lessons.txt
```

---

## Files

```
main.py           Entry point, CLI, signal handling
orchestrator.py   Math-driven loop, plan-based execution, direct-execute, role dispatch
state.py          Blackboard (Board), 3 math pipelines, context rendering, evidence
config.py         All constants, CONTEXT_POLICY, delays, math params
observer.py       Full-screen probe (UIA + cursor hover), element classification, tree render
actions.py        10 verb handlers (click, write, hotkey, press, scroll, wait, focus, read_file, write_file, cmd)
dispatch.py       LLM call wrapper + JSON extraction from raw response
llm.py            Backend transport (LM Studio HTTP / ACP JSON-RPC)
acp_client.py     ACP protocol client (session management, streaming)
win32.py          Raw ctypes: UIA COM, SendInput, window management
log.py            JSONL event emitter + budget counter
tui.py            Independent file-watching event viewer
analyze_run.py    Post-execution statistics
prompts/          System prompts (mutable at runtime by reflector)
schemas/          JSON schemas enforced by LM Studio constrained decoding
```

---

## Design Rules

1. One loop. Mathematics controls scheduling.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py.
4. No fallback modes. Dead code is wrong code.
5. The three mathematical laws are non-negotiable.
6. Prompts are mutable by the organism at runtime.
7. The blackboard is the single source of truth.
8. Fewer moving parts beats theatrical autonomy.
9. Python IS working memory — what can be parsed deterministically should be.
10. Events measure behavior — every `log.emit()` = 1 event toward budget.

---

## Mathematical Pipelines

### Lorenz Attractor (controlled chaos)

Stagnation feeds Lorenz ODE. When trajectory crosses wings (x sign change) AND stagnation > 0.4: force completely different approach. Prevents loops.

### PID Controller (reflection gate)

Accumulates stagnation error. Promotes reflector when output > 0.5. Integral resets on step advance.

### Jacobian (sensitivity analysis)

Tracks screen-change per verb. Exposed to reflector for diagnosis.

### Self-Evolution Tiers

- Tier 1: Lessons persist to lessons.txt across runs
- Tier 2: Reflector mutates prompts at runtime (min 200 chars enforced)
- Tier 3: Code modification — future
- Tier 4: Resurrection — future

---

## Handover Prompt

Use this prompt when starting a fresh session to carry forward methodology and understanding:

```
You are working on endgame-ai — a self-regulating Windows desktop automation system.

LOCATION: /mnt/c/Users/%USERPROFILE%/Downloads/endgame-ai (WSL mount to Windows)
BRANCH: math-pulse
BACKEND: ACP (Claude via kiro-cli) primary, LM Studio (gemma-4-e2b-it 2B) validation

ARCHITECTURE:
- Pure Python 3.13, Windows 11, zero dependencies, raw ctypes for Win32
- Core loop: observe(full screen) → math.decide_next_role() → dispatch → direct-execute OR LLM → loop
- Three math laws: Lorenz chaos (replan on wing cross), PID (reflection gate), Jacobian (verb sensitivity)
- Plan-based execution: planner called ONCE, Python feeds steps sequentially
- Direct-execute: if step starts with known verb + parseable args, Python executes without actor LLM
- Evidence field: verifier sees filesystem proof for file-based goals
- Full-screen probe: observer scans entire desktop, ALL windows rendered to LLM

ROLES: planner (once) → actor (per step, skipped if direct-execute) → verifier (end) → reflector (PID>0.5)

METHODOLOGY — Courageous Scientist:
- Forensic code analysis FIRST, system runs only to VALIDATE
- State whether claims are tested or untested. Untested = experiment required
- Treat counter-intuitive requests as hypotheses to test, not errors to correct
- When results contradict claims, update plainly. No defensiveness
- Do not patch symptoms — find meta-root cause
- Do not compare to "conventional approaches"
- The 2B model is NOT too small — it's us who are not listening to the model

RULES (non-negotiable):
- Pyright strict: 0 errors, 0 warnings, 0 informations
- No comments. No docstrings. No magic numbers outside config.py
- No fallback modes. Dead code is wrong code
- No examples/templates/placeholder values in prompts (2B copies verbatim)
- No push without human approval. No commit without human approval
- Standard test window: 20 events. Cleanup runtime data between experiments
- Test on BOTH backends. Cross-reference results
- ASCII deduction mode for analysis

PROVEN FACTS (2026-06-09):
- Full-screen probe = single most impactful change for 2B behavior
- Verifier deny-loop was architecture bug (missing evidence), not model limitation
- Direct-execute reduces events AND removes actor confusion
- 2B self-evolution works: deny → replan → adapt → succeed
- 2B weakness is PLANNING (format, meta-goals), not perception or execution
- Schema descriptions not read by LM Studio — all semantics in system prompt
- Halt IS reachable (errors persist across Lorenz forks)

TESTING:
  python main.py "goal" --backend acp --event-budget 20
  python main.py "goal" --backend lmstudio --event-budget 20
  Cleanup: del events.jsonl snapshot.json output.txt lessons.txt

Read ALL source files before making claims. Be brave. Implement changes, no safety-hedging.
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
