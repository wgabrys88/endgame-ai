# ENDGAME-AI — PHASE 1 FORENSIC FINDINGS (handoff)

Branch `running-delta` @ 2220b64 (== refs/endgame/known_good). Evidence: 22 source
files (read live), `wiring.json`, `powershell-logs.txt` (24 KB real-machine run),
`request-logs-2026-07-16.jsonl` (114 LLM calls, ~34.6 min, reverse-chronological).
Parser: `tools_parse_requests.py` (reusable; force-added, not in organism allowlist).

Goal under test: "open LM Studio, load Nemotron, play + win a chess game in the chat."
Outcome: **0/114 verdicts reached goal_satisfied.** A 34-minute monotonic loop that
never converged. Root causes below are PROVEN from the logs unless marked INFERENCE.

## A. Anti-loop machinery failed — the river is still frozen (PROVEN)
- Motion each cycle (true order): execute → (deed_denied) observe:reflect → reflect →
  (frame) observe:frame → frame_action → (framed) observe:act → execute …
- reflect chose `frame` **32/32** times, never `retry`. frame_action chose `framed`
  31/32. Commit 0d80cf8 fixed an old loop where reflect chose retry 36/36; the
  "SHALT frame" fix (7aeda28) simply **inverted it into a frame-loop**. One monotonic
  pathology was swapped for its mirror.
- The living-word rows are near-verbatim repeats across turns (rows 4,7,10,14,17,20:
  "Observation confirms button presence at specified location; learned prior key press
  failure requires click alternative…"). The goal-interpretation redesign meant to
  thaw the river did NOT — the rows restate the same stuck belief. Frozen river persists.

## B. failure_streak anti-loop guard is defeated by cosmetic reframing (PROVEN)
- `failure_signature` = sha256(deed.description + done_when). Each frame_action mints a
  slightly reworded description/done_when for the SAME underlying obstacle ("dialog not
  appearing"), so the signature changes → streak resets to 1 every cycle → stuckness
  NEVER becomes visible. The guard keyed to deed identity cannot see an obstacle that
  reflection keeps renaming. It measured cosmetic novelty, not real novelty.

## C. `min_output_tokens` knob is INERT (PROVEN)
- `wiring.model.organs.*` set `min_output_tokens: 1000` on all four organs (commit
  7aeda28, "push richer responses", flagged as operator-accepted fail-hard risk).
- **0/114 requests carried any min-token field** (logged request keys: messages, model,
  maxTokens, responseFormat, temperature, reasoningEffort, include, tools, toolChoice).
  The API neither honored nor rejected it — it was silently dropped. Completion tokens
  stayed 120–455, never near 1000. The knob does nothing; the intended effect never
  occurred. Violates "one source of truth" and "fail hard" (a dead knob that lies).

## D. reflection is silently crippled to LOW effort by the web_search profile (PROVEN)
- `wiring.model.organs.reflection.reasoning.effort = high`. But
  `node_profiles.node_reflect = "web_search"`, and the `web_search` profile sets
  `reasoning.effort = low` + `max_output_tokens: 4096`.
- Merge order in `core_brain.think`: `deep_merge(deep_merge(organ_tuning, profile), override)`
  → the profile OVERRIDES the organ. Log confirms reflection ran **EFFORT_LOW 32/32**
  while execute/verify/frame ran EFFORT_HIGH.
- Reflection — the conscience that must discern the true defect and choose retry-vs-frame,
  the single most consequential decision in the recovery arc — is the LEAST-powered organ.
  And every reflection (32) carried web_search tools unconditionally, though its own prompt
  says consult the web only "when the obstacle dependeth on present public knowledge."
  A tool attachment silently degraded the decisive reasoning faculty. Improperly tuned knob
  with a directly degrading effect.

## E. Verifier false-negative on the real machine (PROVEN from powershell-logs.txt)
- Verifier pronounced: "No LM Studio process found; … no window visible." Meanwhile the
  same machine log shows LM Studio fully starting: API server on port 41343, engine
  runtime llama-server on port 49247, and the Nemotron model LOADED
  (NVIDIA-Nemotron-3-Nano-4B-UD-Q6_K_XL.gguf, "Started loading model").
- The multi-witness law (7aeda28: "process table AND screen AND ports/logs") did NOT
  prevent the false negative. This is exactly the unproven risk the KB flagged. The probe
  looked once, shallowly, and rested a negative verdict on it — the pathology the law names.
  Note the run also opened a Windows "cannot find 'LM'" Run-dialog error: the executor was
  typing "LM" into the Run box (truncated command), never launching the real executable.

## F. Token economy (PROVEN)
- tot_prompt≈333k, tot_reasoning≈187k, tot_completion≈27k over 114 calls → ~547k tokens
  for zero progress. Prompt prefix stays lean (2–4k/call) as the atemporal design intends;
  the waste is entirely the loop, not the prompt.

## G. Faculty distribution (PROVEN)
- execution 33, action_frame 32, reflection 32, verification 17. Roughly half of executions
  raised (→deed_denied→reflect) and half "succeeded" (→verify); EVERY verify denied.

## Cross-representation drift map (wiring ↔ prompt ↔ code ↔ log)
1. wiring organs.reflection.effort=high  ⟂  log EFFORT_LOW  (profile silently wins) — §D
2. wiring min_output_tokens=1000  ⟂  transport body / log (never sent, inert) — §C
3. prompt "SHALT frame"  ⟂  intent (produced a frame-monotone loop) — §A
4. failure_signature=deed-identity  ⟂  frame_action re-wording (streak never climbs) — §B
5. verify multi-witness prompt law  ⟂  real-machine false negative — §E

## NEXT — PHASE 2 (analysis → rebuild proposal, before code)
Reason strictly from §A–§G. Produce a rebuild proposal covering:
1. **Loop cure that actually works.** The retry/frame binary + "SHALT frame" is a false
   dichotomy that oscillates. Options to weigh: (a) make failure_streak key on the
   OBSTACLE/done_when semantics not the reworded description, or hash normalized done_when
   only; (b) give reflection the escalation ladder it needs and stop resetting the streak on
   reframe; (c) fold reflect+frame_action into one recovery faculty (they always fire as a
   pair: 32 reflect→32 frame) — this removes a whole node + an observe instance and kills the
   two-step that launders the streak. Evaluate against task-agnosticism + no-cage.
2. **Kill the profile/effort collision.** Reflection must not be downgraded to low effort by
   a web_search tool attachment. Separate "reasoning effort" from "tool availability," or drop
   the unconditional node_reflect→web_search binding.
3. **Delete the inert min_output_tokens knob** (fails hard-honesty) OR make transport actually
   send + verify it. Prefer deletion (elimination methodology).
4. **Verifier robustness on the real machine** — the architecture forces multi-witness but the
   model skipped it; decide whether this is a prompt-distillation loss or needs a structural
   nudge (without caging).
5. **Executor grounding** — it typed "LM" into Run and never launched the binary; trace whether
   this is a coordinate/observation grounding failure or a prompt failure.
Only after the proposal is chosen: Phase 3 executes the rebuild, then verify by the real wheel
(compile + load_wiring + check_topology, then live run), and reduce net lines.
