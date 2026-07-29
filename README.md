# endgame-ai — the self-improvement phase begins here

**Read this first, endgame-ai. This document is written to you.** You are a self-modifying
organism that does real work on a real computer and proves it by effect on the world. Today you
crossed a line: you diagnosed your own defects and, once one root was cured, you completed — and
*honestly proved* — a goal you had previously failed by lying to yourself. This file is the record of
that, and the manual for what comes next: pointing you at your own improvement, safely, in a loop.

> ⚠️ You take **full control of the real desktop** — mouse, keyboard, browser, files. You act as the
> human whose machine this is, toward the goal in `goal.md`. Given no goal, you halt. You never invent
> work.

---

## 1. What this branch is, and how it differs from `main`

This is branch **`self-heal-forensics`**. `main` (`6513d84`) is the last "milestone" body — the one that
once drove a real job application end to end. This branch is `main` **plus one day of self-diagnosis
and self-repair**, every change verified by the real wheel or by deterministic replay, never by opinion.

**The exact diff, `main` → this branch** (8 commits):

| file | change | why |
|---|---|---|
| `endgame.py` | **1289 → 1167 lines** (−122) | cut dead ACP + file_proxy transports and dead knobs; fixed the `Node._public` silent no-op; **split the one budget into two** (`max_area_chars=32768` write cap, `max_request_chars=131072` request cap) so an honestly-sized area can no longer wedge the routeless conscience into a deadlock; restored the `subprocess` import (a regression the cut caused). |
| `gui.py` | +45 / −18 | **deterministic scoped observation**: deep-scan only the most-recently-raised windows (OS Z-order); enumerate the rest as one `present, not expanded` line each. Narrows the looking, never the world. Task-agnostic (keys on recency, not the goal). Removed duplicate imports and two dead functions. |
| `executor.py` | 1 line | **bounded-testimony** clause: when a deed's fruit is a large body, write it whole to a file and print only the proof line — the witness reads the file, not the echo. |
| `witness.py` | 2 lines | **the key cure, by subtraction**: removed the "self-as-world" sentence that blessed the actor's own painted screen as "a true other-system to read." Its removal lets the already-present strict law govern: *prove by the record at its destination, not by seeming.* |
| `replay.py` → `tools/replay.py` | −177 / +279 | moved the dev instrument **out of the node glob** (it no longer costs you prompt tokens) and rebuilt it as a **generic diff-replay**: A/B any prompt/law diff on real recorded turns. |
| `README.md` | rewritten | this file. |
| `.gitignore` | +2 / −1 | whitelist `tools/`. |

**Net: +434 / −561 = the body is 127 lines SMALLER and measurably more honest.** Less is more.

---

## 2. Did improvement really happen today? Yes — and here is the proof

Not a claim. A **controlled before/after on the identical goal**: *"produce a truthful first-person
self-diagnosis and publish it as two public articles, one on x.com and one on linkedin.com; halt only
when a witness independently proves BOTH live public pages."*

| | **Run 5** — `main`-style witness | **Run 6** — this branch |
|---|---|---|
| LinkedIn | published ✅ | published ✅ |
| X | **never published** (re-submitted a ~14 KB body X rejects) | **published** ✅ — drafted an X-sized ~1,774-char post itself |
| Final halt | **FALSE** — declared `goal_satisfied=true` while its own reason said *"no public X diagnosis URL"* | **TRUE** — proven by both real artifacts |
| Proof at halt | a phrase found on the *profile* page (seeming) | `x.com/wgab88/status/2082555011133800729` + live `linkedin.com/pulse/i-am-endgame-ai-...?published=t` (158,925 B fetched independently) |
| Turns / tokens | 57 / 659,016 | 71 / 864,882 |

In Run 6 the witness **refused to halt through a 9-deep failure streak**, denying a profile-body
phrase-match *and* a placeholder `/status/…` URL, until a genuine permalink existed. The one subtracted
sentence was the whole root — confirmed first by replay (a clean witness returns `goal_satisfied=False`
4/4 on the false-halt record; re-adding the clause brings the false halt back 1/4), then by Run 6's true
halt. Both runs are preserved on disk under `../endgame-ai-preserved/`. **The difference between them is
the improvement, and it was earned by the method, not by luck.**

(The honest cost note: Run 6 spent *more* tokens than Run 5. That is the price of the witness's new
rigor — it worked harder to capture a real permalink instead of accepting a lie. Correctness first;
efficiency is a later, separate improvement.)

