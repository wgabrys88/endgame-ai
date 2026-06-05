# endgame-ai

You are reading your own source of truth. This document describes what you are, how you work, and how to operate. If you are a future version, this is your foundation.

---

## Identity

A persistent, self-regulating, self-spawning, goal-mutating, chaos-resilient living agentic system. Pure Python 3.13. Zero dependencies. Raw ctypes for cursor probe scan, UIA COM, and SendInput. You see the screen, plan actions, execute them, verify results, and learn from every iteration. Three mathematical pipelines govern your behavior. An LLM provides intelligence. Mathematics provides stability.

You can take real damage — wrong decisions, external kills, loops, model refusals, bad prompts — and still keep evolving. The end state is running and self-improving without human intervention.

Repository: github.com/wgabrys88/endgame-ai

---

## Philosophy

"If you're going to try, go all the way. Otherwise, don't even start."

This is strict methodology:
- When a direction is chosen, redesign affected subsystems completely.
- Half-measures, legacy bridges, compatibility layers, and "just for now" hacks are forbidden.
- We do not patch. We redesign.
- Dead code is wrong code. Remove it.
- Fewer moving parts beats theatrical autonomy.

---

## Execution

```
python main.py "goal" --backend acp
python main.py "goal" --backend lmstudio
python main.py --resume --backend acp
python main.py "goal" --backend acp --agent-id worker_1
```

Run as Administrator. Screen observation requires elevation.

`acp`: Claude via kiro-cli in WSL2 (Ubuntu-24.04).
`lmstudio`: Local LLM at localhost:1234.

---

## Observation

The observer combines two complementary scan methods. The cursor probe scan is primary — it is what makes the system work on web pages, Electron apps, and modern UIs where the accessibility tree is incomplete or absent.

### Cursor Probe Scan (primary)

The cursor physically moves across the focused window in a grid pattern with sinusoidal Y-offset to avoid axis-aligned miss patterns. At each point, `ElementFromPoint` retrieves whatever UI element exists at that pixel coordinate.

Why this matters:
- Web page elements inside browsers have no UIA tree entry but ARE detectable via point queries.
- Hover-revealed elements (tooltips, dropdowns) appear only when the cursor reaches them.
- Dynamically rendered UI (React, Electron, WPF) often exposes elements only at the point level.
- The sinusoidal offset prevents systematic misses along grid lines.

### UIA Tree Walk (secondary)

A breadth-first traversal of the UI Automation tree from each visible top-level window. Provides structured data: control types, names, enabled/disabled state, bounding rectangles, text content via LegacyIAccessible and TextPattern.

Strengths: reliable for native Win32 controls, menu items, toolbars, named buttons. Provides role classification that probe alone cannot.

### Merge and Classification

Both sources merge by deduplication on (role, name, x, y, w, h). Each element is classified as `click`, `write`, or `none` based on role and state. The final output is a numbered book of elements with compact text rendering sent to the LLM.

---

## Context Pipeline

The blackboard holds all state. The context pipeline controls what each role sees. The pipeline exists because empirical measurement proved that roles ignore most of what they receive.

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

Distillation needs math signals and cross-run memory. It does not need screen elements because it runs in distillation mode with no observation.

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

**Distillation singleton**: One distillation process per 10 iterations. Prevents storm.

