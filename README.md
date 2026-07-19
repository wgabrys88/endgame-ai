# endgame-ai — operating knowledge base

This is the durable context for endgame-ai. It exists so any mind, human or machine, arriving at a
fresh session can work correctly from the first move. It is written to be as useful today as in a
hundred days: it carries only DURABLE truth — architecture, laws, methodology — and no volatile
session state (no live SHAs, no "current phase"). The live code on disk is always the final
authority: read it fresh, and where this document and the code disagree, the code wins. This file
explains *how* and *why*; the code is *what is*.

A prior handover once described the system as "four core nodes: frame_action, execute, verify,
reflect." That was false and it poisoned downstream reasoning. The topology below is the verified
truth, read from `wiring.json`. Distrust any source — memory, an old prompt, a stale protocol — that
names `frame_action`, `reflect`, a `scheduler`, or a `barrier`.

---

## What endgame-ai is

A stateless, atemporal, TASK-AGNOSTIC self-modifying LLM organism that drives a real Windows 11
desktop the way a human operator would: it beholds the screen, moves mouse and keyboard, runs
commands, and can author code that rewrites its own body. It is not a program that runs one task and
stops. It is a kernel turning a wheel of wired nodes, whose single wiring document (`wiring.json`) is
the entire definition of the organism.

A goal is supplied from outside in one plain-language sentence and pursued through one repeating
motion. No task is baked into the body — not web work, not file editing, not self-improvement. Every
faculty, prompt, and edge stays general; the goal is read afresh each life.

**The narration IS the memory.** Each atemporal, stateless API call tells the next what was learned,
and nothing else crosses the gap between wakings. There is no hidden store, no scratchpad that
survives a turn. What is not narrated forward is forgotten by design.

---

## True topology (verified against wiring.json — 8 node instances)

`node_observe` is ONE module instanced three ways (`:act` / `:verify` / `:recover`), run afresh before
each thinking faculty so none reasons on a stale view. `node_probe` is a distinct node that beholds
the HOST (not the screen) between the act-observation and the executor.

```
node_guidance      --attend-->        node_observe:act
node_observe:act    --observed-->     node_probe
node_probe          --probed-->       node_execute
node_execute        --done-->         node_observe:verify
node_execute        --deed_denied-->  node_observe:recover
node_observe:verify --observed-->     node_verify
node_observe:recover --observed-->    node_recover
node_recover        --recovered-->    node_guidance
node_verify         --deed_confirmed->node_guidance
node_verify         --deed_denied-->  node_observe:recover
node_verify         --unwitnessed-->  node_observe:verify
node_verify         --halt-->         (life ends)
```

`cycle_start = node_guidance`. The wheel turns until `node_verify` emits `halt`, the body raises
(a broken body ends the life hard), or the process is stopped from outside. There is no internal
turn cap, wall-clock leash, or step counter — and adding one would be caging the organism.

