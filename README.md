# endgame-ai

A local desktop organism. Python is the mechanical body (mouse, keyboard, subprocess, UIA
observation), LLM transports are the interchangeable mind, and `wiring.json` is the circuit
diagram: a fixed topology of organs routes one signal per node through
observe → plan → act → verify → recover. The organism can generate and run arbitrary code and
drive real input — this is what makes self-evolution possible, and what makes discipline about
observation quality, prompt shape, code size, and failure bounds non-optional.

This README is a **live correction plan**, kept in sync with the code. Every claim below was
cross-referenced against the source and `wiring.json` at last edit. Sections marked DONE are
committed and smoke-tested; open items state *what it is*, then **Why** and **Why not / cost**.

## Governing constraints (why the code looks the way it does)

- **Self-evolution sends the organism its own source.** `node_self_modify` ships `git_context`
  + `workspace_manifest` (the checked-out repo) to the brain. Every line of code is tokens the
  self-modifier must read and reason over. So: **fewer lines and fewer tokens is a first-class
  functional requirement**, not cosmetics.
- **No comments, no docstrings, anywhere.** They are pure token cost in the self-modify payload
  and add nothing a symbol name cannot. Enforced across all `.py`.
- **No fallbacks, no near-dead code.** Fail hard and delete dead branches. Git (local + remote,
  user `ewojgab`) is the backup; there is no reason to keep a disabled path "just in case".
- **Unify and reuse over add.** Prefer OOP consolidation (state held once, one contract) and
  modern Python 3.13 that expresses more per token over new files or repeated plumbing.
- **Whole-screen only.** The organism has no focus/foreground concept (see Section 1).

**Measured now:** **4194 LOC across 22 `.py` files** — `core_observation.py` 1018,
`core_nodes.py` 699, `core_brain.py` 671, `core_organism.py` 260, `core_desktop.py` 215. (Was
4540 before the comment strip + focus removal.)

---

## How it runs (minimum operator knowledge)

```powershell
python core_organism.py --reset --max-ticks 5 "Open Notepad and write hello"   # fresh, staged
python core_organism.py --max-ticks 3                                           # resume +3 ticks
python -c "import core_stop_check as s; s.request_stop('halt')"                 # cooperative stop
```

- One completed node = one `tick`. On resume, `--max-ticks N` means N *additional* ticks.
- Transport is chosen by `wiring.json` `model.transport` (currently `transport_file_proxy`).
  Fail-hard: no silent fallback.
- Boot: `node_observe` (full whole-screen UIA scan) → planner → scheduler → observe → execute →
  verify → (reflect / self_modify) → satisfied → halt. All 10 nodes reachable; no dangling edges.
- Runtime artifacts are flat `runtime_*` files, all gitignored. `runtime_request.json` /
  `runtime_response.json` are the file_proxy brain channel.

**Transports are NOT unified, and should not be.** `transport_xai` posts to `/v1/responses`
(`input`, `text.format`, `reasoning.effort` = `none|low|medium|high`, `prompt_cache_key`).
`transport_openai` posts to `/v1/chat/completions` (`messages`, `response_format`, honors
`max_output_tokens` as `max_tokens`). `transport_opencode` shells a CLI. `transport_file_proxy`
writes/polls files. `transport_browser_ai` is an intentional fail-hard stub. Each owns its
request shape by design; `core_brain.think()` is the only unification point.

---

## Section 0 — OOP migration — DONE (committed, smoke-tested)

`Desktop`, `BaseNode`, `UiaVariant`, and `UiaScanner` are real classes with no leftover
pass-through scaffolding.

- **0.1/0.2 — Desktop delegation collapsed** (`d293234`). Dead `core_nodes` ctx-ignoring
  wrappers and per-method module delegators removed; callers use `get_desktop().<method>()`.
- **0.3 — `BaseNode` generalized and adopted** (`5a51b3a`). `build_payload`/`evidence`/
  `request_config` hooks + shared `think()`; planner, verify, reflect, frame_action, execute are
  subclasses. One record / one signal / one patch enforced in one place.
- **0.4a — `UiaVariant`** (`0e8b1ed`); **0.4b — `UiaScanner`** (`05c185b`). Harvest pipeline
  folded into one class holding scan state as `self.*`; `gather()` is a thin delegate to
  `UiaScanner(...).scan()`.
