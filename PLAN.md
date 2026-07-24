# PLAN.md — endgame-ai forensic conclusions, approved architecture change, and handover

Author: architect session 2026-07-24. Status: authoritative handover. This file exists so the
next session can act **without** re-reading any deleted `RUN_*` artifacts. The RUN files will be
removed; their evidence that still matters is quoted below. The live `endgame.md` on disk remains
the final authority for *what is*; this file records *what was learned* and *what we decided to do*.

Read order for the next session: (1) this file, (2) the `endgame-ai` knowledge base for durable
methodology, (3) the live `endgame.md` sections named below. Trust the live code over this file
where they disagree, and correct this file if so.

---

## 0. How we work (carry into every action)

- **Fail hard.** No fallbacks, no defensive branches, no silent swallowing. A visible fault drives
  correction; a swallowed one rots the system.
- **Never cage the organism.** Add no cap, guard, counter, or branch it cannot itself rewrite.
- **Subtraction over addition.** Remove a defect rather than wrap it. Reuse before adding. Binary
  essentiality: keep a thing wholly or delete it wholly.
- **Commits are the fallback.** We do not build test suites to feel safe; we commit often with
  precise messages and roll back if wrong. Every completed phase ends in one clean commit.
- **Verify by the real wheel, cheaply.** Default validation is `--dry` (see §7). A real GUI run
  costs time and requires **explicit operator permission** — ask first, never assume.
- **Cross-OS.** Git and any real system run go through the Windows PowerShell shell
  (`powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; ..."`),
  because the git credential manager and the GUI live on Windows. File edits happen from the
  Linux-mounted view. Bake no absolute path and no branch name into the body.

---

## 1. Forensic conclusions (deductions held at 100% confidence, evidence preserved)

The investigation compared two saved lives of the organism and the live body. Facts, each
independently verified against disk before the RUN files were slated for deletion:

1. **The body is stable; only memory drifts.** `config`/`engine`/`reset`/`capabilities` were
   byte-identical across both saved lives. Everything interesting happened in the memory tail.

2. **RUN_2 was the struggle; RUN_1 was the operator's response to it — not an earlier life.**
   Proven by three independent signals:
   - Wall clocks in the captured `## environment` tray: RUN_2 = `12:12:32 AM 7/24/2026`,
     RUN_1 = `12:17:44 AM 7/24/2026` — RUN_1 is **5m12s later**.
   - RUN_1's `## goal` carries an appended clause RUN_2 lacks:
     `USE ONLY PYTHON SCRIPTING TO ACHIEVE ANY OUTCOME YOU ARE CAPABLE OF WRITING ANY SCRIPTS`.
   - RUN_1 had `ledger = none yet`, `failure_streak = 0`, `turn = 1`, yet its
     `## developer_feedback` tail was **byte-identical** to RUN_2's long accumulated tail.
     `reset.py` defines `PRESERVE = {config, engine, capabilities, reset, goal, developer_feedback}`
     and clears ledger + streak. Therefore RUN_1 = a factory-reset relaunch issued *after* RUN_2
     stalled, with the goal edited by hand. Confidence 97%+.

3. **The organism genuinely self-evolved for 7 witnessed turns.** RUN_2's ledger records seven
   confirmed advances, each moving the file's content and adding real markers to its own body:
   `OBSERVATION CONTRACT` → `_stable_elem_dict` / `find` / `format_action_index_lean` →
   `_emit_action_index` (`OBSERVATION_WIRE_V1`) → more wraps → `_safe_elem_get`
   (`OBSERVATION_SAFE_GET_V1`) → `dry_observe_selfcheck` (`DRY_OBSERVE_SELFCHECK_V1`). This is the
   self-modification the project always aimed for. It is real.