**Record contracts (exactly three; a node's prompt fields must match its contract):**
- `execution` → `{perceived, alternatives, intent, code, goal_interpretation}`
- `verification` → `{code, goal_interpretation}`
- `recovery` → `{lesson, target, strategy, goal_interpretation}`

All three set `additional_properties: false` — a record may carry ONLY its contracted fields, nothing
more. (There is no `risk` field in recovery; if a source says otherwise it is stale.)

`action_frame` is a DATA field (produced by `node_recover`, consumed by `node_execute`, cleared by
execute/verify) — not a node. There is no `frame_action` node, no `reflect` node, no scheduler, no
barrier, no fan-out. Each edge has exactly one target.

A node's allowed output signals are exactly its outgoing topology edges (enforced in `core_bus`). A
node's downstream consumer is read from the topology and its module docstring is injected into the
emitter's prompt as the DOWNSTREAM CONTRACT (`core_brain.downstream_contract` / `_node_docstring`).
Prompts are therefore built dynamically from wiring + topology.

The model-facing text is: `shared_prompt_prefix` + node prompt + `downstream_contract` (the static
system message), then the volatile per-turn tail as the user message. That tail is, in order: the
observation brief, the proven ledger, the goal-interpretation table (the living word), and the
STANDING HOST (`node_probe`'s host facts), each rendered by a `core_bus` function from text held in
`wiring.prompt_templates`.

---

## The node faculties (what each waking does)

- **node_guidance** (`cycle_start`) — pure Python, NO model call: reads and clears an external
  operator-counsel file (a one-way human-to-organism mailbox), placing any counsel into state as
  `latest_counsel`, then emits `attend`. It does not read the goal or living word and sets no intent.
- **node_observe** (`act` / `verify` / `recover`) — pure Python, NO model call (~10 lines): calls
  `desktop.observe()` and emits the fresh desktop tree. Blind and fast by design; it must never be
  made goal-aware.
- **node_probe** — pure Python, NO model call: beholds the HOST — platform, screen, shell tools,
  open windows (visible top-level titles), installed apps — and lays them at the tail of the
  executor's user message so the actor builds on what stands rather than rediscovering the machine.
- **node_execute** — the actor. From the living word, the fresh observation, the standing host, and
  any `action_frame`, it authors ONE Python script and enacts it (`exec` in a capability namespace).
  The language is the only tool; there is no tool menu. A script that raises routes to recovery
  (`deed_denied`), never kills the life.
- **node_verify** — the witness. Authors READ-ONLY code proving a system OTHER than the actor
  produced the effect. Judges by independent effect, never the actor's testimony. Sets
  `deed_confirmed` / `deed_denied` / `unwitnessed` / `halt`.
- **node_recover** — when a deed is denied, distils the lesson and frames the next attempt
  (`action_frame`), commanding recovery to change the KIND of road, not retry the failed one.

---

## Enduring architecture truths (the how and why)

**The Law of Separated Powers (the resolved liar paradox — the epistemic spine).** A claim that
warrants itself proves nothing: a mouth that says "I speak true" offers the assertion and its only
evidence in the same hand, and one hand cannot weigh itself — the liar's paradox. An amnesiac
organism that trusted its own unverified claims would loop on a lie or declare false victory.
endgame-ai resolves this structurally, by separation of powers, not by asking the model to be honest:
the **actor** (`node_execute`) moves the world and may only CLAIM an intent; the **witness**
(`node_verify`) proves an effect wrought by a system OTHER than the actor and is given no hand to move
the world it judges. Testimony — any value the actor computed, printed, read back, or wrote to a file
this life — is void as proof, being the same hand speaking of itself. Truth of "X is done" is
established only by a party that did not and could not do X. This is enforced in code, not just prose:
`build_capability_runtime(ctx)` gives the actor the full `desktop` hand; `build_capability_runtime(ctx,
read_only=True)` gives the witness only `observe`/`expand` + stdlib reads — no `desktop`, no
`consult_model` (so it borrows no other mouth). The `proven_ledger` is appended ONLY by `node_verify`,
never by the actor. The law is stated once in `shared_prompt_prefix` and merely applied downstream.

**Atemporalism and the living word.** The organism keeps no memory of past turns. Each thinking
faculty wakes with the living word (a small set of rows recording what the faculties learned) and,
beneath it, the root goal to consult but not to plan from. The present observation is the one present
truth; where it contradicts a remembered belief, the observation wins. Short on-screen identifiers
(W1, e5) are minted anew each observation and die with it — no bare id may enter any text that
outlives the turn; a thing is named by what it *is*. A prior that must never be relearned belongs
distilled into the prompt, not left in the volatile living word (where it evaporates within a lap —
the signature pathology behind recurring-fault live-locks).

**The witness judges by independent effect.** The executor authors a script and enacts it in one
faculty (no separate runner, no tool menu — the language is the only tool). A separate witness then
judges not by the actor's claim but by independent effect: it authors read-only code proving a system
OTHER than the actor produced the effect. A value the actor computed, printed, read back, OR wrote to
a file this life is testimony, not proof — no verdict may rest on it. The actor cannot see the
witness's tools; the witness cannot move the world. A deed that raises is not death — it is evidence
routed to recovery (the deed-fault seam, `node_execute --deed_denied-->`). A broken body (wiring
won't load, dead faculty) ends the life hard. A witness probe that raises before setting a verdict is
`unwitnessed` — no claim about the world — and returns for a fresh probe, never to recovery.

**The proven ledger and failure streak.** A confirmed deed deposits a proven-done fact (written by
the witness, never the actor) into a channel every faculty reads, so the amnesiac organism does not
redo what already stands. A failure streak counts turns since the last witnessed deed; the higher it
climbs the more recovery must change the KIND of road, never retry a failed one. These are hand-wired
proxies for pressure; the companion survival-drive vision would replace them with an external,
unfakeable energy economy that makes the world itself the verifier.

**Perception — the single-rule, window-first observation.** Observation is ONE rule in
`core_observation.observe()`: enumerate the top-level windows (EnumWindows + GetWindowRect — their
rectangles are ground truth), then for EACH window probe its own rectangle with a golden-ratio grid
and keep only the elements whose `GetAncestor(WindowFromPoint)` owner is THAT window. A pixel where a
nearer window lies answers with the nearer window's element, whose owner fails the test and is
dropped — so what survives per window is exactly its visible, reachable face, and the click-point is
proven by the very probe that found it. Consequences that fall out for free: z-order needs no
computation (front-to-back is EnumWindows order); occlusion is not a computed concept (a covered
element is simply never collected — no `occluded_by` field, no occluder-naming, no separate
hit-resolution pass); a covered window contributes nothing and a visible one contributes its face.
The window enumeration is deliberately LOOSE (visible + non-zero rect, NO title-text filter) so
untitled windows — context menus, dropdowns, tooltips, system-error dialogs, and the taskbar itself —
are seen; a minimum-area floor drops 1x1/sliver junk.

The output the LLM reads is a shallow tree, one line per interactive element (short_id, role, name,
`[active]`/`[action]`/`[disabled]`), with NO pixel coordinates in the text (the body
reads px,py from the `action_index` by short_id; a coordinate on the line is a dead token that only
tempts the actor to nail a stale pixel). Elements deepen on demand via `expand()`, a fresh
independent look that harvests a subtree whole; an optional `char_budget` fails hard if a request is a
glutton, else all is harvested. There is no keyboard-input-target state anywhere — the organism sees a
flat 2D plane of windows and elements, not an input-state machine; a `[disabled]` marker and window
`[active]` are the only element states, and the desktop-icons window is dropped, not scanned.

**What the LLM receives vs what stays Python-side.** `core_bus.observation_brief` sends the model
ONLY `desktop_tree_text` + framed-element detail (the elements named by an `action_frame`) (+ small
metadata). The full `action_index` (keyed
by short_id, carrying px,py,rect,runtime_id and every UIA field) lives in the executor's Python
namespace, NEVER in the prompt. So the true model-facing budget is one quantity: the char length of
`desktop_tree_text`. Any budget belongs at injection-time, not during scan (scan is free Python vs one
model call). Classification of what is actionable is by role sets (`CLICK/WRITE/READ/SCROLL_ROLES`)
in `action_for_role`; a non-actionable role yields `""` and is dropped at the render gate, so no
explicit junk/container list is needed.

**The scriptural register is a deliberate steering technique, not ornament.** KJV commandment prose
pulls the model out of the chatty, confabulation-prone assistant basin into a high-fidelity,
low-variance region — recalled rather than improvised. Keep it. Ghost negations are bloat; state what
*is*, positively, and negate only a real model prior.

**The hot-swappable body.** Every node and the topology itself are ordinary Python/JSON files. The
organism is permitted — and its prompts invite it — to edit them when the true fault lies in its own
code: a node whose name deceives its effect should be mended in the body; `wiring.json` may be
rewritten on the spot; if the organism finds it needs memory or any new faculty it may author one,
and when proven useful that DNA change is committed and pushed. This is self-evolution in the
task-agnostic, code-reusing, defect-removing spirit. There are no limitations placed that the
organism cannot itself rewrite through the wiring — never cage it.

`wiring.json` stays INERT DATA (self-editable by the organism, JSON, LF line endings). It is NOT
converted to executable config: a syntax error in a `.py` config would brick the organism and make
self-rewrite and validation harder. `core_wiring.load_wiring()` validates structure AND coherence
(topology reachable, 8 node instances, single-target edges, three record contracts, six
prompt_templates) and raises on either.

---

## The desktop body (core_desktop.py — the hand)

Two true text-entry roads, deliberately distinct:
- `type_text` synthesizes real keystrokes via SendInput + KEYEVENTF_UNICODE per UTF-16 code unit
  (produces trusted WM_CHAR / DOM insertText events that rich web editors like ProseMirror accept —
  the road for any editor that heeds not a paste).
- `paste_clipboard` sets the clipboard (utf-8) and pastes with Ctrl+V (a wholly other road, for
  content a keystroke cannot bear).

Also: `click(x,y)`, `press_key`, `hotkey`, `scroll`, `set_clipboard`, `open_url(browser, url)`,
`observe()`, `expand()`. The actor targets by short_id from the `action_index` and reads px,py there
— it does not hardcode coordinates.

---

## Operating principles (the working protocol)

1. **Token efficiency is sacred.** Work in explicit phases; before major work, state a phased plan.
   Near the context limit (~60-65%), STOP, summarize findings, write exact next-phase instructions,
   and checkpoint with a commit whose body carries enough to resume. After compaction, retrieve the
   last phase commit bodies (`git log -n N --format='%H%n%B'`) and continue exactly from there.

2. **Full git through `powershell.exe`** (Windows credential manager). Commit each phase with FULL
   reasoning in the body; `--allow-empty` is fine for pure-analysis phases. Commit bodies are
   META-DESCRIPTIVE: what KIND of feature/defect was added, removed, or replaced and WHY, never a
   line-by-line diff — so a future reader resumes with understanding.

3. **`refs/endgame/known_good` policy.** The durable rule is: advance ONLY on a live-run-proven
   state. The STANDING OPERATOR ORDER overrides this: advance on EVERY completed improvement ("we
   always advance refs because we can always move them back"). Comply, but ALWAYS flag an advance made
   ahead of live proof and give the one-command revert
   (`git update-ref refs/endgame/known_good <prev-SHA>`).

4. **Deductive-only from the LIVE code on disk.** The code is final authority; this KB and any
   handover explain how and why but never override the files. Re-read fresh; correct prior findings
   when a full read overturns them. Verify claims explicitly against the files; never assert without
   checking. This applies to subagent reports too — they can hallucinate a line or a config key, so
   confirm every finding on disk before acting on it.

5. **Binary and decisive at 100% confidence** — execute, no permission-seeking or hedging closers.
   But earn the confidence: for any model-facing or behaviour-changing change, prove it moves
   behaviour on a real logged moment before distilling it. Give honest pushback with evidence when an
   instruction fights the architecture; never invent the operator's intent; add no unsolicited safety.

6. **Forensic.** Treat every input as a crime scene; quote exact `file:line`; be violently critical
   of redundancy, contradiction, wasted tokens, and mysticism. Cut fat mercilessly. Prefer REMOVING a
   defect to ADDING machinery — binary essentiality: a thing is essential or removed completely,
   nothing left dangling.

7. **Tool-first for logs.** For large log files, first sample several full untruncated lines,
   reverse-engineer the structure, then write and reuse a dedicated Python parser. Parsers are NOT
   core files: they MAY `pip install` deps (pandas, etc.) and should produce the most complete,
   untruncated, multi-session-useful data possible (tables/timelines, not grep dumps). Core files
   (`core_*`) import stdlib only; executor-authored scripts also stdlib-only. Keep parsers generic and
   improve them in place; never pour raw logs into context.

8. **Two self-critique reasoning loops before any conclusion or change:** first deduce, then challenge
   your own conclusions for contradictions and missed implications. Only then act.

9. **Never cage the organism** — add no limit, counter, branch, delay, or guard it cannot itself
   rewrite through the wiring. Distil each run-lesson to its most general POSITIVE law or keep it out
   of the prompt entirely; prompts trend toward fewer, more general laws, never a new commandment per
   stumble. Fail hard: no fallbacks, no defensive `if/else` edge-case support for features that are
   not wired. Logically sound wiring, not branches.

10. **Architectural freedom.** Authorized to make massive changes — rewrite whole components, nodes,
    topologies, configs — when logic shows it superior to patching. Observation was once rebuilt from
    zero on the single window-first rule and three files deleted; that is the expected mode, not the
    exception.

11. **The genesis MoE panel.** For autonomous investigation, run the "genesis" subagents in PARALLEL
    — a critic, a prompt-engineer, and a Python OOP/dedup/dead-code reviewer. ALWAYS pass them the
    full path `/mnt/c/Users/ewojgab/Downloads/endgame-ai` (they CAN read the mount when given the
    correct absolute path). Never ask them to create or modify files. Demand 100%-confidence reports.
    Deduct after round 1, run a SECOND parallel round, THEN do the final verification yourself
    directly against disk.

---

## Meta-laws (durable)

- **The system's own defects are the substrate of emergent behaviour** — "without these problems
  there will be no emergent behavior; the system can self-diagnose." Do NOT over-cure. A defect the
  organism can itself observe and rewrite is a feature of the self-modifying design. Prefer making
  defects VISIBLE and auditable over hiding them. A run stopped from outside is not a defect in the
  organism — it has no internal leash by design, and none should be added.

- **The operator throws bold, sometimes "crazy" ideas on purpose** and trusts the assistant to
  evaluate them against live code — this trust loop is HOW the organism was built. Evaluate every
  idea seriously; store the not-yet-ripe ones in the reservoir below; never dismiss.

- **Reuse existing code over new architecture.** Do not add comments or docstrings as prose bloat.
  The convention on disk: the ONLY human-language prose is the module-level docstring at the top of
  each `node_*.py` file — because those, and only those, are read at runtime and injected into
  prompts. Everything else that needs saying belongs in `wiring.json` prompt text or in these commit
  bodies. Any prose left in the code is therefore, by its mere presence, known to be load-bearing.

- **Deliberately confusing test conditions are a feature:** the operator pre-opens overlapping
  windows to stress observation. Treat messy multi-window desktops as the real target, not the clean
  fixture.

---

## Project execution methodology (verified)

- **Root:** `/mnt/c/Users/ewojgab/Downloads/endgame-ai` (WSL2 mount). Remote
  `github.com/wgabrys88/endgame-ai.git`. The working branch name is not baked into any code — the
  organism must stay correct regardless of where the folder sits or which branch it lives on.
- **Cross-OS:** all git, pip, and real organism runs go through
  `powershell.exe -NoProfile -Command "cd 'C:\Users\ewojgab\Downloads\endgame-ai'; ..."` from WSL
  (Windows-only credential manager + `XAI_API_KEY`). `comtypes`/UIA are Windows-only, so anything
  importing `core_observation`/`core_desktop` MUST run via `powershell.exe`, not plain WSL python.
  Plain WSL `python3` is fine ONLY for `ast.parse` and `core_wiring.load_wiring()`.
- **Offline gates** (every change; necessary but NEVER sufficient — behavioural truth lives only on
  the real desktop):
  1. `python3 -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('*.py')]"`
  2. `python3 -c "import core_wiring as w; w.load_wiring()"` (validates structure AND topology
     coherence, and raises on either)
  3. import the kernel; run `pyflakes` via the Windows python across touched files.
- **.gitignore is a WHITELIST with CRLF endings:** every new tracked file MUST be added as
  `!filename`; a deleted tracked file must have its `!` line removed. `str_replace` can choke on the
  CRLF — use `sed`. `wiring.json` itself is LF.
- **Live run** (the only real witness): `python core_organism.py "<one-sentence goal>"` on Windows.
  The organism prints nothing and there is no logging in the body; stdout stays empty, stderr carries
  only a crash traceback. To witness a natural end-to-end life without a foreground shell timeout
  truncating it, launch DETACHED and observe from outside:
  ```
  powershell.exe -NoProfile -Command "cd \"$env:USERPROFILE\Downloads\endgame-ai\"; Start-Process -NoNewWindow -PassThru python -ArgumentList 'core_organism.py','THE ROOT GOAL' -RedirectStandardError run.err -RedirectStandardOutput run.out | Select-Object -ExpandProperty Id"
  ```
  Observe by: (a) watching the real DESKTOP — the true progress feed, since the organism drives the
  GUI; (b) optionally following the crash file in a second PowerShell window with
  `Get-Content "$env:USERPROFILE\Downloads\endgame-ai\run.err" -Wait -Tail 20` (empty while healthy);
  (c) `Get-Process python` to see if the life still turns. Stop it with `Stop-Process -Id <PID>`
  (the launch prints the PID). A hard kill corrupts no state — the organism is atemporal and keeps no
  memory — but glance at the screen afterward, as stopping mid-action can leave the desktop
  half-acted.
- **README is the published artifact** (this file, tracked). The KB is distilled INTO it so the
  knowledge survives publicly. Read the live code as ground truth over any prose here.

---

## Forensic checklist (verify, don't trust)

1. A bundle of phases advanced by operator order (not a witnessed run) is NOT live-proven. First task
   after any run: confirm the organism still halts coherently; if not, reset
   `refs/endgame/known_good` toward the last live-proven state.
2. Observation: does the single-rule per-window scan keep the reachable face of each window and drop
   covered elements? Does the taskbar appear as a first-class window with running-app buttons
   clickable? Are context menus / dropdowns (their own top-level windows) caught by the loose
   EnumWindows when actually open?
3. Web/embedded content: does WebView2 / an out-of-process iframe get dropped from its host window
   because its owner_hwnd resolves to a child-process root? If a live browser run shows lost content,
   add a keep-exception. (Open risk.)
4. Text entry: does the actor reach a web text field first-try using `type_text` (real keystrokes)
   without DevTools/JS escalation, and use `paste_clipboard`/`set_clipboard` rather than hand-rolled
   ctypes?
5. Hover-revealed UI: the per-probe cursor move was removed to stop the scan stealing the physical
   mouse. `ElementFromPointBuildCache` and `WindowFromPoint` take an explicit POINT and do not need
   the cursor — but physically moving the cursor could materialize hover-only elements (tab close
   buttons, list-row action buttons). Whether that coverage is actually lost depends on a live A/B
   (scan a hover-heavy app with vs without the cursor move and diff the element counts); the old code
   moved the cursor with NO dwell, so it likely never reliably captured hover UI anyway. If a live run
   shows lost hover elements, the correct fix is a cursor-move WITH a real dwell behind a wiring knob
   (default off), not an unconditional restore.
6. KV-cache layout: static system message (prefix + node prompt + downstream_contract) on top,
   volatile tail below; nothing volatile leaks into the cached prefix. Reasoning happens via the
   native transport (grok, reasoning effort set in `wiring.json`), not a two-pass prompt.
7. Re-confirm topology and the three record contracts against `wiring.json` every session; reject any
   `frame_action`/`reflect`/`scheduler`/"four core nodes"/`risk`-in-recovery claim.

---

## Operator idea reservoir (atemporal — surface when the moment fits, do NOT discard)

Operator-originated design seeds, evaluated against live code but deliberately deferred, not rejected.

1. **Environment in the living word (self-narration)** — JUDGED GOOD, staged as a prompt phase (needs
   a live run to prove). The living word carries goal rows only; the atemporal organism should ALSO
   narrate ENVIRONMENTAL state/change across wakings ("I am verifier, only Notepad visible, a process
   hurting CPU — that changes everything"). The fresh observation gives the static per-turn snapshot;
   the value is narrating CHANGE across wakings. Faculty-prompt work, not a body change. `node_probe`
   already lays standing host facts at the executor tail — a partial down-payment on this.

2. **Goal-river steering the observer's `expand()` + "which window is the work in"** — HELD on the
   task-agnostic law. `node_observe` is pure Python with NO model call; making it goal-aware breaks
   the blind-observer design. Steering already lives right: `expand()` is called BY the executor;
   the window `[active]` marker + `node_probe` open-windows answer "which window." Revisit only if a
   live run shows the executor repeatedly expanding the wrong thing.

3. **Tab-jump observer (experimental alt-topology)** — DEFERRED by the operator's own caution.
   Holding Tab jumps across interactive web elements, but Tab CAN generate actions and an observer
   must never mutate the world. A parallel/linear scan sub-topology someday; not now.

4. **Multiple linear sub-topology of scan + elimination framing** — "everything happens in Python so
   it is fast vs LLM calls; get ALL data first, then eliminate by pattern." Birthed the single-rule
   observation rebuild. Deeper seed still open: scan could fan into several cheap linear Python passes.

5. **Single injection-time char budget + "explosion" scan** — one deterministic tree-char budget
   applied at the moment before injection (front-window-first, visible `[TRIMMED]` marker, never
   silent) to replace count-caps. And the "explosion" scan: deep probes per screen region, depth
   graduated by distance from a focal point. Partially pre-empted: the per-window scan already spends
   probes per window, and the tree may be small enough the budget does not yet bite.

6. **The witness proportional to the deed** — the witness mechanism was built to prove phases of
   long-running tasks; it fires the full read-only-proof faculty even for a single trivial click.
   Not a defect to remove — a correct witness handles cheap deeds cheaply. The fix is making
   verification proportional to the deed, not removing independent verification. Needs design + a
   live run.

7. **Survival-drive / energy economy** — the proven-ledger and failure-streak are hand-wired proxies
   for pressure. The larger vision replaces them with an external, unfakeable energy economy that
   makes the world itself the verifier.

---

## Appendix — the "deed becomes a node" revolution (idea + critique; NOT built)

A candidate future architecture: the organism ships as a SEED TOPOLOGY, and thereafter an executor's
deed is no longer a throwaway script — it is a NEW NODE with its own docstring-prompt, which the
executor WIRES into the graph at connection points it chooses. Six mechanisms, in dependency order:

1. **Deed → node.** Executor authors a node (behavior + docstring-prompt + chosen edges), not a
   script. The atomic act.
2. **Fitness by use.** Each non-core node counts its own goal-advancement over time = fitness. No
   external judge, no commit ceremony. (NOT raw invocation count — that would reward the
   click-click-click loop.)
3. **Pruning.** Low-fitness nodes discarded, high-fitness persist; the graph self-cleans.
4. **Stigmergic routing (the key).** Flow is not a hardcoded edge table but ant-colony pathfinding:
   data walks the graph, reinforces paths that reach the goal, evaporates paths that don't. The
   load-bearing insight — hardcoded edges cannot survive nodes appearing at runtime; weighted
   evaporating paths can.
5. **Backprop-of-structure.** When a new node proves useful, the system may rewire NEIGHBORING nodes
   to accommodate it. DEFER — no convergence guarantee, and the system already oscillates.
6. **Recursion without children.** To "call the whole endgame system" you do NOT spawn a child; you
   wire a SECOND executor in PARALLEL (like resistors in parallel) — flow splits through it. That
   parallel-executor IS a sub-organism, achieved purely by wiring, bounded by the same global budget.

**Unifying principle:** core reuses code, node reuses node, topology reuses itself. Self-similarity at
every level — THAT, not literal fractal-spawning, is the real fractal.

**Hard invariants the revolution must not breach:**
- fail-hard CORE | explore-and-decay PERIPHERY — the boundary must be explicit and un-crossable.
- grown wiring stops being human-legible: a legible body becomes a learning body — name that trade
  before committing to it.
- a node must never gain the power to rewrite the survival criterion.

**Deepest tension:** atemporalism says the body carries only wiring + living word. This idea makes the
WIRING ITSELF the accumulating memory — legal, but the wiring stops being a small human-authored
artifact and becomes a large machine-grown, partly-illegible structure. You are trading a LEGIBLE body
for a LEARNING one.

---

*The code on disk is the final authority. This document is how and why; the code is what is. Read it
fresh, and where they disagree, the code wins.*
