# OBSERVATIONS.md

**Only tracked doc.** Provider-agnostic handover for any AI with zero prior context.

**Repo:** `unify-rewrite` (trunk) · **HEAD:** `ce35234` · **`main`** = scale-1 reference only

---

## Session pin (2026-06-15)

4,440 Python LOC across 18 files (was 6,175 at start of session).
Two live runs analyzed: LMStudio (5min, successful pipeline) and ACP attempt (deadlocked on file lock from WSL).

---

## META PROMPT — copy from here

```text
═══════════════════════════════════════════════════════════════════
 ENDGAME-AI — zero-context handover (any AI provider)
═══════════════════════════════════════════════════════════════════

You have no prior context. This block is the full briefing.

TRIGGER: User says "continue with endgame-ai" → checkout branch unify-rewrite,
read OBSERVATIONS.md, work toward the NEXT ACTIONS below.

VISION: LIVING ORGANISM on Windows — not an agent framework.
Brain metaphor: simple areas (observe, reason, act) wired by a bus.
Intelligence = wiring + shared goal + personalities — not Python blocklists.
Papers = one or two equations each → few lines of deterministic code.

REPO: github.com/wgabrys88/endgame-ai
BRANCH: unify-rewrite (trunk). main = scale-1 reference — do not develop there.

═══════════════════════════════════════════════════════════════════
 PAPERS — DO NOT BREAK these equations in code
═══════════════════════════════════════════════════════════════════

MoE routing (Bause 2026) — arxiv.org/abs/2605.25929
  π_j = exp(β·C_j) / Σ exp(β·C_l)   β=3.0, C=power=confidence
  Code: comms.softmax_route + engine._moe_route

Pressure fields (Rodriguez 2026) — arxiv.org/abs/2601.08129
  P = Σ w_j·φ_j(signals), f(t+1) = f(t)·e^(-λ)
  Stagnation = weighted(failures*0.6 + time_pressure*0.4)
  Code: engine._update_pressure

MAP-Elites (Mouret 2015) — arxiv.org/abs/1504.04909
  archive[niche] = (solution, fitness)
  Replace if new_fitness > current. Selection = uniform random.
  Code: reactor.Breeder

ReAct (Yao 2022) — arxiv.org/abs/2210.03629
  thought → action → observation → repeat
  Pipeline: planner→actor→verifier→fission_judge→[reflector→mutator]

═══════════════════════════════════════════════════════════════════
 ARCHITECTURE
═══════════════════════════════════════════════════════════════════

  tui.py → reactor.py → 5× main.py (slots)
  slot1 = comms_operator (MoE router, no LLM)
  slots2-5 = workers (breedable personas)

Pipeline per rod: scheduler → planner → actor → verifier → fission_judge → [reflector → mutator]
Personality = prompts/personalities/{name}.txt (system prompt).
Circuits = prompts/*.txt (user-message hints per pipeline stage).
LLM output = loose JSON via agents._call_circuit / _parse_json.

KEEP: observer + win32 + actions (desktop organ), acp_client (Kiro backend).
KEEP: exec, git, plugin mutation — always on.

═══════════════════════════════════════════════════════════════════
 LAWS
═══════════════════════════════════════════════════════════════════

L1 No new .py files — merge inward.
L2 Delete before add — net LOC shrinks each pass.
L3 One LLM pattern (_call_circuit) — no AST zoo.
L4 Keep desktop stack (win32, observer, actions).
L5 Never commit runtime/ or sessions/.
L6 Update OBSERVATIONS.md on behavior-changing commits.

═══════════════════════════════════════════════════════════════════
 RUN (Windows PowerShell native — NOT WSL)
═══════════════════════════════════════════════════════════════════

python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --model-profile nemotron_parallel "goal sentence"
python tui.py --backend acp "goal sentence"

LM Studio http://192.168.16.31:1234 · nemotron · Max Concurrent ≥ 5.
CRITICAL: Run from WINDOWS python only. WSL causes fcntl deadlock on lock files.

COMPILE: python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py
```

*End META PROMPT.*

---

## ANALYSIS — last two runs (2026-06-15)

### Run 1: LMStudio (nemotron_parallel, 5 min, Windows PowerShell)
- 5 slots alive, 625 events, 80 bus messages
- MoE routing active: gate weights 0.25→0.65, escalation working
- Pipeline cycling: plan→actor→verify→reflect→mutate
- 2 verifier confirmations, 4 denials — verifier too strict
- 0 fissions — fission_judge denied both confirmations ("no changes detected", "gui:EXECUTE proves DONE_WHEN" rejected)
- Mutator ran and **corrupted plugins/fission_log.py** with relative imports and bogus code
- Plugin error spam: 66 events per slot from corrupted fission_log.py

### Run 2: LMStudio (nemotron_parallel, 8 min, triggered from WSL)
- 5 slots started, slot 1 (comms_operator) worked fine
- Slots 2-5: **all LLM calls failed** with `[Errno 36] Resource deadlock avoided`
- Root cause: WSL python uses `fcntl.flock` which deadlocks on Windows filesystem
- comms_operator routed correctly (23 MoE routes) despite worker failures
- Plugin error persisted (corrupted fission_log.py still in repo)

### Key Issues Found

1. **fission_log.py is corrupted IN GIT** — mutator wrote bad code, got committed accidentally
2. **WSL execution deadlocks** — the lock mechanism uses platform-specific syscalls; must run from native Windows python
3. **Fission credit is unreachable** — even confirmed verifications get denied by fission_judge because evidence is too weak ("gui:EXECUTE proves DONE_WHEN" isn't enough)
4. **Workers use full personality text as goal when idle** — `board["_personality_mission"]` is the entire system prompt (200+ chars), making bus messages unreadable
5. **Mutator produces garbage** — the validate_python check only validates syntax, not semantic correctness (relative imports from nonexistent modules pass py_compile)

---

## NEXT ACTIONS (priority order)

1. **Fix fission_log.py** — restore to original working version, commit
2. **Fix idle goal** — when SchedulerAgent sets fallback goal, use a short summary (not full personality prompt)
3. **Loosen fission_judge** — if verifier confirms AND evidence exists, fission should credit; current judge is too conservative
4. **Mutator validation** — after py_compile, do a trial `exec(compile(source, '<test>', 'exec'))` in isolated namespace to catch import errors
5. **Document: Windows-only execution** — WSL deadlocks; add guard or clear error message
6. **Run ACP test** — from native Windows PowerShell, with `--backend acp`, verify Kiro backend works

---

## FILE INVENTORY (4,440 LOC)

```
main.py       69   — entry point per persona
engine.py    320   — pipeline + pressure math + MoE gate + plugins
agents.py    670   — scheduler/planner/actor/verifier/fission/reflector/mutator
reactor.py   237   — 5 slots + MAP-Elites breeder
tui.py       300   — compact colony display
comms.py     721   — blackboard bus protocol + softmax route
llm.py       247   — LM Studio + ACP backend
log.py       123   — JSONL events, session folders
config.py    250   — slots, personas, profiles, priorities
actions.py   362   — desktop verbs + python exec
observer.py  401   — Windows UIA screen observation
win32.py     366   — ctypes UIA bindings
acp_client.py 252  — Kiro CLI sequential backend
python_code.py 41  — syntax validation
plugins/ (4)  81   — hot-swappable runtime plugins
prompts/      ~20  — circuit + personality text files
```
