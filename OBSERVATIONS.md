# OBSERVATIONS.md

**Only tracked doc.** Provider-agnostic handover for any AI with zero prior context (Grok, Codex, OpenCode, Cursor, etc.).

**Repo:** `unify-rewrite` (trunk) · **HEAD:** `31ac4bd` · **`main`** = scale-1 reference only

---

## How to use

1. `git checkout unify-rewrite && git pull`
2. Copy the **META PROMPT** block below into the assistant session (system or first user message).
3. User says **"continue with endgame-ai"** → read this file, execute handover, keep slimming.

**Rollback tags:** `unify-cut-0` · `unify-cut-1` · `unify-cut-2` · `archive/unify-pre-slim`

**Session pin (2026-06-14):** Live boot OK. ~5,404 Python LOC (was ~6,257). Schemas/smokes/immune guards removed. `bare-metal` merged into `unify-rewrite` and deleted.

---

## META PROMPT — copy from here

```text
═══════════════════════════════════════════════════════════════════
 ENDGAME-AI — zero-context handover (any AI provider)
═══════════════════════════════════════════════════════════════════

You have no prior context. This block is the full briefing.

TRIGGER: User says "continue with endgame-ai" → checkout branch unify-rewrite,
read OBSERVATIONS.md, shrink code toward ~3.5k LOC. Do not re-add strict schemas,
smokes, sandbox flags, or code immune-system guards.

VISION: LIVING ORGANISM on Windows — not an agent framework.
Brain metaphor: simple areas (observe, reason, act) wired by a bus.
Intelligence = wiring + shared goal + personalities — not Python blocklists.
Papers = one or two equations each → few lines of deterministic code.
Delete wrappers, fallbacks, display bloat. Keep desktop organ + bus science.

REPO: github.com/wgabrys88/endgame-ai
BRANCH: unify-rewrite (trunk). main = scale-1 reference — do not develop there.
STATUS: live boot verified 2026-06-14 · ~5,404 Python LOC · 35 git files
TARGET: ~3,500 LOC total

═══════════════════════════════════════════════════════════════════
 PAPERS — read before changing routing/pressure/breed/actor
═══════════════════════════════════════════════════════════════════

MoE routing (Bause 2026)
  https://arxiv.org/abs/2605.25929
  comms.softmax_route · engine._moe_route · comms_operator only

Pressure / stagnation (Rodriguez 2026)
  https://arxiv.org/abs/2601.08129
  engine._update_pressure · board["_pressure"] · comms.post_telemetry

MAP-Elites elites (quality-diversity)
  https://arxiv.org/abs/1504.04909
  reactor.Breeder · breed_archive.json · comms.post_evolve

ReAct plan-act-observe (conceptual)
  https://arxiv.org/abs/2210.03629
  scheduler→planner→actor→verifier→fission_judge→reflect→mutator

Blackboard / stigmergy (classical MAS)
  comms.py messages.json + events_bus.jsonl · bus-only between slots

═══════════════════════════════════════════════════════════════════
 ARCHITECTURE
═══════════════════════════════════════════════════════════════════

One rod = main.py → engine.run(board) → agent pipeline.
Colony = 5× same main.py + comms blackboard + reactor parent.

  tui.py → reactor.py → 5× main.py (slots)
  slot1 = comms_operator (MoE router)
  slots2-5 = workers (breedable personas)

Personality = prompts/personalities/{name}.txt (full system prompt).
Circuits = prompts/*.txt (short user-message hints).
LLM output = loose JSON via agents._call_circuit / _parse_json (no strict schemas).

KEEP: observer + win32 + actions (desktop organ).
KEEP: exec, git, plugin mutation — always on.
NO: protected-file lists, mutation sandbox, semantic regression diff guards.

═══════════════════════════════════════════════════════════════════
 CODE PATH
═══════════════════════════════════════════════════════════════════

comms.py → engine.py → agents.py → reactor.py → main.py → tui.py
llm.py = LM Studio backend (swappable)

DELETE NEXT: tui display bloat, comms bus_* shims, acp_client if LMStudio-only.

ALREADY REMOVED: schemas/, dual planner, smokes, README/RULES/CONTRIBUTING.

═══════════════════════════════════════════════════════════════════
 LAWS
═══════════════════════════════════════════════════════════════════

L1 No new .py files — merge inward.
L2 Delete before add — net LOC shrinks each pass.
L3 One LLM pattern (_call_circuit) — no AST zoo.
L4 Keep desktop stack.
L5 Never commit runtime/ or sessions/.
L6 Update OBSERVATIONS.md HEAD on behavior-changing commits.

═══════════════════════════════════════════════════════════════════
 RUN
═══════════════════════════════════════════════════════════════════

python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --model-profile nemotron_parallel "goal sentence"

LM Studio localhost:1234 · nemotron-3-nano-4B · Max Concurrent ≥ 5 for parallel rods.

COMPILE: python -m py_compile tui.py reactor.py main.py engine.py agents.py comms.py
```

*End META PROMPT.*