- **Comment/docstring strip** (`bf172c5`): all 22 `.py`, −161 LOC of pure self-modify token cost.

**Deliberately kept:** the per-element `try/except` in harvest — a single inaccessible/transient
UI element is skipped, not fatal. This is resilience; the scan still fails hard if `automation`
or screen metrics are unavailable.

---

## Section 1 — Observation: focus removed, whole-screen model — DONE

### 1.1–1.3 — focus machinery deleted (`dd594a1`, −175 LOC)

Root cause of "just-launched Notepad missing from the tree": focus was load-bearing and the
focused-window concept itself discriminated against non-foreground windows. `filter_gather`
ranked `keyboard_focus` first, gated survival on `require_interactive or keyboard_focus`, tagged
`[FOCUSED]`, and computed `focused_window_id`; `get_focused_title()` did COM round-trips per
tick; `click_node` force-`SetForegroundWindow` before every click, mutating desktop state
mid-plan.

Resolution: **no focus concept anywhere.** One flat whole-screen scan; every window and element
is in one tree, ranked by content and on-screen position. Removed the `keyboard_focus` field +
property reads, the focus rank, the survival gate, `[FOCUSED]`, `focused_window_id`, all
`focused_title` plumbing (observe/bus/brain/self_modify), `Desktop.focus_window`/
`get_focused_title`/`_get_active_window`/`_get_window_title`/`clear_focus_cache`, the
focus-before-click, the focus capability helpers, and execute's `body_delta`. Prompts rewritten
to the focus-free whole-screen contract.

Tested: launch Notepad → observe → present in tree (previously absent); full
observe→plan→execute→verify loop runs. Tree 7535→7525 bytes, 124 nodes, scan 4.47→4.39s.

### 1.4 — R2 low-discrepancy probe order (`e596333`, `24a584b`)

The residual late-window miss was an ordering artifact: the old sinusoidal sweep visited probes
strictly top-to-bottom, so coverage correlated with elapsed time — a window appearing mid-scan
in an already-passed region got no more probes that tick. Replaced with an **R2 low-discrepancy
sequence** (Roberts' generalized golden ratio, plastic constant g≈1.32472, increments 1/g and
1/g²): every prefix is near-uniform over the whole screen, so the final probes span the entire
desktop. Grid-cell dedup keeps `step_px` density. Raster/sinusoidal fallback fully deleted — R2
is the only path (no dead branch, no `pattern` config).

Proven (1920×1080): last 20% of probes hit all four quadrants (7/8/9/10) vs the old sweep's
bottom-two-only; all quadrants covered after 5% of the scan. Notepad launched ~1s *into* the
scan was captured in that same scan. Scan 4.39→3.94s (the `stale_merges` early-stop now means
true saturation, not a top-down artifact — which also makes it safe).

---

## Open work (verified against current code)

### 2 — Phantom LLM contract for mechanical nodes (low risk)
`core_brain._RECORD_DATA_SCHEMAS` still defines `schedule` and `satisfied`, and `wiring.json`
has prompts for them, yet `node_scheduler`/`node_satisfied` never call the brain (verified: no
`think`/`brain` reference in either). Delete both schemas and both prompts.
**Why:** the declarative layer should describe only paths that execute; a phantom schema is
tokens and confusion for the self-modify organ.
**Why not:** none material — if scheduling ever becomes LLM-driven it is re-added with its node.
*(Section 2.1 "dead `transport_grok_cli`" is already resolved: `transport_config` is empty.)*
*(Section 3.1/3.2 "`default_effort_map` / `global.reasoning_enabled`" already deleted in
`8c6f2ba`; per-organ tuning is single-sourced in `wiring.model.organs`.)*

### 3 — Stable-prefix / cache posture (decision, per transport)
`StablePrefix` renders the checked-out source as a fixed leading block for provider caching but
is `enabled:false, include_in_request:false`. For a paid large-context provider (xai) a stable
prefix + `prompt_cache_key` is real money saved on repeated ticks; for a local 4B it is pure
context bloat. Make it a per-transport switch (on for xai, off for local), or delete the machinery
if we commit to local-only — do not leave a disabled subsystem sitting in `core_brain`.
**Why:** either it earns cache hits or it is dead weight in the largest core module.
**Why not:** deleting it forecloses cheap caching on paid providers, so decide, do not drift.

