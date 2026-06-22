# endgame-ai — Self-Rewiring Autonomous Desktop Organism

A local Windows PC becomes a living organism. A 4B parameter LLM runs locally
(LM Studio) and drives a closed ROD loop (Reason → Observe → Decide) that can
plan multi-step goals, observe the screen, execute desktop actions, verify
outcomes, reflect on failures, and self-modify its own wiring topology.

This is NOT a react agent. NOT a chatbot with tools. It is a persistent
reasoning loop designed to work for hours or days on complex goals: installing
software, configuring systems, interacting with web services, managing files.
The human provides a goal and walks away.

The endgame vision: any person with a computer can have an autonomous digital
worker. No programming. No cloud. No per-token billing. Local model, local
reasoning, local evolution. When Python is purely mechanical and wiring.json
fully governs behavior, the system becomes model-agnostic — swap in any local
LLM and the organism works.

---

## Architecture

```
Python (server.py, desktop.py, actions.py) = mechanical body.
  Probes screen, executes verbs, validates patches, hot-reloads wiring.
  NEVER interprets tasks semantically. Pure mechanical infrastructure.

prompts/wiring.json = mutable brain.
  Topology (graph nodes + edges + signals), prompts (base + roles),
  guards, limits, observe config, reasoning config, verbs config.
  ALL semantic behavior lives here. This is what self_modify mutates.

Local LLM (via LM Studio at localhost:1234) = judgment.
  Plans, decides actions, verifies, reflects, proposes wiring patches.
  Currently: nvidia-nemotron-3-nano-4b (4B params, Q6, runs on any GPU).
```

---

## The Two-Pass Reasoning Loop (Core — Do Not Remove)

Every LLM node executes:

```
Pass 1: system + user → model produces <think>reasoning</think>content
Pass 2: system + user + reasoning_from_pass_1 + "DECIDE NOW" → final JSON
```

This creates self-critique. Pass 1 is impulse, pass 2 is commitment with
review. Proven: pass 2 caught real bugs that would have caused failures.
The reasoning propagates between nodes (planner → act → verify → reflect)
via the reasoning chain — the organism's memory of WHY.

---

## ROD Loop

```
goal → planner → [scheduler → bus_check → observe → act → verify] loop
                                                         ↓ fail
                                                       reflect → retry | replan | escalate → self_modify
```

Nodes: planner (decompose), observe (screen probe), act (decide+execute),
       verify (confirm/deny), reflect (diagnose), self_modify (evolve wiring)

---

## Observation

Single full-screen hover probe: cursor grid at 70px step (~405 points, ~3s).
SetCursorPos + ElementFromPoint at each point. Captures everything visible
regardless of framework. SCREEN rendered as text with [ID] targets (~4-6KB).
This is the act circuit's sole visual input.

Config in wiring.json `"observe"` section:

```
hover_scan_step_px: 70       (grid density)
render_class_name: false     (suppress CSS class noise)
render_automation_id: true   (keep short UIDs)
render_window_per_element: false (window shown in header only)
desktop_tree_enabled: false  (disabled, model works without)
```

---

## Measured Performance (Ground Truth from LM Studio Log)

```
Generation:       6.14 tok/s (HARDWARE WALL — cannot improve in software)
Prompt eval:      50-170 tok/s (cache-dependent)
Single-step goal: ~3.5 min (planner two-pass + act two-pass + verify preflight)
5-step goal:      ~12 min (with preflight on most steps)
```

Where time goes: 69% generation (hardware), 24% prompt eval, 7% non-LLM.
The ONLY software levers: fewer LLM calls (preflight), fewer output tokens
(tighter prompts), fewer retries (better guards/prompts).

---

## Self-Modify

When retries+replans exhausted: reflect escalates to self_modify.
LLM emits a wiring_patch (validated JSON operation). Python validates
against schema, creates timestamped backup, writes new wiring, hot-reloads.

Operations: `set_observe`, `set_limit`, `set_guard`, `append_role_rule`,
`set_prompt_base`, `set_role`, `set_reasoning`, `add/update/remove node/edge`.

The organism cannot corrupt itself — validation prevents invalid mutations.

---

## Endpoints

```
GET  /health     — status + capabilities
GET  /wiring     — current brain
GET  /state      — persisted run state
GET  /events     — SSE live stream
POST /run        — start autonomous goal
POST /step       — execute one graph node
POST /pause      — pause running goal
POST /resume     — resume from saved state
POST /wiring     — validate + hot-reload wiring (JSON body)
POST /node/{id}  — direct node execution
```

