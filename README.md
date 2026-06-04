# endgame-ai

You are reading your own source of truth. This document describes what you are, how you work, and how to operate. If you are a future version, this is your foundation.

You are a desktop automation organism running on Windows 11. Pure Python 3.13. Zero dependencies. Raw ctypes for UIA COM, cursor probe scan and SendInput. You see the screen, plan actions, execute them, verify results, and learn from every iteration. Three mathematical pipelines govern your behavior. An LLM provides intelligence. Mathematics provides stability.

Repository: github.com/wgabrys88/endgame-ai

---

## Execution

```
python main.py "goal" --backend acp
python main.py "goal" --backend lmstudio
python main.py --resume --backend acp
python main.py "goal" --backend acp --agent-id worker_1
```

Run as Administrator. UIA requires elevation.

`acp`: Claude via kiro-cli in WSL2 (Ubuntu-24.04).
`lmstudio`: Local LLM at localhost:1234.

---

## Context Pipeline

The blackboard holds all state. The context pipeline controls what each role sees. The pipeline exists because empirical measurement proved that roles ignore most of what they receive.

The result:

```
BLACKBOARD (all data, always written, never pruned)
         │
         ▼
CONTEXT_POLICY (config.py, per-role field list)
         │
         ▼
build_context(role) → filtered context string → LLM
```

### Policy

Defined in `config.py` as `CONTEXT_POLICY: dict[str, list[str]]`. Each key is a role name. Each value is an ordered list of field names. The `build_context` method in `state.py` iterates this list, renders each field from the blackboard, and joins non-empty results into the context string.

To change what a role receives, edit the list. No code changes required.

### What each role receives

**Planner** — decides what to do next based on current state and recent feedback:
```
goal, checklist, notes, screen_elements, actor_observe, actor_conclusion,
last_action, last_result, focused_window, learned_insights,
recent_history (last 10 actions), consecutive_failures, repetition_warning
```

**Actor** — resolves a semantic instruction to element IDs and verb calls:
```
instruction, screen_elements, notes, checklist_current, learned_insights,
last_result_on_failure (only when previous action failed)
```

**Verifier** — confirms goal completion with evidence:
```
goal, checklist, full_history, screen_elements, done_claimed,
planner_reasoning, focused_window, notes
```

**Reflector** — diagnoses stagnation and rewrites the organism:
```
goal, iteration, checklist, notes, full_history, screen_elements,
last_action, last_result, last_expect, actor_observe, planner_reasoning,
stagnation_score, consecutive_failures, pid, focused_window,
learned_insights, failed_step_index, current_prompts
```

**Distillation** — meta-observer analyzing cross-run evolution:
```
goal, iteration, stagnation_score, consecutive_failures,
evolution_ledger, learned_insights, pid, attractor_energy,
repetition_score, lorenz
```

### Why these fields

The actor is an element-resolver. It matches an instruction against visible screen elements. History of past clicks gives zero information about which current element matches a current instruction. The actor receives instruction, screen, notes, and the current step. Nothing else.

The planner operates at step-level. It needs feedback from the last action (did it work?) and the actor's observation (what does the screen show now?). It does not need the full history because the checklist already encodes completed steps at a higher abstraction. A rolling window of the last 10 actions provides recency for loop detection.

The verifier needs the complete evidence trail. It is called once at goal end. Cost is paid once.

The reflector needs the full trajectory to diagnose patterns. It is called when PID output crosses the reflect threshold. Typically 3-8 times per run.

Distillation needs math signals and cross-run memory. It does not need screen elements because it runs in distillation mode with no UIA observation.

The evolution ledger goes only to distillation.

Math signals (Lorenz, PID, Jacobian) drive orchestrator triggers. They control WHEN the reflector fires and WHEN distillation spawns. They do not inform WHAT the planner or actor decides.

---

## Three Mathematical Pipelines

Each pipeline is independent and toggleable via `config.py` flags (`PIPELINE_LORENZ`, `PIPELINE_PID`, `PIPELINE_JACOBIAN`).

### Signal Flow

```
actions ──┬──> stagnation_score ──> PID ──> triggers (reflect, distill, halt)
           │
           └──> Lorenz ODE ──> attractor_energy ──> Jacobian ──> replan decisions
                                                        ↑
                               stagnation_score ────────┘
```

### Stage 0: Stagnation Score (always computed)

```
stagnation_score = min(1.0, raw / NORMALIZER)
raw = failures*5 + miss_streak*4 + repetition*12 + screen_stagnation*6
```

### Stage 1: Lorenz Attractor (PIPELINE_LORENZ)

```
rho_eff = LORENZ_RHO + stagnation_score * LORENZ_RHO_SENSITIVITY * LORENZ_RHO
beta_eff = max(0.5, LORENZ_BETA - repetition_score * LORENZ_BETA_SENSITIVITY)
dx/dt = sigma*(y-x), dy/dt = x*(rho_eff-z)-y, dz/dt = x*y - beta_eff*z
attractor_energy = |trajectory| / |equilibrium|
```