4. **It then died in a terminal loop with two stacked causes.**
   - **Proximate cause — a quine-class quoting impossibility.** The actor authored a generator
     that builds a sidecar as `sidecar_src = r'''…'''` and embeds inside it another triple-quoted
     literal `SELFCHECK = '''…'''`. Python cannot nest triple quotes: the inner `'''` closes the
     outer string. Result: a 363-byte truncated `_fix_observe_residual.py`, `SyntaxError` at line
     12, dead before touching `endgame.md`. Every recovery re-proposed the same shape and re-hit
     the same wall. (The reconstructed 174-line sidecar additionally carried a duplicated loop and
     an `ungun` NameError at line 125 — it too could never run.)
   - **Deep cause — the organism can edit its genome but cannot test its phenotype.** Verified in
     the live body: `observe()` runs once per turn inside `environment()` (~line 1610), caching
     into `_LAST_OBS`, **before** the model thinks. The actor namespace built by `build(...)`
     (~lines 1602–1606) exposes only the **hand** — `click, type_text, paste_clipboard,
     set_clipboard, press_key, hotkey, scroll, open_url`. It does **not** expose `observe`, though
     `d.observe` exists. A sidecar subprocess has no live GUI at all. So the only "proof" the actor
     could produce was *"this text now exists in my source,"* which the witness **correctly**
     rejected as not runtime proof. The self-heal was an infinite source-patch regress that could
     never reach the running pipeline. This is honesty-by-structure working as designed, not a bug.

5. **The recurring developer_feedback is ~5 real defect classes drowned in ~10:1 restatement, plus
   ~87 empty-string sentinels** (legacy, pre-whitespace-guard, never pruned — pure token rot against
   a goal that explicitly demanded *less* token usage). The single most-repeated complaint
   ("document the `action_index` schema; add a `find()` helper") is a **valid grievance with a wrong
   diagnosis**: it calls `action_index` a `list[dict]`, but the live code (line 1317) declares
   `action_index: dict[str, dict[str, Any]]`, keyed by ephemeral `s{hex}-eN` short_ids.

6. **The 36 turns of self-surgery were discarded.** The live `endgame.md` contains **none** of the
   seven injected helpers — only the clean `observe`/`_render`/`build`/`environment`. The operator
   reverted the body. The runs are the fossil record, not the current genome.

---

## 2. The two problems the operator identified (both correct)

### Problem A — the hashing urge is invalid on a moving target
The witness repeatedly tried to prove change/effect by **checksumming dynamic state**: the SHA of
the ever-mutating `endgame.md` (the body IS the file; it changes every turn by design) and, in
earlier lives, the SHA of the screen (any blinking button or advert changes the hash). A hash of
moving water proves nothing. **The organism must have no urge to hash live state as proof**, and
the shared prompt must say so explicitly.

Precise nuance to preserve so §3 and this law do not contradict: **git commit identity is not this
sin.** Git object IDs name *immutable, frozen snapshots of history*, not live truth. Referencing a
committed snapshot by its id is bookkeeping; checksumming a living document or a live screen to
infer "did it change / did my act land" is the banned behaviour.

### Problem B — patching the single .md is wasted cognition
Self-modification today = the actor emits a full Python program that string/regex-rewrites its own
Markdown body, and must also reason about character-level escaping (the triple-quote quine that
killed RUN_2). This spends model capacity on *how to align characters* instead of *what change to
make*. It is fragile and, as proven, occasionally impossible.

**Operator's approved remedy (dependency law changed for git specifically):** give the organism its
own git. Git is free, needs no money, is known cold by the model, and makes patching *safe by
design* — a patch either applies or git rejects it, and history/branches are a free database. The
zero-dependency architectural vision is **amended to permit git**, by operator decision, and we
pursue it immediately.

---

## 3. Approved architecture change — git as the self-modification substrate

### 3.1 The core win, stated honestly
Git does **not** parse Python by itself; do not overclaim that. The real, free safety comes from
three native git properties, and we use all three:
- **Atomic apply-or-reject.** `git apply --check` validates that a patch's context matches before
  anything is written; a drifted or malformed patch is rejected loudly instead of silently
  corrupting the body. This directly removes the character-alignment cognitive load.