---

## Non-Negotiables

- Python = mechanical. Wiring = semantic. Never cross this boundary.
- Do NOT reintroduce prompt truncation or parse_fallback.
- Do NOT add task-specific or site-specific Python branches.
- Do NOT hide errors with except/pass.
- Do NOT remove or weaken the two-pass reasoning loop.
- Do NOT optimize for trivial goals — the system runs complex multi-day tasks.
- Validate wiring after every mutation. Hot-reload with absolute path.
- Commit every coherent verified batch.
- Changes must be GENERIC — if it names one app/site, it's wrong.

---

## How to Diagnose

The LM Studio server log is GROUND TRUTH:

```
%USERPROFILE%\.cache\lm-studio\server-logs\<year-month>\<date>.log
```

It contains: full request bodies (system + user messages), full responses
(content + reasoning_content + token counts + timing). Map each request
to its pipeline node by matching system prompt role and user content.

Key metrics per call:
- `prompt_tokens`: how large was the input
- `reasoning_tokens`: how much the model thought
- `completion_tokens - reasoning_tokens`: actual output size
- `total_time`: wall clock for that call
- `tg` (tokens generated per second): generation speed

If a goal fails or is slow:
- Read the log, find which node produced wrong output
- If wrong action → fix act prompt in wiring
- If wrong plan → fix planner prompt in wiring
- If wasted verify calls → add preflight pattern in wiring
- If observation missed elements → tune observe config in wiring
- NEVER add task-specific Python code

---

## First Actions (New Session Bootstrap)

1. `git status`, `python -m compileall`, JSON parse check, `/health`
2. Read this README fully — it IS the architecture document
3. Pick a multi-step goal, run it, observe behavior
4. Read LM Studio log for that run — full forensics
5. Identify highest-leverage improvement (usually: more preflight patterns
   or tighter prompts to reduce wasted reasoning)
6. Implement, test with a goal, verify, commit, update README

---
---

# ANALYSIS: KV Cache Optimization

## The Idea

LM Studio (and llama.cpp underneath) caches the KV state of the prompt prefix.
If the system prompt is identical between requests, the prompt eval for that
prefix is essentially free on subsequent calls — only the new/changed user
portion needs fresh computation.

## Current State

```
load_system_prompt() → only base + role text (never state-dependent)
build_user_message() → only dynamic blocks from state
```

System prompt per circuit:
- planner:     base(863) + role(972)  = ~1835 chars ≈ 460 tokens
- act:         base(863) + role(1724) = ~2587 chars ≈ 650 tokens
- verifier:    base(863) + role(974)  = ~1837 chars ≈ 460 tokens
- reflector:   base(863) + role(834)  = ~1697 chars ≈ 425 tokens
- self_modify: base(863) + role(1648) = ~2511 chars ≈ 630 tokens

## Verdict: Already Optimally Structured

```
✓ System prompt = STATIC per circuit (base + role text from wiring.json)
✓ User message = ALL DYNAMIC content (state blocks, screen, history)
✓ Architecture already separates static from dynamic correctly
```

The dominant KV cache win (pass 1 → pass 2 within two-pass loop) is already
captured automatically. Pass 2's prefix is identical to all of pass 1.

## Block Reorder: Marginal KV Gain, Real Attention Gain

Between different calls to the same circuit, the user message diverges
almost immediately (SCREEN changes every observation). KV cache savings
from block reorder: ~0-2 seconds per goal.

However, reordering for **attention quality** is valuable — see next section.

## Quantified Impact

```
                          CURRENT           WITH REORDER
Pass 1→2 (same node):
  Cached prefix:       system+ALL user    system+ALL user   (same!)
  Savings:             ALREADY OPTIMAL    NO CHANGE

Retry (act→act same step):
  Cached prefix:       system only(650)   system+SUBTASK+DONE_WHEN(700)
  Savings:             0                  ~50 tokens ≈ 1s at 50tok/s

Cross-step (act step N → act step N+1):
  Savings:             baseline           NO CHANGE (subtask changes)

TOTAL: <0.3% improvement from KV cache reorder alone.
```

---
---

# ANALYSIS: Attention Quality via Block Ordering

## Transformer Attention Is Not Uniform

```
Token position:   0          500         1000        1500        2000
                  │           │            │           │           │
Attention weight: ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░████████████
                  ▲ high                  ▲ low                   ▲ high
                  │                      │                       │
               "primacy"          "lost middle"            "recency"
```

