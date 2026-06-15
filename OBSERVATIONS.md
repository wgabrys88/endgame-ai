# OBSERVATIONS.md

**Only tracked doc.** Provider-agnostic handover for any AI with zero prior context.

**Repo:** `unify-rewrite` (trunk) · **HEAD:** `pending` · **`main`** = scale-1 reference only

---

## Session pin (2026-06-15)

Starting: 6,175 Python LOC across 18 files.
Target: ~3,500 LOC (stretch) / ~4,400 (realistic given desktop organs = 1,129 LOC untouchable).
Current: **4,440 LOC** (-1,735 from start, -28%).
Live boot verified 2026-06-15: 5 slots, 625 events, 80 bus messages, MoE routing active, pipeline cycling.
Mutator attempted plugin evolution (expected: some failures). No fissions (verifier strict — needs better print evidence from actors).
HEAD: pending → will update after push.

---

## TASK LIST (self-managed)

- [x] Rewrite OBSERVATIONS.md as working tasklist
- [x] Flatten reactor.py Breeder to minimal MAP-Elites (~50 LOC archive)
- [x] Gut tui.py display bloat (target: ~350 LOC)
- [x] Slim comms.py — remove bus_* actor shims, format_breeder_evidence bloat
- [x] Slim agents.py — compress reflector+mutator, trim helpers
- [x] Trim llm.py — remove fingerprint/trace overhead
- [x] Trim config.py — remove dead profiles, ACP bloat stays
- [ ] Trim engine.py — simplify MoE to match paper (deferred: already lean at 320 LOC)
- [x] Final LOC count + compile check
- [x] 5-minute live run via PowerShell, evaluate results
- [ ] Update OBSERVATIONS.md HEAD, push final

---

## PAPERS — equations that matter (DO NOT BREAK)

### MoE routing (Bause 2026) — arxiv.org/abs/2605.25929
```
π_j = exp(β · C_j) / Σ exp(β · C_l)
```
C = confidence = power. β=3.0 in code. Route to highest-weight worker.
Code: `comms.softmax_route` + `engine._moe_route`

### Pressure fields (Rodriguez 2026) — arxiv.org/abs/2601.08129
```
P = Σ w_j · φ_j(signals)
f(t+1) = f(t) · e^(-λ)
```
Stagnation = weighted(failures*0.6 + time_pressure*0.4). Decays via time since fission.
Code: `engine._update_pressure`

### MAP-Elites (Mouret 2015) — arxiv.org/abs/1504.04909
```
archive[niche] = (solution, fitness)
if new_fitness > archive[niche].fitness: replace
selection = uniform random from archive
```
Code: `reactor.Breeder` (simplify to ~50 LOC faithful implementation)

### ReAct (Yao 2022) — arxiv.org/abs/2210.03629
```
thought → action → observation → repeat
```
Pipeline: planner(thought) → actor(action) → verifier(observation) → fission_judge(progress).
Reflector+mutator = recovery path under pressure only.

---

## ARCHITECTURE

```
tui.py → reactor.py → 5× main.py (slots)
slot1 = comms_operator (MoE router)
slots2-5 = workers (breedable personas)
```

Pipeline per rod: scheduler → planner → actor → verifier → fission_judge → [reflector → mutator]

KEEP: observer + win32 + actions (desktop organ), acp_client, bus science.
DELETE: display bloat, over-engineered Breeder trials, bus shims, dead config.

---

## LAWS

L1 No new .py files — merge inward.
L2 Delete before add — net LOC shrinks each pass.
L3 One LLM pattern (_call_circuit) — no AST zoo.
L4 Keep desktop stack (win32, observer, actions).
L5 Never commit runtime/ or sessions/.
L6 Update OBSERVATIONS.md HEAD on behavior-changing commits.

---

## RUN

```
python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --model-profile nemotron_parallel "goal sentence"
```

LM Studio http://192.168.16.31:1234 · nemotron · Max Concurrent ≥ 5.
COMPILE: `python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py`