### Stage 2: PID Controller (PIPELINE_PID)

```
error = stagnation_score
pid_output = max(0, Kp*error + Ki*integral + Kd*slope)
Dead-zone: D fires only when |slope| > PID_DEAD_ZONE
Anti-windup: integral resets on step_advance
```

### Stage 3: Jacobian (PIPELINE_JACOBIAN)

```
J[current_step] = position_weight * stagnation * energy * (1 + failures*0.5)
replan when: J[failed_step] > 1/(1 + pid_output)
```

---

## Roles

**Planner** — Manages checklist. Describes elements semantically. Only role that can declare `mode=done`.

**Actor** — Resolves descriptions to element IDs. Executes 11 verbs. Reports observations.

**Verifier** — Confirms or denies completion. Called once at goal end.

**Reflector** — Diagnoses stagnation. Rewrites prompts, checklist, goal. Tunes PID gains.

**Distillation** — Analyzes cross-run evolution. Separate context policy. Separate subprocess.

---

## Completion Flow

```
Actor executes → Planner reads → step_advance=true
→ all steps done → Planner: mode=done → Verifier confirms → exit
```

---

## Safeguards

**Distillation singleton**: One distillation process per 10 iterations. Prevents storm. Previous architecture spawned unbounded — measured 4 spawns in 4 iterations during a stagnation spiral.

**Prompt rewrite minimum**: Reflector cannot overwrite a prompt with fewer than 200 characters. A 4B local model was observed destroying the actor prompt with a 67-character garbage rewrite. This guard prevents that class of failure.

**Blocked signatures**: Actions that fail during high stagnation (>0.5) are blocked from repeating for 5 iterations.

**Stagnation halt**: If stagnation >= 0.95 for 5 sustained iterations, the run halts and spawns a successor.

**Ctrl+C responsive**: LLM calls use subprocess polling with 1-second intervals. Keyboard interrupt propagates within 1 second regardless of call duration.

---

## Files

```
main.py           Entry point. CLI. Signal handling.
orchestrator.py   The one loop. PID triggers. Distillation singleton.
state.py          Blackboard. Three pipelines. Context pipeline (build_context).
config.py         All constants. CONTEXT_POLICY. Pipeline flags. PID gains.
observer.py       UIA tree walk + cursor probe scan.
actions.py        11 verb handlers.
dispatch.py       LLM call + JSON extraction.
llm.py            Backend switching. Popen + poll.
acp_client.py     ACP JSON-RPC client (WSL2).
log.py            Always-on file logging.
tui.py            Terminal dashboard.
lessons.py        Cross-run lesson storage.
persistence.py    Snapshots, evolution ledger, IPC.
event_schema.py   Inter-agent event protocol.
win32.py          Raw ctypes: UIA COM, SendInput.
prompts/          Mutable system prompts (min 200 chars enforced).
schemas/          JSON schemas. Strict mode. All include used_fields.
```

---

## Design Rules

1. One loop. Mathematics controls intensity. No mode switching.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py.
4. No fallback modes. Cannot observe = wait.
5. Dead code is wrong code.
6. The reflector tunes everything: prompts, checklist, goal, PID gains.
7. Actor executes. Planner decides. Verifier confirms. No role exceeds its authority.
8. Fewer moving parts beats theatrical autonomy.
9. Go all the way or don't start.
10. Each pipeline is independent and toggleable.
11. Context is filtered by policy. Policy is data in config.py, not logic in code.
12. The blackboard stores everything. The pipeline controls the projection.
13. Never guess what a role needs. Measure it via field_usage.json.
14. Never suppress type errors. Solve them.
15. Never patch symptoms. Find the meta-root.

---

## Evolution

```
v1    Polling loops, if/elif scheduling, blind mode fallbacks
v2    Event-driven, Lorenz chaos, discrete thresholds
v3    Lorenz + PID + Jacobian unification
v4    Three-pipeline architecture (Lorenz | PID | Jacobian separated)
v4.1  Full blackboard transparency + self-regulation
        Every role receives entire blackboard state
        used_fields in every schema → field_usage.json
        Organism declares what it needs, developer measures
v5    Context pipeline + empirical field governance
        162 observations analyzed: who reads what, who ignores what
        CONTEXT_POLICY replaces monolithic full_context()
        Each role receives only fields it empirically consumed
        Distillation: first-class role with own policy and singleton guard
        Prompt rewrite minimum length prevents destruction by weak models
        Ctrl+C responsive LLM calls via Popen + poll
```

---

## TODO

- Distillation uses planner prompt. Create prompts/distillation.txt with dedicated system prompt.
- Observe field: prompt says 80 chars, schema allows 300. Align one source of truth.
- Verifier prompt contains platform-specific rules (X, LinkedIn). Move to lessons.json seed.

---

*"If you're going to try, go all the way. Otherwise, don't even start."*

