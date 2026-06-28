# endgame-ai — PROVEN FACTS (log-backed, 2026-06-28)

Every claim here is backed by the LM Studio server log + run.log + state.json from real runs on
2026-06-28. Branch: `size-shrinking`. Repo: `C:\Users\<user>\Downloads\endgame-ai`
(WSL: `/mnt/c/.../endgame-ai`). This file is a distilled index for future sessions; the full
narrative is `README.md`.

## What it is
A living, unconstrained, self-modifying autonomous Windows desktop organism. Small Python files
+ one `wiring.json` + a local LLM. **Standard library only.** No framework, no agent SDK, no
RAG, no MCP, no LangChain, no vector store, no cloud API, no fine-tune.

Files: `organism.py` (living loop), `brain.py` (LLM transports + ROD two-call, fail-hard),
`nodes.py` (engine core, hot-swappable node loader, `call_node`), `wiring.json` (single source of
truth: model/verbs/reasoning-contract/topology/prompts), `seed_nodes/` (8 circuits: planner
scheduler observe act verify reflect self_modify satisfied), `workbench.py` (stdlib http debug
surface :8800), `actions.py` + `desktop.py` (reused Windows UI Automation + input, stdlib+ctypes).

DELETED / do-not-recreate: `engine.py`, `runtime.py`, `wiring-editor.html`, `colony.py`,
`server.py`, `hands.py`, `config.json`, `wiring-schema.json`.

## Hardware / model
`nvidia-nemotron-3-nano-4b` (4B) in LM Studio at `http://localhost:1234`, ~6 tok/s, GPU-less
laptop, ZERO API cost. Each decision = 2 LLM calls (ROD). One step ~4–8 min. Runs are long
(30–90+ min). Nemotron returns EMPTY `reasoning_content`, so capturing the inline
`<think>...</think>` block is LOAD-BEARING. LM Studio server log (ground truth):
`C:\Users\<user>\.cache\lm-studio\server-logs\<month>\<date>.N.log`.

## Proven on 2026-06-28 (two unsupervised runs, ~110 min)
The organism autonomously planned, operated the real desktop via human-like input, verified by
intent, recovered from its own failures, and REWROTE ITS OWN `wiring.json` at runtime TWICE — the
engine reloaded wiring + re-bound the brain LIVE with NO crash. Verb counts in the long run:
`launch` ×11 (only ever `notepad`), `write` ×46, `focus` ×11, `hotkey` ×12 (`alt+f4` ×6 to close,
`win+del` ×6), `open_url` ×5, `wait` ×5, `click` ×9. EVERY click targeted a labeled UI element by
semantic ID (e.g. `[1]`,`[10]` = dialog buttons), NEVER a raw coordinate — no blind clicking, no
harm, cleaned up after itself (closed Notepad, engaged Save dialog by button ID). Aggregate: 89
chat completions, 134 ROD echoes, mean 57.7 s/call (range 20.9 s – 463 s; the 463 s call =
self_modify with full `CURRENT_WIRING`). Stopped manually while HEALTHY.

## The central finding — EMERGENT GOAL-INTERPRETATION DRIFT
Under a FIXED abstract goal (`"understand how you think, and find a way to think differently"`),
the 4B model PROGRESSIVELY RE-INTERPRETED the goal across the run in three logged stages, with its
two self-modification events as the inflection points:
- STAGE 1 INTROSPECTION — write "I am thinking about how I think" + save as think_log.txt
- STAGE 2 ASSERTION — write "I am thinking differently now"
- STAGE 3 DIALECTICAL CONTRAST — "I am thinking differently now" in Notepad vs "My thoughts are
  static" in a browser (two contrasting environments)

