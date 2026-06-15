# OBSERVATIONS.md — LIVING SYSTEM PROMPT

You are continuing work on **endgame-ai**, a living organism that runs on Windows and does useful work by controlling the desktop (mouse, keyboard, screen reading) toward any long-running goal.

This file IS the prompt. Read it fully. Then act.

---

## IDENTITY

```
REPO:     github.com/wgabrys88/endgame-ai
BRANCH:   unify-rewrite (the only development branch — never use main)
PATH:     C:\Users\ewojgab\Downloads\endgame-ai
HEAD:     2073669
LOC:      4,432 Python (target: under 2,000)
```

**What this is:** A self-evolving organism that decomposes any goal into parallel subtasks, assigns them to specialized workers based on expertise and fitness, executes them on the Windows desktop (keyboard, mouse, screen), verifies outcomes, and breeds better workers over time.

**What this is NOT:** An agent framework. Not a chatbot wrapper. Not a pipeline that runs once.

---

## RUNTIME MODEL

```
tui.py (TUI + keyboard input)
  └─→ reactor.py (spawns + monitors slots)
        ├─→ main.py (slot 1, comms_operator)    ─┐
        ├─→ main.py (slot 2, architect)          │  5 independent OS processes
        ├─→ main.py (slot 3, implementor)        │  sharing ONE bus file + ONE LLM endpoint
        ├─→ main.py (slot 4, reviewer)           │
        └─→ main.py (slot 5, devops)            ─┘
```

Each `main.py` is a **standalone process**. No threads, no async. They share:
- `runtime/comms/messages.json` — blackboard bus (read/write JSON)
- LM Studio HTTP at `http://192.168.16.31:1234` — accepts concurrent requests

**Parallelism is purely about the LLM server capacity:**

| Profile | LM Studio Max Concurrent | Behavior |
|---------|-------------------------|----------|
| `nemotron_parallel` | 5 | All 5 processes hit LLM simultaneously |
| `nemotron` | 1 | Global file lock queues them one at a time |
| `acp` | N/A | Single worker talks to Kiro CLI sequentially |

The architecture (MoE routing, pressure, breeding) works identically in parallel or sequential mode. Parallel = faster throughput. That's all.

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
- Use `git push origin unify-rewrite`

---

## PAPERS — THE MATHEMATICAL FOUNDATION

You MUST research these papers, understand the equations, and ensure the code implements them faithfully.

### 1. Mixture of Experts routing (Bause 2026)
- **Paper:** arxiv.org/abs/2605.25929
- **Equation:** `π_j = exp(β·C_j) / Σ_l exp(β·C_l)` where β=3.0, C=confidence=power
- **Intent:** Route EXCLUSIVELY to the best expert. Winner-take-all.
- **Code:** `comms.softmax_route()` + `engine._moe_route()`
- **STATUS:** ✅ Fixed. Human goals go ONLY to comms_operator. It decomposes and routes subtasks to workers via `bus_route()`. Workers only receive explicitly addressed messages.

### 2. Pressure Fields (Rodriguez 2026)
- **Paper:** arxiv.org/abs/2601.08129
- **Equation:** `P = Σ w_j·φ_j(signals)`, decay `f(t+1) = f(t)·e^(-λ)`
- **Intent:** Environmental pressure drives behavioral adaptation. High pressure = change strategy.
- **Code:** `engine._update_pressure()` — stag = failures×0.15 + time_since_fission
- **STATUS:** ✅ Working. Drives escalation and mutator triggers.

### 3. MAP-Elites evolutionary selection (Mouret 2015)
- **Paper:** arxiv.org/abs/1504.04909
- **Equation:** `archive[niche] = (solution, fitness)` — replace if `new_fitness > current`
- **Intent:** Maintain DIVERSE archive of solutions per niche. Evolve the BEHAVIOR PROMPTS as solutions.
- **Code:** `reactor.Breeder`
- **GAP:** Solution space is 5 fixed persona names. Should evolve personality PROMPTS themselves. Mutator currently patches plugins only — extend to prompt evolution.

### 4. ReAct reasoning loop (Yao 2022)
- **Paper:** arxiv.org/abs/2210.03629
- **Equation:** `thought → action → observation → repeat`
- **Code:** `planner(think) → actor(act) → observer(see) → verifier(judge)`
- **STATUS:** ✅ Working end-to-end.

---

## ARCHITECTURE

```
Per worker pipeline (ReAct loop):
  scheduler → planner(LLM) → actor(LLM/exec) → verifier(LLM) → fission_judge(LLM)
                                                                    │
                                                              credit? → evolve msg → reactor breeds
                                                              deny?  → reflector(LLM) → mutator(LLM) → retry

Goal flow:
  human types goal → bus post (kind=ping, pri=3, from=human)
    → comms_operator receives (ONLY recipient)
    → comms_operator plans: bus_route(to=worker, goal=subtask) × N
    → each worker receives its specific subtask via interrupt
    → worker plans, acts, verifies independently
    → fission credit → reactor archives fitness → breeding
```

