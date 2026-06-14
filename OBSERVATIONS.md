# OBSERVATIONS.md — AI handover (only tracked doc)

**Branch:** `bare-metal` · **HEAD:** update after commit · **Tags:** `unify-cut-0` → `unify-cut-1` → `unify-cut-2`

---

## Last observation (2026-06-14 — live boot OK)

Operator ran the colony after unify slim passes. **It works.**

| Check | Result |
|-------|--------|
| Reactor + 5 slots | All PIDs alive |
| Bus | Colony goal posted; MoE routed `@architect` |
| LLM | Nemotron via LM Studio responded (`api_schema: false`) |
| Pipeline | planner → actor → verifier on routed slot |
| Plugins | fission_log, web_sentinel ran |
| Desktop | observer UIA scan fired |

Boot command used: `python reactor.py --goal "maintenance: print ok on bus"` (profile `auto` → `nemotron`).

**Parallel LLM:** processes are parallel (6 PIDs); inference is **serialized** unless you use `--model-profile nemotron_parallel` and LM Studio Max Concurrent ≥ 5 (`LLM_MAX_CONCURRENT=5`, global lock off).

**Code reduced (this session):**

| | Before (`unify-cut-0`) | Now |
|--|------------------------|-----|
| Python LOC | ~6,257 | **~5,404** (−853) |
| Git-tracked files | 46 | **35** |
| `agents.py` | 1,318 | **734** |
| `reactor.py` | 961 | **740** |
| `schemas/` | 7 files | **deleted** |
| Docs in git | README/RULES/CONTRIBUTING | **OBSERVATIONS only** |

**Tomorrow (Codex / OpenCode / any zero-context tool):** copy handover block below; continue slimming toward ~3.5k LOC — `tui.py`, `comms.py` shims, optional `acp_client.py`. Do not re-add strict schemas, smokes, or immune-system guards.

---

Copy everything inside the block below into a zero-context AI session.

```text
═══════════════════════════════════════════════════════════════════
 ENDGAME-AI — meta vision & your job
═══════════════════════════════════════════════════════════════════

We are building a LIVING ORGANISM on Windows — not an agent framework.

Brain metaphor: simple specialized areas (observe, reason, act) wired together.
Intelligence emerges from wiring + goal, not from one clever module or Python guards.

STATUS (2026-06-14): LIVE BOOT VERIFIED. Unify passes landed. ~5,404 Python LOC.
Rollback tags: unify-cut-0 (pre-slim), unify-cut-1 (schemas gone), unify-cut-2 (docs slim).

YOUR JOB: shrink code toward ~3.5k LOC while keeping the science and desktop organ.
Each paper = one or two equations → a few lines of deterministic Python.
Delete wrappers, fallbacks, strict schemas, smokes, display bloat, immune-system checks.
Personalities + one shared goal self-regulate — no code blocklists.

═══════════════════════════════════════════════════════════════════
 PAPERS (read before changing behavior)
═══════════════════════════════════════════════════════════════════

1. MoE routing — Bause 2026
   https://arxiv.org/abs/2605.25929
   Code: comms.softmax_route, engine._moe_route (comms_operator only)
   Math: power = confidence; softmax over worker powers → route assignment

2. Pressure / stagnation — Rodriguez 2026
   https://arxiv.org/abs/2601.08129
   Code: engine._update_pressure, board["_pressure"], comms.post_telemetry
   Math: stagnation ramps with failures + time since fission; power = 1 - stagnation

3. Quality-diversity elites — MAP-Elites
   https://arxiv.org/abs/1504.04909
   Code: reactor.Breeder, breed_archive.json, comms.post_evolve, process_evolve_candidates

4. Plan–act–observe loop — ReAct (conceptual)
   https://arxiv.org/abs/2210.03629
   Code: agents pipeline scheduler→planner→actor→verifier→fission_judge→reflect→mutate

5. Blackboard / stigmergy (classical MAS — no single paper)
   Code: comms.py messages.json + events_bus.jsonl; bus-only between slots

═══════════════════════════════════════════════════════════════════
 ARCHITECTURE (same organism, scale 1 vs 5)
═══════════════════════════════════════════════════════════════════

One instance = main.py → engine.run(board) → agent pipeline.
Colony = 5× identical main.py + comms blackboard + reactor parent. NOT a rewrite.

Topology:
  tui.py → subprocess reactor.py
    slot1 = comms_operator (MoE thalamus)
    slots2-5 = workers (breedable personas)
    each slot: subprocess main.py — same code, different personality .txt

Personality = prompts/personalities/{name}.txt (full SYSTEM prompt).
Circuits = prompts/planner.txt etc. (short hints in USER message only).
Loose JSON hints in agents._CIRCUIT_HINTS — NOT strict schemas (deleted).

Desktop organ (KEEP): observer.py + win32.py + actions.py — see + act on Windows.
Metabolism (KEEP): exec, git, plugin mutation — always on, no sandbox flags.
NO code immune system — goal + personalities regulate; verifier reads evidence.

Bus = wiring only. Rods post/read comms; never call sibling processes.

═══════════════════════════════════════════════════════════════════
 CODE PATH (read in this order)
═══════════════════════════════════════════════════════════════════

comms.py   — bus protocol (~400 LOC core; trim mirrors/CLI next)
engine.py  — loop, pressure, MoE, plugins hot-swap
agents.py  — unified _call_circuit / _parse_json, one text-step planner (~734 LOC)
reactor.py — spawn slots, MAP-Elites archive (~740 LOC)
main.py    — one personality instance entry
tui.py     — human face (display bloat — trim next, ~605 LOC)
llm.py     — LM Studio backend (swappable)

═══════════════════════════════════════════════════════════════════
 LAWS (slimming)
═══════════════════════════════════════════════════════════════════

L1. No new .py files — merge inward.
L2. Delete before add — net LOC must shrink each pass.
L3. One LLM pattern (_call_circuit) for all roles; no AST zoo.
L4. Keep desktop stack; shrink elsewhere.
L5. Never commit runtime/ or sessions/.
L6. Update OBSERVATIONS.md on every behavior-changing commit.

═══════════════════════════════════════════════════════════════════
 SIZE (measured)
═══════════════════════════════════════════════════════════════════

Now: ~5,404 Python LOC · 35 git files.
Target: ~3,500 LOC (wiring ~2,300 + desktop ~950 + prompts ~200).

Delete next: tui display, comms bus_* shims, acp_client if LMStudio-only.

Already removed: schemas/, dual planner, smokes, semantic regression guard, README/RULES/CONTRIBUTING.

═══════════════════════════════════════════════════════════════════
 RUN (human)
═══════════════════════════════════════════════════════════════════

python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --model-profile nemotron_parallel "Your long-term goal in one sentence"

Requires: LM Studio localhost:1234, nemotron-3-nano-4B.
Parallel rods: nemotron_parallel profile + LM Studio Max Concurrent ≥ 5.

COMPILE (no LLM):
  python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py

NOT IN GIT: runtime/, sessions/, events*.jsonl
```

*End handover block.*