### 4 — Failure circuit breaker (highest topology risk)
`bus.update_failure_streak` tracks a per-signature `count`, and `node_reflect` uses
`count >= 2` only to upgrade `retry/replan` → `frame`; it **never forces `give_up`**. A failing
self-modify can loop escalate → self_modify → error → reflect → escalate, bounded only by
`--max-ticks`. Force `give_up` after a bounded streak on the *same* failure signature (already
computed). Optionally gate `self_modify` to a stronger transport (degrade to
"propose-don't-apply" when only a local model is available).
**Why:** an organism that rewrites itself needs an internal stop, or a weak patch loop burns
brain calls and thrashes the repo.
**Why not:** a breaker that trips too early kills legitimate multi-attempt recovery — trip only
on the same signature, not any failure.

### 5 — Token / LOC reduction pass on self-modify payload (self-evolution lever)
The self-modify brain receives the whole repo (`git_context` + `workspace_manifest`). Direct
levers: keep cutting LOC via OOP unification (the remaining thin builders across the `node_*.py`
files and the two large cores), and shrink what is *sent* — send only the files the diagnosis
implicates rather than the full manifest, and prefer 3.13 constructs that say more per token.
**Why:** self-modify quality scales inversely with how many tokens of its own code it must wade
through; this is the compounding constraint.
**Why not:** over-trimming the payload can hide the file that needs changing — implicate by
evidence, never blind-truncate.

### 6 — Minimal desktop-free test harness (readiness gap)
No test harness exists; correctness is verified by running the organism. The bus contract,
topology wiring, `filter_gather` output shape, and **R2 prefix-uniformity** are all testable
without a live desktop.
**Why:** every core refactor is risky with nothing to catch a regression; these are cheap and
CI-able.
**Why not:** UIA scan + real actuation still need Windows, so leave those as manual smoke tests.

---

## Recommended order (safety × payoff)

1. **Section 2** phantom `schedule`/`satisfied` schemas + prompts — quick clarity, token cut.
2. **Section 4** failure circuit breaker (+ optional self_modify gating) — highest risk today.
3. **Section 5** self-modify payload/LOC reduction — the self-evolution compounding lever.
4. **Section 3** stable-prefix posture decision (keep-per-transport or delete).
5. **Section 6** desktop-free contract/topology/filter/R2 tests.

**Invariant for every step:** re-run the observe→execute smoke test (open Notepad) *including
the observer* before committing. Must-not-regress behaviors: end-to-end file_proxy control,
resume/tick control, cooperative stop, fail-hard routing (missing transport/edge/
`fresh_observation` all raise → `node_error`), and self-evolution guardrails (compile + JSON
validation before and after write).

---

## Appendix — file_proxy operating model

file_proxy writes `runtime_request.json` and polls `runtime_response.json`; the coding agent
that answers those files IS the organism's brain. Two personas:
- **Mode A (brain):** knows ONLY the request file, answers with one typed record, and never works
  around a blocker outside the protocol — if the body cannot do it, return `CANNOT` / `give_up`.
- **Mode B (operator):** reviews and tunes the SYSTEM (prompts/wiring/code), never the loop.
Approval gate: Mode A writes `runtime_response_proposal.json`; Mode B promotes it to
`runtime_response.json` (the only file the organism polls).

**Future (NOT built until requested): dual-agent file_proxy** — a cheap/local brain writes
response proposals; a stronger model approves or rejects them before consumption. Composes with
the propose-don't-apply self_modify idea in Section 4.

**Environment.** WSL2 on Windows 11; drive Windows via `powershell.exe`. Repo
`C:\Users\ewojgab\Downloads\endgame-ai` (WSL `/mnt/c/Users/ewojgab/Downloads/endgame-ai`).
Windows Python `"C:\Program Files\Python313\python.exe"`. Read `runtime_state.json` with
`encoding="utf-8"`. Run the organism in the background so the blocking file_proxy poll can be
serviced. Never commit API keys or sensitive data.