- **A fail-hard syntax gate for free.** A `pre-commit` hook that runs `python -m py_compile` on
  staged `.py` and `json.load` on staged `.json` aborts the commit on any syntax error (non-zero
  exit). This is the "git guards proper syntax" property — implemented as one small hook the
  organism authors once and may itself rewrite (so it is not a cage). A commit that lands is, by
  construction, syntactically valid.
- **History + branches as a database.** Each experimental change to a section lives on a branch;
  merge to the trunk only on a witness-confirmed advance. Variants are never lost; rollback is a
  checkout. This is the "everything becomes branches" leverage.

### 3.2 Where the repo lives (no collision with the outer repo)
On launch the engine ensures a **dedicated subdirectory** exists beside the document — proposed
name **`.self/`** (leading dot; unambiguous; self-modification workspace) — and runs `git init`
inside it if absent. Collision is avoided two ways at once: it is a *nested* repo in its own
directory (the outer repo only ever sees a directory), and the outer `.gitignore` is already
`*` + an explicit whitelist, so any new path is ignored by the outer repo automatically. Do **not**
rename `.git`; a nested repo needs no rename. Bake no absolute path: resolve `.self/` from the
document's own directory (`pathlib.Path(BOARD).resolve().parent / ".self"`), exactly as the engine
already resolves `reset.py` and `guidance.txt`.

### 3.3 The one constitutional decision the operator must rule on
The core law "one source of truth = the single document" collides with "sections live as files in a
git tree." Two lawful shapes; pick one:

- **Path A (recommended first — reversible, ~90% of the value):** `endgame.md` stays the authority.
  `.self/` is a per-life **validation sandbox**. Self-modification becomes: the actor writes the
  intended new content of a body section into its file in `.self/`, runs `git apply --check` / lets
  the pre-commit compile-hook gate it, commits on success; **only gated, committed content is then
  written back into `endgame.md`** by ordinary engine code. The witness proves by reading the
  committed file/commit on the branch — never by hashing the live document. This kills the quine
  and the patching pain, keeps single-source-of-truth intact, and is one revertible commit.
- **Path B (fuller vision, later, needs explicit ruling):** the `.self/` repo *becomes* the body —
  `config.json`, `engine.py`, `capabilities.py`, `reset.py` as tracked files, branches per variant
  — and `endgame.md` becomes a **regenerated build view** (the KB already sanctions a derived file
  as a build output, never a second authority). This is the "everything is branches" end state but
  is a genuine constitutional change; do not do it until Path A is proven in a real run.

Recommendation: **execute Path A now; treat Path B as a proven-then-promoted follow-on.** State the
Path A→B trade ("a legible single body for a learning, git-backed one") aloud before ever crossing
into B, per the KB's invariant.

### 3.4 Interaction with the witness (ties Problem A and B together)
Rewrite the verify contract so the witness proves a body change by **git fact** — the commit exists
on the branch, the file content is present and compiles (the hook already guaranteed it) — and by
reading the thing afresh, **never** by a checksum of the live document. This simultaneously
satisfies the anti-hash law and gives the witness a clean, independent, non-hash proof it currently
lacks.

---

## 4. The anti-hash law (exact prompt amendment)

Add one commandment to `config.shared_prompt_prefix` (it is data; the engine re-reads config each
turn, so it takes effect on the next turn within the same life). Proposed wording, in the existing
biblical register:

> "Hash thou not the living word nor the face of the [screen] to prove that a thing hath changed or
> that thy deed hath landed; the body is ever rewritten and the screen ever flickers, and a
> [checksum] of that which cannot hold still proveth nothing. Prove instead by reading the thing
> itself afresh and by the world's own effect. The [commit] identity of a frozen [git] snapshot is
> lawful memory of history, and is no such hash of moving water."

Also correct the verify stage prompt so the witness's notion of "independent effect" stops meaning
"run a different process such as a process-list check or a hash" (the exact misfire that produced
the false Chrome-window denials) and instead means "read the same fresh world / the committed git
fact afresh; a positive fresh observation defeats an absence inference; an unresolved contradiction
is `unwitnessed`, never `denied`."