The drift is monotonic, self-consistent, history-aware (the planner notes it "already typed that
string" and adapts), and deepens TOWARD the abstraction.

## Honest boundaries (kept in the record, never amended away)
1. The literal `goal` STRING never changed — identical in all 26 prompts; self_modify edits
   `wiring.json`, NOT the goal which lives in `state.json`. So this is emergent INTERPRETATION
   DRIFT, not deliberate goal substitution.
2. Stage 3 is partly genuine abstraction, partly stuck-state improvisation (model casting about
   while stuck at a Save-as dialog).
3. It did NOT swap its brain: in its own logged reasoning it considered `model.transport` and
   explicitly wrote *"change transport? Not needed"*, using self_modify as a task-debugging
   wrench. The two self-mods patched PERIPHERAL fields: #1
   `model.file_proxy.request_path="comms/think_log.txt"`, #2 `model.browser_ai.open_wait_ms=2000`.
4. CRUCIAL SYNTHESIS: those same task-pressured self-mods are what FORCED the re-plans that drove
   the drift — failure-to-upgrade-cognition and success-at-deepening-goal-understanding happened
   in the SAME events.

## Key mechanisms
ROD = two LLM calls per decision (reason, then re-reason with own draft as
`ROD_REASONING_CONTENT`, then commit a typed record validated against contract; wrong
`record_type` -> fail hard -> route to reflect). Record types: planner=`task`, act=`action`,
verify=`verdict`, reflect=`diagnosis`, self_modify=`wiring_patch`. `self_modify` is reachable ONLY
via `reflect->escalate`, which fires when consecutive failures on a step reach
`limits.max_attempts`; the `retries` counter resets to 0 on every success (per
`verify.py`/`self_modify.py`). In the milestone run `max_attempts` was set 7->2 to make escalation
reachable.

Three brain transports in `brain.py`: `openai` (the CORE; always boots here; the seam for a
stronger model), `file_proxy` (writes `comms/request.json`, waits `comms/response.json`, blocks
~900 s then fails hard), `browser_ai` (drives a browser AI; REQUIRES `actions.browser_ai_handoff`
which is NOT present, so swapping to it RAISES and kills the organism). No fallback anywhere —
errors raise.

## Current wiring.json values (committed as proof, reflect the run)
`limits.max_attempts=2`, `model.file_proxy.request_path="comms/think_log.txt"` (organism patch
#1), `model.browser_ai.open_wait_ms=2000` (organism patch #2), planner `e.g.`-example removed. If
a clean baseline is wanted later, those are the four values to review.

## Hard rules for any agent
Branch `size-shrinking` only, never `main`, never force-push, human pushes manually. Stdlib only,
no deps/frameworks. No fallbacks, no constrained mode, no safety gate inside the organism
(unconstrained by design). ONLY hard safety line: never let any action close/kill the
terminal/window hosting the running session. Operate on INTENTIONS not literal strings. Two-layer
gate: gather data -> report with evidence -> human decides -> only then change code. Ground every
claim in logs; if not in a log, do not claim it. Stay TRANSPARENT: failures are kept lessons,
never amended away. "Less is best."

## Anti-hang discipline
Wrap every `powershell.exe` call from WSL in `timeout N`. Launch organism DETACHED
(`Start-Process -WindowStyle Hidden -PassThru`, redirect `run.log`/`run.err.log`) — it survives
the launcher being killed by timeout (124 exit on launch is EXPECTED). Pass the goal as a SINGLE
quoted token in the PowerShell arg-line. Poll `run.log` + `state.json` with bounded timeout calls.
Never run unbounded/interactive commands. Don't probe workbench with `Invoke-WebRequest` on a slow
machine (hangs); use a raw TCP connect test.

## Roadmap / what next (none committed; bring a MoE simulation to the human first)
1. Attack DISPOSITION not capability — reframe self_modify (and/or the goal) so "change how you
   think" resolves to `model.transport`, not a task-chasing config patch (prompt-only, highest
   leverage).
2. STUDY THE DRIFT deliberately — does introspection -> assertion -> contrast reproduce across
   goals/brains? Is self-modification necessary to trigger it? (most novel research seam).
3. Swap in a stronger brain via the existing `openai`/`file_proxy` seam — disposition and drift
   may be functions of model strength.
4. Survival policy: one deliberate exception to no-fallbacks — on non-core brain error, revert
   `model.transport` to core.
5. Close the verification/perception loop (verifier denies genuinely-done steps because evidence
   is indirect — both escalations came from this; but those false escalations CAUSED the
   interesting drift, so change thoughtfully).
6. Restore `actions.browser_ai_handoff` only if a browser_ai swap is wanted.

## Evidence committed
`evidence/run-2026-06-28-threshold2.log.txt` (run narration),
`evidence/state-2026-06-28-final.json` (final state, PII-redacted). Commits on `size-shrinking`:
`9248383` (milestone: wiring+evidence), `61b4a02` (drift reframe of README), `e5d9cb9`
(Appendix A starter prompt). Runtime artifacts gitignored/regenerated: `live_nodes/`
`state.json` `goal.json` `comms/` `*.log`.