"Lost in the Middle" (Liu et al. 2023): small models (4B) are MORE
susceptible. Information in the middle of context gets weaker attention.

## Current ACT Block Order (suboptimal)

```
START ──────────────────────────────────────────────────────── END

┌──────────┬──────────┬════════════════════┬──────────┬─────────┬───────┐
│ SUBTASK  │ DONE_WHEN│      SCREEN        │LAST_ERROR│ HISTORY │MEMORY │
│  20 tok  │  15 tok  │   1200-1800 tok    │ 0-50 tok │ 50-400  │0-100  │
└──────────┴──────────┴════════════════════┴──────────┴─────────┴───────┘

★ SCREEN (the PRIMARY decision input, 70% of user tokens) sits in the
  MIDDLE where attention is WEAKEST.
```

## Optimal Block Order

```
START ──────────────────────────────────────────────────────── END

┌──────────┬──────────┬───────┬──────────┬─────────┬════════════════════┐
│ SUBTASK  │ DONE_WHEN│MEMORY │LAST_ERROR│ HISTORY │      SCREEN        │
│  20 tok  │  15 tok  │0-100  │ 0-50 tok │ 50-400  │   1200-1800 tok    │
└──────────┴──────────┴───────┴──────────┴─────────┴════════════════════┘

★ SUBTASK at start = primacy effect (model knows WHAT to do)
★ SCREEN at end = recency effect (model sees WHAT'S ON SCREEN clearly)
★ HISTORY/ERROR in middle = acceptable (context, not primary input)
```

## Expected Reasoning Token Reduction

When SCREEN is in lost middle, the model re-scans context redundantly:

```
# Bad: model confused, re-reads
<think>
The user wants me to click the search bar.
Let me look at the SCREEN... I see elements...
Looking for search bar... [re-reading context]     ← WASTE
I found [3] Edit "Search" which seems right...
Wait, let me check again...                        ← WASTE
Yes, [3] is correct.
</think>

# Good: model clear, decides fast
<think>
The subtask is to click the search bar.
SCREEN shows [3] Edit "Search" — that's the target.
I'll click [3].
</think>
```

Estimated savings: 80-150 fewer reasoning tokens per call.
At 6.14 tok/s: 13-24 seconds saved per LLM call.
For 5-step goal (~10 calls): ~130 seconds (~2 minutes) saved.

**Must be measured via LM Studio logs before/after.**

---
---

# ANALYSIS: Verify Preflight — The #1 Performance Lever

## What Is It?

After act executes actions, the verify node must CONFIRM or DENY
that the step is complete. Normally this costs 2 LLM calls (two-pass):

```
verify pass 1: "did this step succeed?" → reasoning (90-180s)
verify pass 2: reasoning + "DECIDE NOW" → verdict JSON (90-180s)
```

PREFLIGHT = deterministic rules evaluated BEFORE the LLM calls.
If rules can PROVE success or failure structurally → skip LLM entirely.

```
        act finishes
            │
            ▼
   ┌────────────────┐
   │ PREFLIGHT CHECK │ ← Pure rule evaluation, zero LLM, <1ms
   └────────┬───────┘
            │
       ┌────┴────┐
       │         │
  CONFIRMED   DENIED    UNCERTAIN
       │         │         │
       ▼         ▼         ▼
  advance     reflect    LLM verify (two-pass, 100-180s)
  to next     (retry)    only when rules can't decide
  step
```

**SAVINGS PER HIT: 100-180 seconds** (entire two-pass LLM verify eliminated)

## Time Budget Comparison

```
One step WITHOUT preflight: ~204s
  act pass 1:     ~50s
  act pass 2:     ~50s
  execution:      ~4s
  verify pass 1:  ~50s  ← ELIMINATED by preflight
  verify pass 2:  ~50s  ← ELIMINATED by preflight

One step WITH preflight:    ~104s
  SAVINGS: ~100s (49% of step time)
```

## Lever Comparison

```
┌─────────────────────┬──────────────┬─────────────────────────────────┐
│ Lever               │ Savings/goal │ Mechanism                       │
├─────────────────────┼──────────────┼─────────────────────────────────┤
│ 1. Verify preflight │ 100-500s     │ Skip LLM calls entirely        │
│ 2. Block reorder    │ 60-130s      │ Fewer reasoning tokens (maybe) │
│ 3. KV cache order   │ 0-2s         │ Slightly faster prompt eval    │
└─────────────────────┴──────────────┴─────────────────────────────────┘
```