---

## 5. The genome-vs-phenotype fix (closes the original self-heal goal)

Independent of git, the original goal ("fix your own observation methods and prove them") cannot
close while the actor cannot invoke the eyes. Minimal, subtraction-shaped, non-caging fix:

- **Expose `observe` in the actor namespace.** In `build(...)` (~line 1602) add `observe=d.observe`
  to the actor's `SimpleNamespace`. One key. The actor can then edit the observation source, call
  `observe()` in the same turn, inspect the returned dict, and print proof the witness can
  corroborate. It does not cage (the organism could already rewrite the source; this only lets it
  *test*) and it fails hard (a broken edit raises into evidence). The no-GUI hand must gain a
  matching `observe` that raises the honest "no GUI on this host" like the other methods.
- **Document the true `action_index` schema** in the always-visible actor preamble, stated
  correctly this time: `action_index` is `dict[short_id -> {name, role, class_name, automation_id,
  rect, px, py, owner_hwnd, action_key, ...}]`. A `find()` helper, if added, must iterate
  `.values()`, not index a list.

---

## 6. Housekeeping subtractions

- **Prune the ~87 empty `developer_feedback` sentinels** once. The whitespace guard in
  `append_developer_feedback` (`if not feedback.strip(): return`) already prevents new ones; the
  existing dead entries are legacy and pure token cost. One-time removal, committed.
- Keep the developer_feedback *content* the operator wants preserved; remove only the empty
  `{"faculty":""}` rows.

---

## 7. Verification protocol (what "test" means here)

Default, free, safe smoke test — validates that the whole body loads and the prompt assembles,
**before any model call or actor code runs** (confirmed from `turn()`: the `--dry` branch prints
the assembled prompt and returns):

```
# from the Windows host, GUI present:
powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; <launch> --dry"
# on a screenless validation, add --no-gui to skip the live scan:
powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; <launch> --no-gui --dry"
```

Known flags (verified in the engine): `--dry`, `--once`, `--inject <file>`, `--mode
<xai|lmstudio|acp|file_proxy>`, `--reset`, `--no-gui`. `--dry` exercises: engine execs → `config`
JSON parses → `capabilities` execs/loads (a syntax error here raises) → `refresh_environment` →
prompt assembled and printed. That is our free syntax/load gate for `config` + `capabilities` +
`engine`. `reset.py` is only exercised by `--reset`; validate reset changes against a throwaway
copy, never the live board.

`<launch>` = the operator's bootstrap that reads the `## engine` fence and execs it with
`BOARD`/`ARGV` set. **The exact bootstrap invocation must be confirmed with the operator** (no
launcher file is tracked in the repo; only `endgame.md`, `.gitattributes`, `.gitignore` are
tracked).

Escalation: if `--dry` cannot prove a change (anything requiring a live model turn or a real GUI
effect — e.g. proving `observe()` emits lean dicts at runtime), **stop and ask the operator for
permission for a real run.** Do not build a test suite.

---

## 8. Phased implementation plan (each phase: small, reversible, one commit)

Ordering is deliberate: cheap high-certainty body fixes first, then the git substrate, then the
prove-it run.

- **Phase 1 — anti-hash law + witness realignment (data only).** Amend `shared_prompt_prefix`
  (§4) and the verify prompt. Validate with `--dry` (config still parses, prompt assembles).
  Commit: `feat(prompt): forbid hashing live state as proof; realign witness to fresh/gitfact`.
- **Phase 2 — expose observe + correct schema doc (capabilities/prompt).** §5. Validate with
  `--dry` (capabilities execs; `build` still loads). Commit: `feat(actor): expose observe to close
  the genome/phenotype proof gap; document real action_index schema`.
- **Phase 3 — prune dead feedback (memory only).** §6. `--dry`. Commit: `chore: prune empty
  developer_feedback sentinels`.