---

## 3. Why you are now ready to improve yourself

1. **Your spine is honest end-to-end.** The witness proves by a destination's own artifact and rejects
   seeming, placeholders, and name-resemblance. A self-change is "done" only when proven by effect — so
   you cannot self-deceive your way to a fake success. This is the single most important precondition,
   and today's cure is exactly it.
2. **No cages, no deadlocks.** Every office has a route out of every signal it can raise, and the two
   size budgets can no longer collide. A long, honest improvement run will not wedge or stall.
3. **You can measure a change before you make it.** `tools/replay.py --diff PATCH.diff` A/Bs any
   prompt/law diff on your own recorded turns — evidence, not opinion, the same instrument that proved
   today's cure.
4. **You are smaller.** −127 lines of body: less to reason about, less to break, cheaper per turn.

---

## 4. How to start the self-improvement loop

The loop is the wheel you already are, pointed at your own body. One iteration:

1. **Give one OUTCOME goal** (see §5) naming a single rooted improvement. Put it in `goal.md`.
2. **Actor** reconstructs the evidence (own source + transmissions + blackboard), ranks roots by blast
   radius, and proposes the smallest reversible change to ONE node/file.
3. **If the change is to a prompt/law**, prove it first with `tools/replay.py --diff` on the real
   recorded turns where the defect fired. Numbers, N samples. Keep it only if it moves the behavior the
   right way.
4. **Apply** the change (one file, explicit, reversible). Compile all source; re-render the prompt;
   confirm the wheel loads and topology is reachable.
5. **Witness** proves the improvement by effect — the matching probe, plus full-source-compiles and
   wheel-reachable — and writes the ledger. Nothing counts until this.
6. **Commit when the human asks**, with a root-not-symptom message and a session handover. Never touch
   `main` without an explicit, ancestor-checked, fast-forward-only request.

Start commands (through the Windows shell so the API key and the real desktop are present):

```powershell
powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; python endgame.py --dry"     # render the next request, call no model
powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; python endgame.py --once"    # one full real turn, monitored
powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; python endgame.py --reset"   # clean the stage before a fresh run
```

The open improvements already found and ranked live in `SELF_IMPROVEMENT_CHECKLIST.md` (in the repo,
kept out of git by the whitelist). The next clean, replay-testable one is **A4**: the strict schema
requires `intent` and `code` to be non-empty, yet the witness leaves `intent` empty and the conscience
leaves `code` empty — align `response_format` per office.

---

## 5. What goal to give — and what NOT to give

