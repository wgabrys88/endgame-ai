# MoE Behavioral Analysis — endgame-ai Event-Driven Blackboard System

## Experiment Summary

| Metric | Exp1 "emit done" | Exp2 "notepad + describe" |
|--------|-------------------|---------------------------|
| Wall time | 12.0s | 84.9s |
| Iterations | 1 | 7 |
| LLM calls | 2 | 13 |
| Actions | 0 | 7 |
| Actor continuations | 0 | 3 |
| Verifier calls | 1 | 2 |
| Reflector calls | 0 | 0 |
| Efficiency | 0.00 | 0.54 |
| Outcome | COMPLETE | COMPLETE |

## ASCII Event Flow — Experiment 2 (7 iterations)

```
ITER  PHASE           MATH STATE                              EVENT
────  ──────────────  ──────────────────────────────────────  ──────────────
 1    observe         stag=0.00 pid=0.00 lorenz=(8.5,8.5,27) LLM:planner
      planner         mode=direct "Open Run with Win+R"       PLAN:direct
      actor           hotkey win+r → OK                       OK
      actor(cont)     click Open:  → OK                       OK
      actor(cont)     write notepad → OK                      OK
 2    observe         stag=0.00 pid=0.00                      (actor.continue)
      actor(cont)     hotkey return → OK                      OK
 3    observe         stag=0.21 pid=0.41 screen_stag=1        (actor.continue)
      actor           wait 2s (Notepad launching)             OK
 4    observe         stag=0.00 pid=0.02                      (actor.continue)
      actor           conclusion=DONE (Notepad visible)       ACTOR:done
      verifier        verdict=DENIED (hello world not typed)  →consecutive_failures=1
 5    observe         stag=0.00 pid=0.02                      LLM:planner
      planner         "click text editor, type hello world"   PLAN:direct
      actor           click [5] + write "hello world" → OK    OK
 6    observe         stag=0.39 pid=0.63                      LLM:planner
      planner         step_advance=true, "describe screen"    PLAN:direct
      actor           conclusion=DONE (screen described)      ACTOR:done
      verifier        verdict=CONFIRMED                       DONE
```

## Behavioral Findings

### F1: Math Pipeline Is Stabilizing, Not Chaos-Driving

TESTED-IN-THIS-SESSION:
- Lorenz state evolved from (8.5, 8.5, 27) → (11.6, 18.2, 34.0) over 7 iterations
- attractor_energy went 1.0 → 1.36 — modest drift, no wing switch
- PID integral was reset to 0 twice by checklist advances
- Jacobian vector was never logged as affecting a decision

The math computes values that are **only consumed in two places**:
1. `board.should_replan(step_index)` — triggers `_maybe_phase_reflect` when Jacobian impact > 1/(1+pid_output)
2. `pid_output > REFLECT_THRESHOLD` — gates the reflect call

PROBLEM: The Lorenz system was designed to produce controlled chaos for exploration of alternative approaches. Currently:
- It feeds `attractor_energy` into the Jacobian weights
- The Jacobian weights feed into `should_replan`
- `should_replan` only triggers reflection — it does NOT cause re-planning
- The PID is a simple error accumulator on stagnation score

NET EFFECT: Math signals stagnation (converges toward "things are bad") but never injects divergence (never says "try a radically different approach"). The Lorenz chaos attractor is decorative.

### F2: Actor Continuation Is the Critical Efficiency Mechanism

TESTED-IN-THIS-SESSION: 3 out of 7 iterations used actor continuation (skipped planner entirely).
This saved ~3 LLM calls × ~5s = ~15s.

The rule: if last_instruction exists, actor concluded EXPECTED, action succeeded, no failures, no repetition, and screen changed → keep using actor without planner.

BEHAVIORAL PROBLEM: In iteration 5, actor concluded DONE prematurely (only steps 1-2 done, not step 3). The verifier correctly denied it, but this burned an extra iteration. The actor continuation mechanism has no knowledge of the checklist, so it can't determine if the INSTRUCTION is complete vs the OVERALL GOAL.

### F3: Verifier-as-Gate Creates Correct But Expensive Behavior

The verifier denied in iter 5 because the actor claimed DONE having only opened Notepad. The verifier saw empty text in Notepad. This is CORRECT behavior. But it cost:
- 1 LLM call (verifier)
- 1 failure record
- The premature DONE claim caused `_actor_done_should_verify_goal` to trigger verification

PATTERN: Actor gets confused between "instruction DONE" and "whole goal DONE" because `_actor_done_should_verify_goal` returns True when remaining steps ≤ 1. In this case, the checklist was at step 2 but was advanced to step 3 by the DONE signal before verification.

### F4: Dead Code and Redundancy