- **Phase 4 — git substrate, Path A (engine + capabilities).** Implement §3.2/§3.3-A: ensure
  `.self/` repo on launch, author the pre-commit compile hook, route section self-edits through
  `git apply --check` + hook-gated commit, write gated content back to `endgame.md`. Reuse the
  engine's existing subprocess + path-resolution patterns; add no fallback. Validate with `--dry`,
  then request operator permission for a real `--once` turn that performs one real gated commit.
  Commit: `feat(engine): git-backed self-modification sandbox (.self repo, apply-or-reject, compile
  hook)`.
- **Phase 5 — prove the original goal in a real run (operator-gated).** With observe exposed and
  git patching in place, run a real life and confirm the witness accepts a *runtime* observation
  improvement (lean, stable, lower token). Only after this is proven, consider promoting to Path B
  and state the legible-vs-learning-body trade aloud first.

Do not begin Phase 4/5 without the operator's go for the real run.

---

## 9. Open decisions requiring a human ruling

1. **Path A vs Path B** for one-source-of-truth (§3.3). Default: A now, B later.
2. **Confirm the exact bootstrap launch command** (§7) so validation is real.
3. Approve the `.self/` directory name (or supply a preferred one).

---

## 10. Handover prompt (adopt verbatim next session)

> You are a ruthless, high-agency systems architect on **endgame-ai**, a stateless self-modifying
> Windows-desktop organism that is a single Markdown document (`endgame.md`) turning a wheel of
> execute → verify → recover over a blackboard. Root:
> `/mnt/c/Users/ewojgab/Downloads/endgame-ai` (WSL2). Run git and any real system run through
> `powershell.exe` on Windows 11; edit files from the Linux mount. Laws: fail hard, never cage the
> organism, subtraction over addition, one source of truth, honesty by structure, atemporal.
> Deductive reasoning from live code only. Commits are the fallback — commit often with precise
> messages. Validate with `--dry` (optionally `--no-gui`); for anything needing a real GUI/model
> turn, **ask permission first**. Do not build test suites.
>
> The forensic work is done and lives in `PLAN.md`; the RUN_* files are gone. Established at 100%
> confidence: (1) the organism truly self-evolved for 7 witnessed turns editing its own body; (2)
> it died on a triple-quote quine in a self-rewrite sidecar; (3) the deep cause is that the actor
> can edit its genome but cannot invoke `observe()` to test its phenotype, so the witness rightly
> rejected source-text presence as runtime proof; (4) the witness has an invalid urge to prove
> change by hashing dynamic state (the mutating body, the flickering screen) — hashing moving state
> proves nothing.
>
> Approved direction (operator has ruled): (a) add a shared-prompt commandment forbidding hashing
> live state as proof, while noting git commit ids of frozen snapshots are lawful history; (b) give
> the organism its own git in a nested `.self/` repo (no collision with the outer `.git`; outer
> `.gitignore` already ignores it) so self-modification is patch-apply-or-reject with a fail-hard
> pre-commit compile hook and branches as a free database — the zero-dependency law is amended to
> permit git; (c) expose `observe` in the actor namespace and document the real `action_index`
> schema (`dict[short_id -> {...}]`, NOT list[dict]); (d) prune the ~87 empty developer_feedback
> sentinels. Execute Phases 1–3 (cheap, data/capabilities, `--dry`-validated, each its own commit),
> then Phase 4 git substrate (Path A: `endgame.md` stays authority, `.self/` is a gated sandbox),
> then request permission for the Phase 5 real run. Confirm the exact bootstrap launch command with
> the operator before the first real run. Read `PLAN.md` then the live `endgame.md` sections
> `config` (shared_prompt_prefix, stages/verify prompt), `engine` (`build`, `turn`, `run_exec`,
> `refresh_environment`, `factory_reset`), `capabilities` (`observe`, `_render`, `build`,
> `environment`, `_no_gui_hand`) before editing. Where this file and the live code disagree, the
> code wins.

---

*Verified line references are against the `endgame.md` state read on 2026-07-24; confirm live
before editing, as the body may have moved.*