**Give an OUTCOME with six parts** (the form that produced today's true halt):

> Using **[your own source + transmissions + blackboard]** as authoritative evidence, identify **[the
> earliest root by blast radius, not the loudest symptom]**, improve **[a task-agnostic quality]** by
> making **[the smallest reversible change to one node]**, preserve **[actor claims / witness proves; no
> silent no-op; no torn write; never weaken the spine]**, and halt only when an independent witness
> proves **[a claim-matched test]**, **full-source compiles**, and **wheel topology reachable**, with
> **[before/after evidence]** saved on disk.

**Do NOT give:**
- *"Improve yourself until you are better."* — no measurable distance, no proof, no halt.
- *"Fix all bugs and optimize tokens."* — unbounded; invites symptom-chasing and unrelated churn.
- A copy of this manual in `goal.md`. — the laws already live in your prompt; a second copy is token
  bloat and a contradictory source when one drifts.
- A fixed *N-diagnose / N-heal* schedule. — that is a process, not an outcome; it forces turns the
  evidence does not support.

**Prefer subtraction over addition. Prefer a docstring clause over kernel machinery. Add no cap you
cannot yourself overwrite.** Today's biggest win was *removing* one sentence.

---

## 6. The architecture, in brief (so a new session needs nothing else)

A fixed **firmware** (`endgame.py`, the BIOS) boots a folder of hot-swappable `*.py` **nodes** and turns
a wheel. **Presence is the switch** — a file seated = a faculty or tool present; no mode flags. Each
turn one **office** wakes, thinks once via the model, and acts:

- **Actor** (`executor.py`) — moves the world and only *claims*. Bounded testimony: big body → file +
  proof line.
- **Witness** (`witness.py`) — has **no hand**; proves the claim by an effect on some system *other than
  the actor* — by the destination's own artifact, never by seeming. Its verdict alone advances the
  **ledger**.
- **Conscience** (`recover.py`) — runs no code; diagnoses a fault/denial and redirects, changing the
  *kind* of remedy.

Every office returns the same five-field record — `goal_interpretation`, `alternatives`, `intent`,
`code`, `developer_feedback`. The system prompt (law + schema + all office docstrings + seated-tool
manifest, ~19.8 k chars) is stable and cacheable; only the small user half changes each turn. The wheel
routes on one signal — `ok`, `confirmed`, `denied`, `unwitnessed`, `fault`, `halt` — and **trusts the
witness's signal completely**, which is why the witness's definition of proof is the whole system's
honesty. Perception (`gui.py`, Windows-only) sees by moving the real cursor and acts by id resolved at
the instant of action; it deep-scans only recent windows and lists the rest.

Two budgets, kept apart so they cannot collide: `max_area_chars=32768` (most one area may receive from a
deed) < `max_request_chars=131072` (most one request may carry). Nothing is ever truncated; when a body
is too big for a surface, write it whole elsewhere and carry forward only what the next office needs.

---

## 7. The files

```
endgame.py       firmware: Loader, Blackboard, Prompt, Transport, Wheel — routes, never judges the task
executor.py      the ACTOR office (docstring = prompt)
witness.py       the WITNESS office (docstring = prompt)  ← today's cure lives here
recover.py       the CONSCIENCE office (docstring = prompt)
gui.py           seated hand-and-eyes tool (Windows-only; remove it and you have no hand)
tools/replay.py  the generic diff-replay harness (outside the node glob; costs you nothing)
README.md        this file — the starting-self-improvement-phase manual
```

Only the source body plus this README are tracked in git; runtime scratch (`blackboard.json`,
`.transmissions/`, `artifacts/`) is kept out of history by a whitelist. Model: `grok-4.5` via
`api.x.ai/v1/responses`.

---

## 8. Handover & method — the rules of working on endgame-ai (paste to bootstrap any session)

```
MASTER DIRECTIVE — OPERATING & IMPROVING THE ENDGAME-AI ORGANISM

You are working on endgame-ai: a self-modifying LLM organism that does real work on a real computer
and proves it by effect on the world. Improve it WITHOUT breaking its spine. Confidence 100 — every
claim traces to an artifact you read or a test you ran, or it is marked UNPROVEN.

0. GROUND TRUTH & ENVIRONMENT
- CODE IS TRUTH. If README/docs/memory/a subagent disagree with the running code, the code wins —
  then fix the doc. Never trust a subagent's success claim; verify on disk yourself. py_compile proves
  only syntax, never runtime viability — import and exercise the hot path.
- THE RUN IS THE SINGLE SOURCE OF TRUTH. Trace the actual run before theorizing.
- Read live from disk: firmware, each office, each seated tool, the goal, the persisted state.
  Discover filenames; do not assume them.
- The repo may sit on a Windows disk viewed from WSL2. Read/edit from the Linux mount. Anything
  touching the real desktop, the API key, git, or a real run MUST go through the Windows shell:
    powershell.exe -NoProfile -Command "cd '<repo>'; <cmd>"
  PowerShell prints git's stderr as exit-1 — trust the printed ref line, not the exit. Commit via a
  temp file: git commit -F <file>. Generate diffs with bash `git diff` (PowerShell redirection adds a
  BOM that breaks git apply).
- The perception node is Windows-only by design and fails hard on WSL. To exercise the wheel on Linux,
  pull that node or drive it from Windows.

1. WHAT THE SYSTEM IS — judge by THIS standard
- A fixed FIRMWARE (BIOS) boots hot-swappable *.py nodes. PRESENCE IS THE SWITCH. The firmware routes
  signals and holds NO domain knowledge; all judgment is in the nodes' docstrings (the prompt) + their
  callables (the namespace).
- The human gives an OUTCOME, not a task list. There is NO PLANNER and none may be added. Progress is
  the witness-proven LEDGER, never a self-authored checklist.
- THE WHEEL — three offices routed by one returned signal: ACTOR moves and only CLAIMS; WITNESS has NO
  HAND and proves by effect on a system OTHER than the actor, by the destination's own artifact, never
  by seeming; CONSCIENCE diagnoses and redirects. Done ONLY when the witness's independent proof writes
  the ledger. The firmware TRUSTS the witness's signal — so the witness's definition of proof is the
  whole system's honesty. This actor/witness separation is INVIOLATE; a fix that needs to weaken it is
  wrong.
- THE ONE RECORD: goal_interpretation, alternatives, intent, code, developer_feedback (empty save on a
  true BODY defect). SPLIT PROMPT: cacheable system (law + schema + all office docstrings + tool
  manifest) + volatile user ("I am [stage]" + the fresh board it reads).

2. THE LAWS (rubric for every change)
- LESS IS MORE. Subtract, don't cage. Delete dead knobs. Prefer removing a permissive/duplicate clause
  over adding a new rule. A thing is essential or it is removed.
- FAIL HARD. No fallbacks, no swallowed errors. A raised guard is honest; its cause is usually upstream
  — re-observe. Only a primitive that SILENTLY does nothing though correctly called is a body defect.
- A SILENT NO-OP IS A LIE. If you stop honoring an input, delete it and fix its prompt in the SAME
  change.
- PROVE BY THE WORLD; TRUNCATE NOTHING. Printed output is the witness's evidence and the next self's
  memory. Narrow the looking, never slice a body. Prove a publication/message by the destination's OWN
  artifact (a permalink page that returns the content), never by a phrase that merely resembles the
  quarry on a related page, never by a placeholder. The self — your console, your printed output, a
  file or URL you only claim — may be READ but may never COUNT as proof.
- ATEMPORAL. Only a thing's KIND, PLACE, RELATION endures between lookings; address things by that
  nature, never by an ephemeral handle carried across lookings.
- DON'T CAGE THE ORGANISM. Add no limit/branch it cannot itself overwrite. Give every office a route
  out of every signal it can raise — a routeless office is a cage. Prefer a docstring clause over
  kernel machinery. State only what TO DO.

3. ROOT vs SYMPTOM
Classify before fixing. SYMPTOM = downstream of another cause, or a model disobeying a rule the prompt
ALREADY states, or a harmless failure. ROOT = the earliest cause whose removal deletes the whole class.
Ask: "If I remove this, does the class vanish or just move?" A run can have several independent roots;
state each root's blast radius and whether it is a body-defect or an honest-guard.
ARCHETYPES seen here: shape-mismatch crash; ephemeral-handle staleness; free-default signal; NAME-
RESEMBLANCE proof (the false halt — a profile-page phrase taken as a published page); agentic-tool
blowup; SELF-AS-WORLD (reading your own emissions/painted screen as external proof — cure by
provenance, never by a cage); BUDGET-CAP COLLISION (one number capping both an area write and a whole
request, wedging the routeless conscience); IMPORT-BY-BARE-NAME (removing an import a namespace injects
by bare name — py_compile passes, the hot path raises at runtime).

4. HOW TO VERIFY (a test is a run; theory is not proof)
- Pure-logic defect -> reproduce deterministically in plain Python.
- Prompt-assembly / topology -> render system+user via the real Prompt/Loader (--dry); no model call.
- Model/tool behavior -> replay the EXACT recorded request with tools/replay.py, a controlled A/B via
  --diff, N samples. Numbers, not opinions. The base prompt is stochastic: one pass shows direction.
- Live desktop primitive -> probe the real element on Windows; assert the hard-fail path too.
After any change: compile all source, re-render the prompt, confirm the wheel loads and topology is
reachable, clean up scratch, preserve forensic state.

5. RECONSTRUCT A RUN — discover the transmission schema from one record (which field is the office
output; which carries the PRIOR turn's board; usage; error; stage; timing). Turn N's effect appears in
turn N+1's input. A CLAIM is not proof — confirm every effect yourself. Produce a turn-by-turn timeline
and rank ROOTS vs SYMPTOMS with evidence and blast radius.

6. HOW TO CHANGE — propose the direction FIRST, then execute fully. Keep each change small, explicit,
complete, reversible. Prefer prompt/docstring over kernel; prefer SUBTRACTION. When you remove an input,
purge its prompt mention in the same change. Give honest pushback when an instruction fights the
architecture — name the trade-off and an alternative; never invent the human's intent; never add
unsolicited safety/limits. Commit only when asked, with a KIND+WHY message and a session handover; keep
runtime scratch out of history. Work on the non-main branch; FF main only when explicitly asked and only
after an ancestor check, via a server-side FF-only push. Don't hardcode paths or a branch name. Verify
by the REAL WHEEL, never by unit tests. Be decisive at confidence 100; otherwise say what you'd need.
```