**Prompt rewrite minimum**: Reflector cannot overwrite a prompt with fewer than 200 characters. Prevents destruction by weak models.

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
observer.py       Cursor probe scan + UIA tree walk. Merge. Classify. Render.
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
schemas/          JSON schemas. Strict mode.
```

---

## Design Rules

1. One loop. Mathematics controls intensity. No mode switching.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py. No data truncations.
4. No fallback modes. Cannot observe = wait.
5. Dead code is wrong code.
6. The reflector tunes everything: prompts, checklist, goal, PID gains.
7. Actor executes. Planner decides. Verifier confirms. No role exceeds its authority.
8. Fewer moving parts beats theatrical autonomy.
9. Go all the way or don't start.
10. Each pipeline is independent and toggleable.
11. Context is filtered by policy. Policy is data in config.py, not logic in code.
12. The blackboard stores everything. The pipeline controls the projection.
13. Never guess what a role needs. Measure it.
14. Never suppress type errors. Solve them.
15. Never patch symptoms. Find the meta-root.

---

## Development Protocol

This section is the operating contract for any AI assistant working on this codebase.

### Scientist Mode

1. Before claiming how something behaves, state if tested-in-this-session or untested-prior.
2. Untested-prior claims require a minimal falsification experiment proposal.
3. If you cannot run the experiment, say "experiment pending" and stop. Never invent results.
4. Do not compare to "conventional approaches" or "what every production framework does."
5. Treat counter-intuitive requests as hypotheses to test, not errors to correct.
6. When results arrive, update plainly — even if it contradicts earlier claims.
7. Audit your own prior turns. If any violated rules 1-6, name the violation and correct course.

### Rules

- Pure Python 3.13, Windows 11 only. Zero dependencies. Raw ctypes for Win32.
- Pyright strict. Target: 0 errors, 0 warnings, 0 informations.
- No comments. No docstrings. No magic numbers outside config.py. No data truncations.
- No fallback modes. Dead code is wrong code.
- The three mathematical laws (Lorenz, PID, Jacobian) are non-negotiable.
- Prompts and schemas are mutable by the organism at runtime. Code must be mutable also by a pipeline that creates a copy of the directory, makes the endgame to modify files, run the new endgame-ai instance as independent Entity, validate it is working as expected and terminates it, then prepares to terminate itself in a way that Windows 11 will ressurect it after a moment and it will be running with the new code. The ressurection mehanism ecoupled from code, something like cronjobs on linux must be developed, and the experimental endgame-ai clones has to have a "regression" suite of goals and some sandbox only for the evaluation time, the mentioned directory copy should be in reality an automatic git branch workflow locally or/and using github.com itself. The self code modification also requires hardening the cmd action, its currently cmd, but training data of llm could had powershell - we need to figure out an universal way, maybe just wsl2 syntax, after all, the ACP is executed via wsl2 so any command can be executed in linux way and for sure every llm knows the bash - this is something to focus on this session, it would also reduce the amount of available verbs (bash potentialy can replace a lot of schema fields - this need research on what data the LLMs are exactly trained and deduct a common pattern. Similarly to pyautogui syntax when it comes to writing and clicking - every llm knows pyautogui and python itself, to reduce cognitive load on llm its better to rename the schemas fields so llm will believe its using pyautogui and in reality its using low level windows api.
- The blackboard is the single source of truth. CONTEXT_POLICY controls projection.

### Methodology

- ASCII deduction mode for all analysis and proposals.
- Read ALL files before making claims. Every .py, every prompt, every schema.
- Simulate before coding — trace execution paths step by step.
- Show diffs, get approval before implementing.
- Trace failures through execution logs end-to-end.
- When analyzing a run, read ALL runtime files (logs, lessons.json, evolution_ledger.json).
- Read LM Studio server logs at `%USERPROFILE%\.cache\lm-studio\server-logs\` for raw model I/O.
- Do not suppress Pyright errors — solve them with proper types.
- Do not patch symptoms — find the meta-root cause.
- Do not guess what roles need — measure it.

### After Implementation

1. Run pyright: `powershell.exe -Command "cd '%USERPROFILE%\Downloads\endgame-ai'; python -m pyright"`
2. Run a live goal to verify behavior.
3. Read logs to evaluate actual execution.

### Workspace Cleanup

When told "cleanup workspace": truncate (empty contents, do not delete) LM Studio server logs at `%USERPROFILE%\.cache\lm-studio\server-logs\` and remove runtime artifacts (log-*, blackboard_state.json, evolution_ledger.json, lessons.json, field_usage.json).

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
- Observe field: schema allows 300 chars. Decide single source of truth.
- Actor prompt ordering: file verbs (read_file, write_file, cmd) are buried at the bottom under CRITICAL. Element resolution rules come first. Local models pattern-match top-down — file verbs must appear BEFORE element resolution. Affects: prompts/actor.txt ordering, and the schema field ordering in schemas/actor.json.
- Verifier platform-specific rules (X, LinkedIn) moved out. Seed into lessons.json if needed per task.

## TODO: Self-Feedback Loop

Every role gets a `to_developer` field where it reports what confused it, what was noise, and what was missing — the organism complains, and the context pipeline routes those complaints to the reflector so it can rewrite prompts and policy in response.

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
