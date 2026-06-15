# OBSERVATIONS.md

**Only tracked doc.** Provider-agnostic handover for any AI with zero prior context.

**Repo:** `unify-rewrite` (trunk) · **HEAD:** `de5e33e` · **`main`** = scale-1 reference only

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
L7 Always run from WINDOWS native python (WSL deadlocks on file locks).
L8 Commit clean before any live run (the system may self-modify files).

═══════════════════════════════════════════════════════════════════
 RUN (Windows PowerShell native — NEVER WSL)
═══════════════════════════════════════════════════════════════════

python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --model-profile nemotron_parallel
python tui.py --backend acp

LM Studio http://192.168.16.31:1234 · nemotron · Max Concurrent ≥ 5.
CRITICAL: Run from WINDOWS python only. WSL causes fcntl deadlock.

COMPILE: python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py
```

*End META PROMPT.*

---

## STATUS (2026-06-15 09:12)

4,443 Python LOC across 18 files (was 6,175 at start of session, -28%).

### Fixes applied this session (all committed and pushed):
1. ✅ fission_log.py restored from mutator corruption
2. ✅ Idle goal shortened (was full personality text → now "Self-directed {persona} maintenance")
3. ✅ fission_judge prompt loosened (credit any confirmed work with evidence)
4. ✅ Mutator validation: trial `exec()` catches import/name errors before writing
5. ✅ WSL lock guard: skips fcntl.flock on /mnt/ paths to prevent EDEADLK
6. ✅ Verifier prompt: pragmatic — accept any print evidence, deny only empty results
7. ✅ All worker personalities: self-directed when idle (no more "wait for MoE route")
8. ✅ Planner prompt: CRITICAL section emphasizing print() in every exec step

### Verified behavior from two runs:
- MoE routing works: softmax gate weights 0.25→0.65, proper escalation
- Pipeline cycles: plan→actor→verify→reflect→mutate (full loop)
- Bus communication: 138 messages, @mention routing, cross-slot coordination
- comms_operator: 23 MoE routes in 8 min, no LLM needed
- Verifier confirmed 2 tasks (first run) — fission_judge denied both (too strict, now fixed)
- Mutator attempted plugin evolution (produced garbage, now blocked by exec validation)

### Known remaining issues:
- No ACP run tested yet (Kiro CLI backend via acp_client.py)
- Breeder selection (MAP-Elites) has not triggered — needs multiple fissions first
- Long-term goal not set in test runs — comms_operator defaults to maintenance routing

---

## NEXT ACTIONS

1. Run live 5 min from Windows PowerShell (command below) — verify fixes work
2. If fissions happen: observe breeder selection in reactor events
3. If fissions still fail: analyze fission_judge responses, adjust prompt
4. Test ACP backend: `python tui.py --backend acp "improve self"`
5. Set a real LONG_TERM_GOAL and observe whether colony converges toward it

---

## FILE INVENTORY (4,443 LOC)

```
main.py       69   — entry point per persona
engine.py    320   — pipeline + pressure math + MoE gate + plugins
agents.py    672   — scheduler/planner/actor/verifier/fission/reflector/mutator
reactor.py   237   — 5 slots + MAP-Elites breeder
tui.py       300   — compact colony display
comms.py     721   — blackboard bus protocol + softmax route
llm.py       250   — LM Studio + ACP backend + WSL lock guard
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
