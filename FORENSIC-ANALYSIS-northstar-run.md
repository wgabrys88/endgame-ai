# FORENSIC ANALYSIS — North Star Run (turns 0–107)

Author: architect session 2026-07-25. Method: deductive, from this repo only
(endgame.md live body, .self/.git, .transmissions/*.json, git history, KB north-star).
Tooling: tools/transmission_parser.py (reusable, authored this session).

---

## THE GOLDEN QUESTION, ANSWERED

**Human asked:** *"Was the committed North Star code the seed that ran, or did the
organism mutate itself? Did node fitness and the self-evolve mechanism behave? Is
the system capable of self-healing/self-modifying — are we even needed anymore?"*

### 1. The organism DID heal its own body, mid-run, without a human. PROVEN.

Git archaeology on `endgame.md` settles it beyond doubt:

| commit | run | `click` primitive | clamp/re-derive present? |
|---|---|---|---|
| `1c69c71` | Run 1 STABLE (empty goal) | `def click(self, x, y, hwnd)` → **raises RuntimeError** on HWND-invalid (fail-hard seed) | **NO (0 hits)** |
| `6b0f292` | Run 2 Two Articles | `def click(self, x, y, hwnd=0)` → clamp + WindowFromPoint re-derive + center-fallback | **YES (1 hit)** |

- The **seed that started Run 2 had the fail-hard click** (no clamp).
- At **turn 93** (`.transmissions/turn-00093-execution`), after repeated
  *"prior actor click failed on HWND mismatch"*, the actor's `intent` was:
  *"Mend desktop click HWND/point resolution at source via commit_section."*
  It authored — verbatim — the clamp/re-derive `click` body that now stands in the
  committed body and in `.self/capabilities.py`.
- The compile-gate (`.self/_gate.py` + pre-commit hook) accepted it; `.self/.git`
  recorded exactly one commit `b1248b5 "section:capabilities"` at 03:23:07, ~5 min
  before halt (03:29). Capabilities recompiled in place; the mended click was then
  used to finish the task.

**This is the north-star self-repair clause, proven in the flesh: a broken primitive
diagnosed as a body defect, mended via `commit_section`, effective same-life, no human.**

`.self/capabilities.py` being byte-identical to the embedded capabilities section is
NOT evidence of a null mend — it is evidence the mend **persisted correctly** into the
one true body (`endgame.md`) via the engine's end-of-turn `write_board`, with `.self/`
as the compile-gate/audit mirror.

### 2. Node fitness / learning graph: DORMANT this run (not broken).

Across all 108 turns the parser found **zero** `save_node`, `call_node`,
`suggest_next`, `spawn_actor`, `web_search`, `ask_model` calls. `config.nodes` and
`node_edges` are still `{}`; `_spawn_left` still 3. The only capability calls were
`desktop.*` (296) and `open_url` (2), plus `commit_section` (turns 77, 93).

- This does **not** mean the graph is broken: the KB/README records it *proven in a
  prior run* (write_text_file node called 4×, fitness 2/4, edge weight 3.9, a spawn).
- It was dormant here because **the goal was linear and non-repeating** (navigate →
  generate image → download → compose → publish → cross-post), so no deed-type
  recurred to trigger a save, AND the prompt gates node use behind
  *"when a manner of deed hath proven itself and thou wouldst wield it again."*

### 3. Are we needed? — Honest verdict.

The organism autonomously: perceived, acted on a real desktop across two web apps,
generated media via grok, recovered from 37 faults, **diagnosed and repaired its own
click primitive**, and halted correctly without inventing a new goal. The north-star
property holds as reality. **We are not needed to turn the wheel.** We are still needed
to (a) hand the one-sentence goal, (b) own the environment it acts in, and (c) curate
which self-authored mutations become the canonical seed — which is exactly the decision
in front of us now.

---

## DEFECTS FOUND (100% confidence, cross-referenced)

1. **[LAW VIOLATION — introduced by the organism's own turn-93 mend] Click
   center-fallback.** The self-authored `click` contains:
   `# If mismatch, re-target click to center of intended hwnd rather than abort hard on stale coords`
   This is a silent fallback that contradicts the organism's own law
   *"Let faults rise unswallowed."* The clamp is defensible; the **center re-target is
   not** — on stale coordinates it should raise so `recover` re-derives from a fresh
   look. The organism, healing under pressure, healed itself in an un-law-clean way.
   **Fix in rebuild:** replace the center-fallback branch with a hard raise.

2. **`self._click_at(...)` is a dead reference** in the mended click (method never
   defined; `try/except AttributeError` always falls through). Vestige of the mend.

3. **Prompt defensiveness suppresses proven capability.** Verbatim offenders:
   `save_node` gated on *"when a manner of deed hath proven itself and thou wouldst
   wield it again"* (cold-start trap); `spawn_actor` *"Spawn sparingly … the budget is
   finite"*; `web_search` *"to learn a present fact the [screen] cannot show thee"*;
   `ask_model` *"to break a hard sub-decision"*; triple *"counsel … never proof."*
   Net effect: advanced faculties are framed as break-glass, so the organism rationally
   never reached for them.

4. **Engine reincarnation is one turn delayed, not "at once"** as the execute prompt
   claims (`heal_if_body_changed` runs at the *top* of the next `turn()`). Capabilities
   heal is genuinely same-turn; engine heal is next-turn. Prompt overclaims.

5. **`.self/` is write-only** — never read back on startup, so it provides audit + a
   compile-gate but **no crash recovery**. If a crash lands between the `.self` commit
   and end-of-turn `write_board`, the mend lives in `.self` but is lost to `endgame.md`.

6. **Duplication (subtraction targets):** `read_board` ×3, fence-extraction ×4, LLM
   transport ×3 (`call_llm`/`ask_model`/`web_search`), inline atomic-write vs
   `_atomic_json`. ~90 lines reclaimable with zero capability loss.

7. **Swallowed exceptions** in capabilities (`element_to_raw`, `harvest_subtree`,
   `_pattern_text`, `enum_windows`, `_pattern`) contradict fail-hard. Perception errors
   vanish silently and can feed the mind a broken world-view.

---

## PLAN OF ACTION (north-star-aligned, non-defensive, ordered)

**P1 — Preserve the truth of this run (do first).**
Freeze the seed vs the self-mutated body. Tag Run-2 body. Keep `.transmissions/` and
`tools/transmission_parser.py` in history as the forensic record. (This commit.)

**P2 — Law-clean the organism's own mend.**
Rewrite `click`: keep edge-inset clamp; **delete the center-fallback**, make HWND
mismatch raise with a message telling `recover` to re-observe. Delete dead `_click_at`
branch. This corrects the one un-law-clean thing the organism did to itself.

**P3 — Un-cage the faculties (prompt surgery, promise==provision preserved).**
Soften the five suppressive phrases so proven capability is reachable, without adding
machinery: `save_node` → "lay down a deed thou mayest wield again"; drop "sparingly"
from spawn; `web_search`/`ask_model` → "when the world outside this screen bears on the
deed." Change nothing in the namespace; only the register that gates use.

**P4 — Truth in the prompt.** Fix the engine-reincarnation "at once" overclaim to name
the one-turn delay, OR move `heal_if_body_changed` to fire mid-turn after a committed
engine mend. Prefer the latter (makes the claim true) if it stays law-clean.

**P5 — Subtraction pass (no capability loss).** Unify `read_board`, fence extraction,
LLM transport, atomic writes. Convert perception's swallowed excepts to hard raises
(fail-hard). ~90+ lines out.

**P6 — DO NOT delete the node/spawn graph.** It is proven-in-a-prior-run latent
capability (per KB), not dead weight. Keeping it whole honors "keep a thing wholly."
Its dormancy this run is a prompt-gating and goal-shape issue, addressed by P3.

**P7 — Verify by the real wheel** offline (`--no-gui --dry`, file-proxy mind): body
reads, config parses, engine/reset/capabilities compile, topology fully reachable,
every signal mapped. Then a bounded real-desktop smoke run.

---

## NEXT-PHASE HANDOFF (for post-compaction continuation)

- Truth is settled: **organism self-healed its click at turn 93; proven by
  1c69c71→6b0f292 git delta + turn-00093 transmission.** Start from P2.
- Use `python3 tools/transmission_parser.py` for any deeper log work
  (`--narrative`, `--turn N`, `--grep`, `--full`, `--csv`).
- Open question worth one probe: reconcile the KB's "node graph proven" against this
  run's dormancy by finding the prior run's transmissions if they exist elsewhere.
- Do not secularize the biblical register; distill only.