| Item | Location | Status |
|------|----------|--------|
| `_try_spawn_successor` | orchestrator.py | Dead — empty function |
| `_actionable_sequence` | orchestrator.py | Dead — identity function |
| `_normalize_used_field` | orchestrator.py | Used but unnecessary complexity for log-only data |
| `_log_used_fields` | orchestrator.py | Expensive for zero behavioral impact |
| `LEGEND` constant | observer.py | Empty string, never contributes |
| `_is_runtime_log_line` | observer.py | Terminal filter for self-reference — correct but complex |
| `sixel.py` | root | Only used by TUI visual mode (valid, but large) |
| `CONTRIBUTING.md` | root | Documentation only |
| `ENDGAME-AI-META-CHECKLIST.md` | root | Stale planning doc |
| Dual dispatch system | `actions.spawn_agent_verb` + `orchestrator._spawn_child` | Two code paths for spawning children |

### F5: Stagnation Score Is Screen-Dominated

Formula: `raw = failures*5 + miss*4 + repetition*12 + screen_stag*6`
Normalization: `raw / 28`

In Exp2, iter 3: screen_stagnation=1 → stagnation=0.21 → pid_output=0.41.
In Exp2, iter 6: screen_stagnation=1 → stagnation=0.39 (after prior integral accumulated).

PROBLEM: screen_stagnation increments by 1 every time the semantic hash repeats. But between sending a hotkey and the effect appearing, screen_stagnation ALWAYS goes up by 1. This creates false stagnation signals that accumulate PID integral. The integral was only reset by checklist advances, not by evidence of progress.

### F6: Observer Runs Full Probe+Tree Even When Not Needed

In Exp1 ("emit done"), the observer did a full screen probe despite the goal having nothing to do with the screen. The observer has no knowledge of the goal — it always performs a complete scan. This is ~1s of wall time per iteration.

DESIGN CHOICE: Keep this. The planner needs screen context to decide "there's nothing to do." Without screen data, the planner would hallucinate. The cost is acceptable.

### F7: Artifact Materialization Overhead

Every iteration produces 4+ artifact files (raw, filtered, rendered, semantic). Over a 7-iteration run, this creates 28+ files. The artifact system correctly prevents log bloat but creates filesystem pressure. In long runs, `_prune_agent_artifacts` will clean old entries.

This is not a problem — it's working as designed.

### F8: `used_fields` Logging — Expensive Telemetry with No Behavioral Impact

Every LLM response is checked for which context fields the LLM claims it used. This:
1. Costs ~5 lines of code per role call
2. Produces log entries with no consumer
3. The LLM frequently lies about what it used (actor reports "CURRENT STEP" which doesn't map to `checklist_current`)

PROPOSAL: Remove `used_fields` from schemas, remove `_log_used_fields`. This simplifies schemas and prompts.

## Architecture Problem Sources

### P1: Lorenz Math Produces No Behavioral Fork

The Lorenz attractor should cause the system to **try a different wing** when stuck. Currently:
- `attractor_energy` scales Jacobian vector entries
- Jacobian vector entries scale `should_replan` threshold
- `should_replan` only triggers reflection

MISSING: When Lorenz crosses a wing threshold (e.g., x changes sign), the system should inject a HARD replan — force the planner to abandon current approach and try an alternative. This was the original design intent.

### P2: PID Accumulates Error Without Clear Control Target

PID has: error = stagnation_score, integral clamped at 5.0, derivative on slope.
Output is used as: reflection threshold comparison.

PROBLEM: The PID has no setpoint other than "0 stagnation." It accumulates integral during normal screen transitions (screen_stagnation=1 between actions). The only reset is checklist advance. This means by iteration 6, `pid_integral=0.79` and `pid_output=0.63` despite everything working correctly.

PROPOSAL: PID should only accumulate when there's actual failure evidence, not screen stagnation from normal action latency.

### P3: Premature Actor DONE → Unnecessary Verifier Deny Loop

The `_actor_done_should_verify_goal` function:
```
def _actor_done_should_verify_goal(board) -> bool:
    if not board.plan_steps: return True
    remaining = len(board.plan_steps) - board.plan_step_index - 1
    return remaining <= 1
```

This fires GOAL verification when 1 step remains. But the actor concluded DONE about the INSTRUCTION, not the goal. The system confuses instruction completion with goal completion.

FIX: Only trigger goal verification when plan_step_index == last step AND actor says DONE.

### P4: Dual Child Spawn Paths

`orchestrator._spawn_child` and `actions.spawn_agent_verb` both spawn children. They share 80% of the logic but differ in registration patterns. Unify into a single spawn function.

## Proposed Changes (Priority Order)

1. **Remove dead code**: `_try_spawn_successor`, `_actionable_sequence`, `LEGEND`
2. **Fix premature verification**: Only verify goal when at last checklist step
3. **Remove used_fields telemetry**: From schemas, prompts, and orchestrator
4. **Unify spawn paths**: Single spawn function used by both orchestrator and actor
5. **PID accumulation fix**: Only accumulate on actual failures, not screen lag
6. **Lorenz behavioral fork**: When attractor_energy crosses threshold, force replan with "try different approach" signal
7. **Screen stagnation grace period**: Don't count screen_stagnation during the first N ms after an action (normal latency window)