---
---

# IMPLEMENTATION PLAN: Declarative Preflight Rules in Wiring

## Problem Statement

Current preflight patterns are **hardcoded Python** with app-specific checks
("notepad", "chrome", "editor"). This violates two principles:

1. **Python = mechanical** — semantic knowledge shouldn't be in Python
2. **Self-modify can't learn** — patterns are frozen in code

## Target Architecture

```
BEFORE (hardcoded, frozen, task-specific):

  server.py:
    if "notepad" in focused and typed:   ← FROZEN IN PYTHON
        return CONFIRM

AFTER (declarative, learnable, task-agnostic):

  wiring.json "preflights": [
    {
      "id": "write_to_writable_field",
      "verdict": "confirm",
      "match": {
        "outcome_ok": true,
        "done_when_matches": ["written","typed","text","entered"],
        "actions_include_verb": "write",
        "actions_wrote_nonempty": true
      }
    }
  ]

  server.py:
    for rule in WIRING["preflights"]:    ← GENERIC EVALUATOR
        if evaluate_rule(rule, state): return rule["verdict"]

  self_modify can emit:
    {"op":"add_preflight","payload":{...new pattern...}}
```

## Preflight Rule Schema

Each rule is a declarative condition set. ALL conditions must match (AND logic).

### Condition Primitives (what the evaluator can check)

```json
{
  "id": "unique_rule_id",
  "verdict": "confirm | deny",
  "description": "human-readable purpose",
  "match": {
    // ─── Outcome conditions ───
    "outcome_ok": true,              // last_outcome starts with "OK:"
    "outcome_failed": true,          // last_outcome starts with "FAILED" or empty

    // ─── Action chain conditions ───
    "actions_include_verb": "write",         // at least one action has this verb
    "actions_all_verb": "remember",          // ALL actions have this verb
    "actions_sequence": ["hotkey","write","press"],  // verbs in this order
    "actions_wrote_nonempty": true,          // at least one write has non-empty value
    "actions_pressed": "enter",             // at least one press/hotkey contains this key
    "actions_hotkey_contains": ["ctrl","s"], // hotkey target contains all these

    // ─── Done_when conditions (task-agnostic keyword matching) ───
    "done_when_matches": ["save","saved"],   // done_when contains any of these
    "done_when_absent": ["verify","check"],  // done_when does NOT contain these

    // ─── Screen/focus conditions ───
    "focused_contains_action_target": true,  // focused title contains focus verb's target
    "screen_contains_domain_needle": true,   // domain from goal/done_when appears in screen
    "focused_element_role_any": ["Edit","Document","ComboBox"],  // focused has writable element

    // ─── State conditions ───
    "memory_has_key_from_action": true,      // remember verb stored something
    "goal_has_domain": true,                 // goal contains a domain-like string

    // ─── Composite structural proofs ───
    "chain_is_launch": true,     // hotkey(win+r) → write → press(enter)
    "chain_is_navigation": true, // focus/hotkey(ctrl+l) → write(url) → press(enter)
    "chain_is_save": true        // hotkey(ctrl+s) with done_when matching save
  }
}
```

### Composite Conditions (sugar for common patterns)

These are NOT app-specific. They describe universal desktop interaction patterns:

| Composite | Expands To |
|-----------|-----------|
| `chain_is_launch` | `actions_sequence: [hotkey,write,press]` + first hotkey contains win+r + press contains enter |
| `chain_is_navigation` | actions include write(non-empty) + press(enter) + (ctrl+l in chain OR address bar targeted) |
| `chain_is_save` | hotkey contains ctrl+s + `done_when_matches: [save,saved]` |

## Initial Rule Set (migrated from current Python)