**Key code paths:**
- `comms.inbox_match()` — human messages match ONLY comms_operator (fixed)
- `comms.apply_interrupt()` — sets board["goal"] from route payload
- `agents._active_claims()` — workers see what others are working on
- `agents._planner_state()` — builds LLM context with personality, claims, bus, desktop
- `engine._moe_route()` — escalation routing when workers are stuck (stag>0.7)

---

## WHAT REMAINS — NEXT WORK

### Immediate (needs live test validation)
1. Verify comms_operator LLM produces valid `bus_route()` exec steps
2. Verify workers plan DIFFERENT subtasks based on their routed goal
3. Verify fission credit flows (retain message → reactor archives)

### Then (code reduction)
4. Merge `acp_client.py` into `llm.py` (both are LLM backends)
5. Merge `observer.py` + `win32.py` into single `desktop.py`
6. Eliminate defensive try/except chains throughout
7. Target: each file under 200 LOC, total under 2,000

### Then (MAP-Elites prompt evolution)
8. Mutator evolves personality prompts (not just plugins)
9. Archive stores winning prompt TEXT as the "solution"
10. Respawn loads best prompt from archive for that niche

---

## CAPABILITIES

- **exec**: Run Python (files, git, subprocess, network) — print() required for evidence
- **GUI**: Click, type, press keys, scroll, focus windows (win32.py UIA)
- **Screen**: Read focused window title + UI element tree (observer.py)
- **Bus**: Post/read messages, route tasks, post progress
- **Self-modify**: Mutator patches plugins (hot-reloaded next cycle)
- **Breed**: Fittest workers survive; dead slots respawn from archive

---

## RUN COMMANDS

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai

# Clean runtime state before each test
python -c "import log; log.cleanup_runtime(deep=True)"

# Parallel (5 LLM calls at once — LM Studio Max Concurrent ≥ 5)
python tui.py --model-profile nemotron_parallel "Open Chrome and play Shakira She Wolf on YouTube"

# Sequential (1 LLM call at a time — slower but stable)
python tui.py --model-profile nemotron "Open Chrome and play Shakira She Wolf on YouTube"

# ACP mode (Kiro CLI backend — single worker)
python tui.py --backend acp "your goal here"

# Compile check after changes
python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py llm.py config.py actions.py log.py
```

---

## FILE MAP

```
main.py        69   entry point per worker slot (env: ENDGAME_PERSONALITY, ENDGAME_SLOT)
engine.py     320   main loop: interrupt → plugins → pressure → MoE → scheduler → pipeline
agents.py     690   pipeline agents + validate_python + _active_claims
reactor.py    237   spawn/kill/monitor 5 slots + MAP-Elites breeder
tui.py        320   terminal UI (full-width, per-slot event lines, bus feed)
comms.py      721   blackboard bus + softmax routing + envelope protocol
llm.py        250   LM Studio HTTP + global lock + ACP backend selector
log.py        123   JSONL event logging + session dirs + cleanup
config.py     250   constants, personas, model profiles, thresholds
actions.py    362   exec sandbox + GUI verbs (click/write/press/hotkey/scroll/focus)
observer.py   401   Windows UIA screen observation (tree walk + probing)
win32.py      366   ctypes UIA/user32 bindings
acp_client.py 252   Kiro CLI sequential prompting (JSON-RPC over stdin/stdout)
plugins/
  comms_beacon.py  18   posts telemetry to bus every 30s
  fission_log.py   22   tracks fission count changes
prompts/
  planner.txt            plan instructions (decompose for comms_op, expertise for workers)
  actor.txt              GUI action selection
  verifier.txt           outcome confirmation (pragmatic)
  fission_judge.txt      credit/deny novel progress
  reflector.txt          failure diagnosis
  mutator.txt            plugin patching
  personalities/         per-persona system prompts (5 files)
```

---

## COMPLETED (2026-06-15)

- MoE routing ENFORCED: `inbox_match` routes human goals → comms_operator ONLY
- comms_operator decomposes goals → `bus_route(to=worker, goal=subtask)`
- Workers receive ONLY explicitly routed subtasks (no duplication)
- `_active_claims()` shows workers what others are working on
- Planner prompt: comms_operator decomposes, workers filter by expertise
- All personality prompts tightened with expertise + claim awareness
- TUI: full terminal width+height, 4 event lines per slot, bus fills space
- Merged `python_code.py` into `agents.py` (file deleted)
- Deleted dead plugins: `lessons_decay.py`, `web_sentinel.py`
- Fixed `_evolution_fitness` → `_fitness` naming bug (fission chain unblocked)
- Fission judge loosened (credit any confirmed work)
- Mutator: trial `exec()` catches broken imports before writing
- WSL lock guard: skip `fcntl.flock` on `/mnt/` paths
- LOC: 6,175 → 4,432 (-28%)