```json
{
  "preflights": [
    {
      "id": "deny_outcome_failed",
      "verdict": "deny",
      "description": "Any non-OK outcome is immediate denial",
      "match": {
        "outcome_failed": true
      }
    },
    {
      "id": "confirm_launch_chain",
      "verdict": "confirm",
      "description": "Win+R → type app → Enter is structurally proven launch",
      "match": {
        "outcome_ok": true,
        "chain_is_launch": true
      }
    },
    {
      "id": "confirm_browser_navigation",
      "verdict": "confirm",
      "description": "URL typed into address bar + Enter + domain visible",
      "match": {
        "outcome_ok": true,
        "chain_is_navigation": true,
        "screen_contains_domain_needle": true
      }
    },
    {
      "id": "confirm_remember_action",
      "verdict": "confirm",
      "description": "Remember verb has no side effect; OK = data captured",
      "match": {
        "outcome_ok": true,
        "actions_all_verb": "remember"
      }
    },
    {
      "id": "confirm_write_to_writable",
      "verdict": "confirm",
      "description": "Write to focused writable field with text proven typed",
      "match": {
        "outcome_ok": true,
        "done_when_matches": ["written", "typed", "text", "entered", "pasted"],
        "actions_include_verb": "write",
        "actions_wrote_nonempty": true
      }
    },
    {
      "id": "confirm_save_hotkey",
      "verdict": "confirm",
      "description": "Ctrl+S with done_when mentioning save",
      "match": {
        "outcome_ok": true,
        "chain_is_save": true
      }
    },
    {
      "id": "confirm_focus_matches_done_when",
      "verdict": "confirm",
      "description": "Focus verb succeeded and target words appear in done_when",
      "match": {
        "outcome_ok": true,
        "actions_include_verb": "focus",
        "focused_contains_action_target": true,
        "done_when_matches": ["open", "focused", "active", "front", "visible"]
      }
    }
  ]
}
```

## Self-Modify Operations (new)

```
add_preflight    {id, verdict, description, match}
update_preflight {id, set: {match?, verdict?, description?}}
remove_preflight {id}
```

These follow the same pattern as existing `add_edge`, `update_node`, etc.

## Python Evaluator (mechanical, generic)

```python
def evaluate_preflight_rules(state, wiring):
    """Evaluate declarative preflight rules from wiring. Returns verdict or None."""
    rules = wiring.get("preflights", [])
    for rule in rules:
        verdict = rule.get("verdict")
        match = rule.get("match", {})
        if _all_conditions_met(match, state):
            return verdict  # "confirm" or "deny"
    return None  # uncertain → fall through to LLM

def _all_conditions_met(match, state):
    """Generic condition evaluator. Each key is a named check."""
    for key, expected in match.items():
        if not _check_condition(key, expected, state):
            return False
    return True

def _check_condition(key, expected, state):
    """Dispatch to mechanical check functions. No semantic interpretation."""
    # Each condition is a pure function of state fields.
    # Python never decides WHAT constitutes success —
    # it only checks structural properties declared in the rule.
    ...
```

The evaluator is ~80 lines of mechanical dispatch. Each condition function
is 3-8 lines checking string containment, list membership, or field existence.

## Migration Plan

### Phase 1: Schema + Evaluator (this session)

1. Add `"preflights"` section to wiring-schema.json
2. Write generic evaluator in server.py (`evaluate_preflight_rules`)
3. Add condition check functions (one per primitive)
4. Wire evaluator into `node_verify` (before existing Python checks)
5. Add self-modify ops: `add_preflight`, `update_preflight`, `remove_preflight`

### Phase 2: Migrate Existing Patterns

6. Translate `_verify_preflight_denied` → `deny_outcome_failed` rule
7. Translate `_verify_preflight_confirmed` patterns → individual rules
8. Remove hardcoded Python preflight functions
9. Validate: run same goals, confirm same behavior

### Phase 3: Self-Modify Integration

10. Update self_modify role prompt to know about preflight ops
11. Add preflight ops to SELF_MODIFY_OPS set
12. Test: force a scenario where self_modify learns a new preflight

## Critical Design Decisions

### Why AND logic (all conditions must match)?

- Simple, predictable, debuggable
- Each rule is self-contained — no cross-rule dependencies
- Order matters only for priority (first match wins)
- Self-modify only needs to emit one complete rule

### Why first-match-wins?

- Deny rules first = safety (can't accidentally confirm)
- Order in the array = priority
- Self-modify adds to the end by default (lowest priority)
- Can reorder via `update_preflight` if needed

### Why composite conditions (chain_is_launch, etc.)?

- Reduces rule verbosity — self-modify LLM writes less JSON
- Captures universal desktop patterns without naming apps
- Each composite is 5-10 lines of Python expanding to primitive checks
- Still generic: "launch" means "run dialog + type + enter" on ANY app

### Rule evaluation order:

```
1. deny rules (fail-fast)
2. confirm rules (most specific first)
3. if no rule matches → None → LLM verify (fallback)
```

## Self-Critique & Risks

### Risk: Over-eager confirmation

**Problem**: A rule might confirm when the step actually failed silently
(e.g., "typed text" but into wrong field).

**Mitigation**: Rules require `outcome_ok` AND structural evidence.
The act node's guards already prevent wrong-target writes. If a write
succeeds (element found, text typed), the target was resolved correctly.

### Risk: Rule explosion

**Problem**: Self-modify adds many similar rules over time.

**Mitigation**: `update_preflight` can merge. Periodic cleanup via
self_modify with "consolidate preflights" reasoning. Limit in wiring:
`max_preflight_rules: 30`.

### Risk: Missing the "uncertain" case

**Problem**: A rule incorrectly matches and confirms when LLM would deny.

**Mitigation**: Conservative match conditions. Rules should only fire
on STRUCTURALLY UNAMBIGUOUS cases. If there's any doubt, no rule matches
and LLM decides. Start with high-confidence patterns only.

### Risk: Condition primitives too limited

**Problem**: Self-modify wants to express a pattern the primitives can't.

**Mitigation**: Start with the patterns we KNOW work (from current Python).
Add primitives only when real failures demonstrate the need. Keep the
primitive set small and well-tested rather than speculative.

### Risk: Composites hide complexity

**Problem**: `chain_is_navigation` might be wrong in edge cases.

**Mitigation**: Each composite has clear, documented expansion.
If it fails, self-modify can use primitive conditions directly instead.
Composites are sugar, not magic.

## Expected Outcomes

After full implementation:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Metric                    │ Before        │ After                      │
├────────────────────────────────────────────────────────────────────────┤
│ Preflight coverage        │ ~60% (frozen) │ ~60% initially, grows      │
│ Pattern learnability      │ 0 (Python)    │ self_modify can add rules  │
│ Task-specificity          │ HIGH (names)  │ ZERO (generic conditions)  │
│ Lines of preflight Python │ ~200          │ ~80 (evaluator only)       │
│ Semantic logic in Python  │ YES (bad)     │ NO (mechanical only)       │
│ Schema-validated          │ NO            │ YES                        │
│ Debuggable via /wiring    │ NO            │ YES (rules visible in API) │
│ Hot-reloadable            │ NO            │ YES (wiring reload)        │
└────────────────────────────────────────────────────────────────────────┘
```

Long-term: the organism discovers patterns humans didn't anticipate.
A self_modify that fires after repeated verify failures can emit:

```json
{"op": "add_preflight", "payload": {
  "id": "confirm_click_then_element_gone",
  "verdict": "confirm",
  "description": "Click + element disappeared from screen = action worked",
  "match": {
    "outcome_ok": true,
    "actions_include_verb": "click",
    "done_when_matches": ["clicked", "selected", "pressed", "activated"]
  }
}}
```

This is the organism LEARNING what "done" means — in data, not code.

---
---

# WHAT TO WORK ON (Priority Order)

1. **DECLARATIVE PREFLIGHTS** — Implement the plan above. Move all verify
   preflight logic from Python into wiring.json rules. Add self-modify ops.
   Each pattern = 100-180s saved per occurrence. Target: 80% coverage + learning.

2. **BLOCK REORDER** — Resequence user message blocks for attention quality.
   SCREEN last (recency), SUBTASK first (primacy). Expected: fewer reasoning
   tokens, ~2 min saved per 5-step goal. Zero-risk wiring-only change.

3. **PROMPT PRECISION** — Analyze reasoning tokens in LM Studio logs.
   Where the model re-derives rules from the system prompt, make the
   prompt more decisive so the model reasons less redundantly.

4. **RELIABILITY** — Run complex goals (install software, configure systems).
   When the model makes wrong actions, fix via prompts/guards in wiring.
   Every prevented retry = 300s+ saved.

5. **TRACE LEARNING** — Completed goal traces inform future planning.
   More traces = better first plans.

---

## Session Handover Notes

- Branch: `validation-observation` (up to date with origin)
- All files compile clean, JSON validates
- README.md was deleted (prior work), now restored with this analysis
- No runtime changes made yet — this session was analysis + planning only
- Next session: implement Phase 1 (schema + evaluator + self-modify ops)
- The existing `_verify_preflight_confirmed` and `_verify_preflight_denied`
  functions in server.py (lines ~700-850) contain the patterns to migrate
- The `SELF_MODIFY_OPS` frozenset (line ~100) needs the new ops added
- The `apply_wiring_patch` function (line ~780) needs new op handlers
- The `validate_wiring` function (line ~80) needs preflight array validation
