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

---
---

# ANALYSIS: Code Reduction & Separation of Concerns

## Current Codebase Metrics

```
┌─────────────────────┬───────┬──────────┬─────────────────────────────────┐
│ File                │ Lines │ Functions│ Purpose                         │
├─────────────────────┼───────┼──────────┼─────────────────────────────────┤
│ server.py           │ 2003  │ 98       │ HTTP + graph + nodes + guards   │
│ desktop.py          │ 1370  │ 62       │ UIA observer + input simulation │
│ actions.py          │  229  │ 14       │ Verb dispatch + runtime glue    │
│ wiring-editor.html  │  986  │ 66       │ Full workbench UI (CSS+JS+HTML) │
│ colony.py           │   95  │  5       │ Multi-slot launcher             │
├─────────────────────┼───────┼──────────┼─────────────────────────────────┤
│ TOTAL               │ 4683  │ 245      │                                 │
└─────────────────────┴───────┴──────────┴─────────────────────────────────┘
```

## server.py Breakdown (2003 lines, 98 functions)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CATEGORY              │ LINES │ FUNCTIONS │ BELONGS IN PYTHON?              │
├───────────────────────┼───────┼───────────┼─────────────────────────────────┤
│ Config/setup          │  ~60  │    5      │ ✓ mechanical                    │
│ Wiring validation     │  ~80  │    3      │ ✓ mechanical                    │
│ Wiring accessors      │ ~120  │   18      │ ✓ mechanical                    │
│ LLM call + parsing    │ ~100  │    8      │ ✓ mechanical                    │
│ Prompt assembly       │  ~80  │    6      │ ✓ mechanical                    │
│ Node handlers         │ ~350  │   12      │ ✓ mechanical                    │
│ Graph engine          │ ~100  │    4      │ ✓ mechanical                    │
│ Run loop              │ ~100  │    8      │ ✓ mechanical                    │
│ HTTP server           │ ~180  │    6      │ ✓ mechanical                    │
│ State/bus/trace       │  ~80  │    8      │ ✓ mechanical                    │
│ Self-modify apply     │ ~180  │    6      │ ✓ mechanical                    │
│                       │       │           │                                 │
│ SEMANTIC GUARDS       │ ~190  │   12      │ ✗ SHOULD BE WIRING              │
│ VERIFY PREFLIGHTS     │ ~160  │    4      │ ✗ SHOULD BE WIRING              │
│ ACTION NORMALIZER     │  ~55  │    1      │ ✗ SHOULD BE WIRING              │
│ TASK CLASSIFIERS      │  ~30  │    6      │ ✗ SHOULD BE WIRING              │
├───────────────────────┼───────┼───────────┼─────────────────────────────────┤
│ TOTAL MISPLACED       │ ~435  │   23      │ 22% of server.py is SEMANTIC    │
└───────────────────────┴───────┴───────────┴─────────────────────────────────┘
```

## The Violations — Semantic Logic in Python

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIOLATION #1: Task-Specific Classifiers (lines 766-791)                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  _browser_focused()         — checks for "chrome", "edge", "firefox"        ║
║  _focuses_browser()         — checks for "chrome", "edge", "firefox"        ║
║  _is_browser_navigation_step() — checks for "navigate", "url", "website"   ║
║  _is_playback_step()        — checks for "play", "playback", "video"        ║
║  _is_chat_message_step()    — checks for "send", "message", "chat"          ║
║                                                                             ║
║  PROBLEM: These encode SEMANTIC KNOWLEDGE about task categories.             ║
║  Python is deciding "is this a browser task?" — that's judgment, not         ║
║  mechanism. A new category (e.g., "file transfer step") requires             ║
║  editing Python.                                                            ║
║                                                                             ║
║  FIX: Move category keywords to wiring.json as guard conditions.            ║
║  Python just does: "does done_when contain any keyword from this list?"     ║
║  The list lives in wiring. Self-modify can extend it.                       ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  VIOLATION #2: normalize_action_chain() (lines 793-842, 50 lines)           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  This function:                                                             ║
║    - Detects "browser navigation step" (semantic classification)            ║
║    - Injects ctrl+l if missing (semantic correction)                        ║
║    - Clears write target after ctrl+l (semantic rule)                       ║
║    - Appends Enter if missing (semantic assumption)                         ║
║                                                                             ║
║  It's a 50-line function that ONLY fires for browser navigation.            ║
║  It hardcodes the pattern: "when navigating, ensure ctrl+l → write → enter" ║
║                                                                             ║
║  PROBLEM: This is the act prompt's job. If the model forgets ctrl+l,        ║
║  the correct fix is: make the prompt clearer, or add a guard that           ║
║  rejects the action chain (forcing retry). Not silently fix it in Python.   ║
║                                                                             ║
║  WORSE: It masks model failures. The model never learns because Python      ║
║  patches its mistakes silently. No trace of the correction in history.      ║
║                                                                             ║
║  FIX OPTIONS:                                                               ║
║    A) Remove entirely — let act prompt handle it (already has rules)        ║
║    B) Convert to a wiring "normalizer" rule set (declarative)               ║
║    C) Convert to a guard that REJECTS incomplete chains (forces retry)      ║
║                                                                             ║
║  RECOMMENDED: Option C. A guard in wiring.json:                             ║
║    "if step has domain needle AND actions include write but NOT ctrl+l       ║
║     → reject with hint: include ctrl+l before URL write"                    ║
║  This teaches the model. The current approach hides the problem.            ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  VIOLATION #3: unsafe_* guards (lines 843-885, 42 lines)                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  unsafe_chat_target()               — "address bar" in target line          ║
║  unsafe_browser_navigation_context() — "browser focused" check              ║
║  unsafe_launch_then_content_write() — Win+R → write → too soon              ║
║                                                                             ║
║  These are SEMANTIC GUARDS. They decide: "this action chain is unsafe        ║
║  because it targets the wrong UI element for this task type."               ║
║                                                                             ║
║  They're doing the RIGHT thing (preventing wrong actions) but in the        ║
║  WRONG place (Python code instead of wiring data).                          ║
║                                                                             ║
║  FIX: Express as declarative guard rules in wiring.json. Python             ║
║  evaluates them mechanically. Self-modify can add new ones.                 ║
║                                                                             ║
║  Example wiring guard:                                                      ║
║  {                                                                          ║
║    "id": "reject_write_to_address_bar_on_chat_step",                        ║
║    "when": {                                                                ║
║      "done_when_matches": ["send","message","chat","prompt"],               ║
║      "actions_write_target_line_contains": "address"                        ║
║    },                                                                       ║
║    "reject": "chat write targeted address bar; find chat input"             ║
║  }                                                                          ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  VIOLATION #4: Verify preflights with app names (lines 1121-1280)           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Line 1190: value_l.endswith(" - google chrome")                            ║
║  Line 1190: value_l.endswith(" - microsoft edge")                           ║
║  Line 1214: ("notepad", "editor") in focused_title                          ║
║                                                                             ║
║  These are NAMED APP CHECKS. They break on:                                 ║
║    - Non-English Windows (localized app names)                              ║
║    - Alternative editors (VS Code, WordPad, vim)                            ║
║    - Alternative browsers (Brave, Vivaldi, Arc)                             ║
║                                                                             ║
║  FIX: Already covered in the preflight implementation plan.                 ║
║  Use generic conditions: "focused element has writable role" instead         ║
║  of "focused title contains notepad".                                       ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## Code That SHOULD Stay in Python (mechanical)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ These are correctly placed — pure mechanism, no semantic knowledge:          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ✓ check_repeat_block()     — "same actions as last time" = structural       │
│ ✓ _step_domain_needles()   — regex extraction, not interpretation           │
│ ✓ _target_screen_line()    — lookup by ID, not judgment                     │
│ ✓ _focused_title()         — parse screen text mechanically                 │
│ ✓ _find_advance_hint()     — already reads hints FROM wiring.json ✓         │
│ ✓ apply_memory_action()    — dict write, no interpretation                  │
│ ✓ All node handlers        — execute wiring topology, no judgment           │
│ ✓ Graph engine             — find_targets, step_once, run                   │
│ ✓ HTTP server              — routing, serialization                         │
│ ✓ Wiring validation        — schema enforcement                             │
│ ✓ Self-modify apply        — validated patch application                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---
---

# ANALYSIS: Duplications and Redundancies

## Identified Duplications

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  DUPLICATION #1: Browser detection logic (3 copies)                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location 1 — _browser_focused() line 768:                                  ║
║    any(token in title for token in ("chrome","edge","firefox","opera",...))  ║
║                                                                             ║
║  Location 2 — _focuses_browser() line 775:                                  ║
║    any(token in target for token in ("chrome","edge","firefox","opera",...)) ║
║                                                                             ║
║  Location 3 — _verify_memory_capture_denied() line 1190:                    ║
║    value_l.endswith(" - google chrome") or ... "microsoft edge"             ║
║                                                                             ║
║  Same concept ("is this a browser?") expressed 3 different ways.            ║
║  If you add Brave support, you edit 3 places. Miss one = bug.              ║
║                                                                             ║
║  FIX: One keyword list in wiring.json. All three checks reference it.       ║
║  Or better: eliminate the checks entirely when preflights go declarative.  ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  DUPLICATION #2: "ctrl+l detection" (4 occurrences)                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  normalize_action_chain:                                                    ║
║    is_ctrl_l() local function (line ~798)                                   ║
║    has_ctrl_l check (line ~820)                                             ║
║                                                                             ║
║  _verify_preflight_confirmed:                                               ║
║    ctrl_l_ready check (line ~1230)                                          ║
║                                                                             ║
║  All check: verb=="hotkey" and "ctrl" in target and "l" in target           ║
║  Same logic, 4 places.                                                      ║
║                                                                             ║
║  FIX: When guards become declarative, this becomes one condition            ║
║  primitive: "actions_hotkey_contains": ["ctrl","l"]                         ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  DUPLICATION #3: "outcome OK" check (8 occurrences)                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Pattern: outcome.startswith("OK:")                                         ║
║  Found in: _verify_preflight_denied, _verify_chat_submission_denied,        ║
║  _verify_memory_capture_denied, _verify_preflight_confirmed,                ║
║  _verify_chat_submission_denied (again), node_reflect playback check,       ║
║  unsafe checks...                                                           ║
║                                                                             ║
║  Not a bug but shows how pervasive the preflight logic is — all these       ║
║  collapse into one declarative condition: "outcome_ok": true                ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  DUPLICATION #4: done_when keyword matching (5+ occurrences)                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Pattern: any(word in done_when for word in ("written","typed",...))         ║
║                                                                             ║
║  _verify_preflight_confirmed line 1214:                                     ║
║    ("written", "write", "typed", "text", "summary")                         ║
║  _verify_preflight_confirmed line 1220:                                     ║
║    ("load", "page", "navigate", "url", "website", "site")                   ║
║  _verify_preflight_confirmed line 1253:                                     ║
║    ("save", "saved")                                                        ║
║  _verify_preflight_confirmed line 1256:                                     ║
║    ("open", "focused", "active window", ...)                                ║
║  _is_browser_navigation_step line 781:                                      ║
║    ("go to ", "navigate", "url", "website", "site", ...)                    ║
║  _is_chat_message_step line 789:                                            ║
║    ("send ", "message", "prompt", "follow-up", ...)                         ║
║                                                                             ║
║  Each is a DIFFERENT keyword list for a DIFFERENT category.                 ║
║  All do the same mechanical operation: "does text contain any of [...]?"    ║
║                                                                             ║
║  FIX: One condition primitive in the evaluator:                             ║
║    "done_when_matches": ["written","typed","text"]                           ║
║  Keywords live in each rule's match block. Zero Python lists.               ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  DUPLICATION #5: Action verb extraction patterns (widespread)               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Repeated across guards and preflights:                                     ║
║    - "any action has verb == X"                                             ║
║    - "all actions have verb == X"                                           ║
║    - "action sequence starts with [hotkey, write, press]"                   ║
║    - "any press/hotkey contains 'enter'"                                    ║
║    - "any write has non-empty value"                                        ║
║                                                                             ║
║  Each guard re-implements these from scratch with inline list comps.        ║
║                                                                             ║
║  FIX: Condition primitives in the evaluator. Each is one function,          ║
║  called by name from any rule. Written once, reused everywhere.             ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## Removal Candidates — Code That Provides No Value

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  CANDIDATE #1: normalize_action_chain() — 50 lines, REMOVE                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  PURPOSE: Silently fix browser navigation chains the model gets wrong.      ║
║                                                                             ║
║  WHY REMOVE:                                                                ║
║  1. Violates "Python = mechanical" — it interprets task intent              ║
║  2. Masks model failures — model never gets negative signal                 ║
║  3. Only fires for ONE task type (browser navigation)                       ║
║  4. The act prompt already has navigation rules                             ║
║  5. A guard (reject + hint) teaches the model; normalization doesn't        ║
║                                                                             ║
║  REPLACEMENT: Declarative guard rule in wiring.json:                        ║
║    {                                                                        ║
║      "id": "reject_navigation_without_address_focus",                       ║
║      "when": {                                                              ║
║        "step_has_domain_needle": true,                                      ║
║        "actions_include_verb": "write",                                     ║
║        "actions_hotkey_absent": ["ctrl","l"],                               ║
║        "actions_verb_absent": "focus"                                       ║
║      },                                                                     ║
║      "reject": "navigation write requires ctrl+l or address bar focus"      ║
║    }                                                                        ║
║                                                                             ║
║  RISK: Model might fail more initially without the crutch.                  ║
║  MITIGATION: The act prompt already covers this. If it still fails,         ║
║  append_role_rule via self_modify fixes it in the prompt.                   ║
║                                                                             ║
║  NET: -50 lines of Python, +5 lines of wiring, model learns faster.        ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CANDIDATE #2: Task classifiers — 30 lines, REMOVE                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  _is_browser_navigation_step()                                              ║
║  _is_playback_step()                                                        ║
║  _is_chat_message_step()                                                    ║
║  _browser_focused()                                                         ║
║  _focuses_browser()                                                         ║
║                                                                             ║
║  These exist ONLY to gate the unsafe_* guards and normalize_action_chain.   ║
║  If guards become declarative rules with their own conditions,              ║
║  these classifiers have zero callers and can be deleted.                    ║
║                                                                             ║
║  NET: -30 lines of semantic Python, zero loss.                              ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CANDIDATE #3: unsafe_* functions — 42 lines, MIGRATE TO WIRING            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  unsafe_chat_target()                  — 11 lines                           ║
║  unsafe_browser_navigation_context()   — 11 lines                           ║
║  unsafe_launch_then_content_write()    — 20 lines                           ║
║                                                                             ║
║  All three are GUARD RULES that can be expressed declaratively.             ║
║  They check conditions and return rejection strings.                        ║
║  This is EXACTLY what declarative guard rules do.                           ║
║                                                                             ║
║  NET: -42 lines of Python, +3 rules in wiring.json.                        ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CANDIDATE #4: Playback special case in node_reflect — 8 lines, REMOVE     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Lines 1304-1313: Special handling for "_is_playback_step" in reflect.      ║
║  This is task-specific behavior in a node handler.                          ║
║                                                                             ║
║  FIX: The reflector LLM should handle this via its prompt.                  ║
║  If playback steps need special retry logic, encode it in the               ║
║  reflector role prompt, not in Python.                                       ║
║                                                                             ║
║  NET: -8 lines, prompt handles the edge case.                               ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

## Total Reduction Potential

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  REMOVABLE FROM server.py:                                                  │
│                                                                             │
│    normalize_action_chain:     -50 lines                                    │
│    Task classifiers:           -30 lines                                    │
│    unsafe_* guards:            -42 lines                                    │
│    Verify preflights (Python): -160 lines                                   │
│    Playback special case:      -8 lines                                     │
│    ─────────────────────────────────────                                    │
│    TOTAL REMOVABLE:            -290 lines (14.5% of server.py)              │
│                                                                             │
│  REPLACED BY:                                                               │
│    Generic preflight evaluator:  +80 lines (mechanical)                     │
│    Generic guard evaluator:      +40 lines (mechanical)                     │
│    ─────────────────────────────────────                                    │
│    TOTAL ADDED:                  +120 lines                                 │
│                                                                             │
│  NET: -170 lines from server.py                                             │
│       server.py goes from 2003 → ~1833 lines                               │
│       AND all semantic logic moves to wiring (learnable)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---
---

# ANALYSIS: HTML Interface — Capabilities & Modernization

## Current State (wiring-editor.html)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ METRICS                                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Total:      986 lines (50KB) — single file, zero dependencies              │
│  HTML:        72 lines (layout structure)                                   │
│  CSS:        114 lines (dark theme, grid layout, responsive)                │
│  JavaScript: 800 lines (all logic — graph, editors, SSE, state)             │
│  Functions:   66 (JS)                                                       │
│                                                                             │
│  ARCHITECTURE: Single-page app served from GET /                            │
│  RENDERING: SVG graph + DOM panels                                          │
│  STATE: In-memory JS objects, synced via /state and /wiring endpoints       │
│  UPDATES: SSE event stream for live node transitions                        │
│  PERSISTENCE: localStorage for graph node positions                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

## What It Does Well

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STRENGTHS                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✓ Zero dependencies — loads instantly, no build step                       │
│  ✓ Full topology graph editor (drag nodes, drag-to-connect edges)           │
│  ✓ Schema-driven property editor (reads wiring-schema.json, generates UI)   │
│  ✓ Live SSE updates (node transitions, wiring changes, push events)         │
│  ✓ Hot-reload wiring with validation feedback                               │
│  ✓ Step/Run/Pause/Resume controls                                           │
│  ✓ State inspector (plan, history, reasoning chain)                         │
│  ✓ Screen/Tree/Telemetry display                                            │
│  ✓ Dark theme, responsive grid layout                                       │
│  ✓ Auto-layout with z-index graph ordering                                  │
│  ✓ Edge routing with cubic bezier curves                                    │
│  ✓ Inline wiring JSON editor with hot-save on edit                          │
│                                                                             │
│  This is a COMPLETE development workbench for the organism.                 │
│  It's genuinely impressive for 986 lines with zero deps.                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

## What It's Missing / Could Improve

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  GAP #1: No Preflight Rule Editor                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  When preflights move to wiring.json, the UI needs a way to:               ║
║    - List all preflight rules with their match conditions                   ║
║    - Add/edit/remove rules visually                                         ║
║    - Show which rule fired on last verify (highlight in real-time)          ║
║    - Show rule hit counts (which patterns save the most time)              ║
║                                                                             ║
║  IMPLEMENTATION: The schema-driven editor already handles this!             ║
║  As long as wiring-schema.json has the preflight rule definition,           ║
║  renderValueEditor() will auto-generate the edit UI.                        ║
║  Only addition: a "Preflights" section in the left rail.                   ║
║                                                                             ║
║  EFFORT: ~20 lines of JS + schema definition. No new architecture.         ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  GAP #2: No Guard Rule Editor                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Same as above. When guards become declarative, the UI shows them.          ║
║  The schema-driven editor already covers generic object editing.            ║
║  Just need a "Guards" panel in the left rail alongside "Filters".           ║
║                                                                             ║
║  EFFORT: ~10 lines of JS.                                                  ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  GAP #3: No Timing/Performance Panel                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  The workbench shows WHAT happened but not HOW LONG each step took.         ║
║  Missing:                                                                   ║
║    - Per-node execution time (from SSE timestamps)                          ║
║    - "Preflight hit" vs "LLM verify" indicator                             ║
║    - Cumulative time per goal                                               ║
║    - Token count per call (if server exposes it)                            ║
║                                                                             ║
║  WHY IT MATTERS: Optimization is blind without timing visibility.           ║
║  Currently you have to read LM Studio logs manually.                        ║
║                                                                             ║
║  IMPLEMENTATION:                                                            ║
║    - Server already pushes SSE events with cycle number                     ║
║    - Add timestamp to SSE events (trivial: time.time() in sse_push)        ║
║    - JS calculates deltas between node/result events                        ║
║    - Display in telemetry panel or new "Timing" tab                        ║
║                                                                             ║
║  EFFORT: ~5 lines server.py + ~30 lines JS.                                ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  GAP #4: No Preflight Hit Visualization on Graph                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  When verify fires preflight (skips LLM), the graph should show it.        ║
║  Currently: verify node turns green (active) briefly, same as LLM call.    ║
║  Better: flash a different color or show "⚡" badge on preflight hit.       ║
║                                                                             ║
║  This tells the operator: "that was instant, no LLM cost."                 ║
║                                                                             ║
║  IMPLEMENTATION:                                                            ║
║    - Server SSE result event already has signals: ["step_confirmed"]        ║
║    - Add field: "preflight": true to the event when rule matched            ║
║    - JS checks for preflight flag, applies different node style             ║
║                                                                             ║
║  EFFORT: ~3 lines server.py + ~10 lines JS.                                ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  GAP #5: No Wiring Diff View                                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  When self_modify mutates wiring, the dashboard shows "wiring_modified"     ║
║  SSE event but not WHAT changed. A diff view showing before/after would     ║
║  make self-modification observable and debuggable.                           ║
║                                                                             ║
║  IMPLEMENTATION: Store last wiring snapshot in JS. On wiring_modified,      ║
║  compute diff (JSON key-level) and display in log tab.                      ║
║                                                                             ║
║  EFFORT: ~30 lines JS.                                                     ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## What NOT to Change

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ KEEP AS-IS                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✓ Single-file architecture — no build step, no npm, no frameworks          │
│  ✓ Zero dependencies — loads from disk or localhost instantly                │
│  ✓ SVG-based graph — performant, scriptable, no canvas state bugs           │
│  ✓ Schema-driven editors — auto-adapt when wiring-schema.json changes       │
│  ✓ SSE for live updates — simple, reliable, no WebSocket complexity         │
│  ✓ localStorage for positions — no server persistence needed                │
│  ✓ Dark theme — this is a dev tool, not a consumer product                  │
│                                                                             │
│  DO NOT:                                                                    │
│    ✗ Add React/Vue/Svelte — kills the zero-dep advantage                    │
│    ✗ Split into multiple files — adds serving complexity                    │
│    ✗ Add a build step — violates "any person with a computer" vision        │
│    ✗ Add external CSS frameworks — bloat for no gain                        │
│    ✗ "Modernize" with TypeScript — the 800 lines of JS work fine            │
│                                                                             │
│  The HTML IS already modern. It uses:                                       │
│    - CSS Grid + custom properties                                           │
│    - async/await                                                            │
│    - Optional chaining (?.)                                                 │
│    - EventSource (SSE)                                                      │
│    - Template literals                                                      │
│    - Pointer events API                                                     │
│    - dvh units                                                              │
│                                                                             │
│  "Modernization" = adding the missing FEATURES, not rewriting the stack.    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---
---

# ANALYSIS: Unified Declarative Rule System

## The Big Picture — One Evaluator, Three Rule Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Currently: 3 separate Python systems doing similar pattern matching:       │
│                                                                             │
│    1. PREFLIGHTS  — verify: should I confirm/deny without LLM?              │
│    2. GUARDS      — act: should I reject this action chain?                 │
│    3. NORMALIZERS — act: should I silently fix this chain?                  │
│                                                                             │
│  All three: read state + actions → evaluate conditions → return verdict     │
│                                                                             │
│  UNIFIED DESIGN:                                                            │
│                                                                             │
│    wiring.json:                                                             │
│      "rules": [                                                             │
│        {"id":..., "phase":"verify",  "verdict":"confirm", "match":{...}},   │
│        {"id":..., "phase":"verify",  "verdict":"deny",    "match":{...}},   │
│        {"id":..., "phase":"act",     "verdict":"reject",  "match":{...}},   │
│      ]                                                                      │
│                                                                             │
│    server.py:                                                               │
│      def evaluate_rules(phase, state, wiring):                              │
│          """One evaluator for all phases."""                                 │
│          for rule in wiring.get("rules", []):                               │
│              if rule.get("phase") != phase:                                 │
│                  continue                                                   │
│              if _all_conditions_met(rule["match"], state):                  │
│                  return rule                                                │
│          return None                                                        │
│                                                                             │
│  ONE evaluator replaces:                                                    │
│    - _verify_preflight_denied()        (8 lines)                            │
│    - _verify_preflight_confirmed()     (85 lines)                           │
│    - _verify_chat_submission_denied()  (35 lines)                           │
│    - _verify_memory_capture_denied()   (40 lines)                           │
│    - unsafe_chat_target()              (11 lines)                           │
│    - unsafe_browser_navigation_context() (11 lines)                         │
│    - unsafe_launch_then_content_write() (20 lines)                          │
│    - normalize_action_chain()          (50 lines)                           │
│    - _is_browser_navigation_step()     (3 lines)                            │
│    - _is_playback_step()               (3 lines)                            │
│    - _is_chat_message_step()           (5 lines)                            │
│    - _browser_focused()                (3 lines)                            │
│    - _focuses_browser()                (6 lines)                            │
│                                                                             │
│  Total replaced: ~280 lines of semantic Python                              │
│  Total added:    ~100 lines of generic evaluator                            │
│  NET GAIN:       -180 lines + all logic now learnable via self_modify       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Rule Phases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE: "verify" — runs in node_verify BEFORE LLM call                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Verdict options: "confirm" | "deny"                                        │
│                                                                             │
│  "confirm" → step advances, no LLM verify needed                           │
│  "deny"    → step fails, goes to reflect, no LLM verify needed             │
│  no match  → fall through to LLM verify (two-pass)                         │
│                                                                             │
│  Evaluation order: deny rules first, then confirm rules.                   │
│  Safety: deny is cheaper (prevents false confirms).                         │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ PHASE: "act" — runs in node_act AFTER LLM produces actions, BEFORE exec     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Verdict options: "reject"                                                  │
│                                                                             │
│  "reject" → action chain NOT executed, error message set, goes to reflect  │
│  no match → actions execute normally                                        │
│                                                                             │
│  This replaces unsafe_* guards AND normalize_action_chain.                  │
│  Instead of silently fixing: reject + hint. Model learns.                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Self-Modify Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  New self_modify operations:                                                │
│                                                                             │
│    add_rule    {id, phase, verdict, description, match}                     │
│    update_rule {id, set: {match?, verdict?, description?}}                  │
│    remove_rule {id}                                                         │
│                                                                             │
│  When self_modify fires after repeated failures:                            │
│                                                                             │
│    SCENARIO: act keeps writing URL without ctrl+l, gets rejected            │
│    REFLECT: "model forgets address bar focus for navigation"                │
│    SELF_MODIFY options:                                                     │
│      1. append_role_rule to act prompt (teach model)                        │
│      2. add_rule phase=act to reject the pattern (guard)                   │
│      3. add_rule phase=verify to confirm navigation structurally            │
│                                                                             │
│  The organism can now learn BOTH:                                           │
│    - "What actions are wrong" (act-phase reject rules)                      │
│    - "What outcomes prove success" (verify-phase confirm rules)             │
│                                                                             │
│  This is the organism developing INTUITION about its own capabilities.      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Condition Primitive Inventory (Complete)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CONDITION NAME                      │ CHECKS                                │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                                     │                                       │
│ ── Outcome ──                       │                                       │
│ outcome_ok                          │ last_outcome starts with "OK:"        │
│ outcome_failed                      │ last_outcome starts with "FAILED"/""  │
│                                     │                                       │
│ ── Actions (verb checks) ──        │                                       │
│ actions_include_verb                │ any action.verb == value              │
│ actions_all_verb                    │ all action.verb == value              │
│ actions_verb_absent                 │ no action.verb == value               │
│ actions_sequence                    │ verb sequence starts with [...]       │
│                                     │                                       │
│ ── Actions (value checks) ──       │                                       │
│ actions_wrote_nonempty              │ a write action has non-empty value    │
│ actions_pressed                     │ press/hotkey target contains key      │
│ actions_hotkey_contains             │ hotkey target contains ALL of [...]   │
│ actions_hotkey_absent               │ no hotkey contains ALL of [...]       │
│ actions_write_is_url                │ write value looks like URL/domain     │
│                                     │                                       │
│ ── Done_when / Step text ──         │                                       │
│ done_when_matches                   │ done_when contains any of [...]       │
│ done_when_absent                    │ done_when does NOT contain [...]      │
│ step_has_domain_needle              │ goal/done_when has domain pattern     │
│                                     │                                       │
│ ── Screen / Focus ──                │                                       │
│ screen_contains_domain_needle       │ domain needle in screen/title         │
│ screen_contains                     │ screen text contains any of [...]     │
│ focused_contains_action_target      │ focused title matches focus target    │
│ focused_has_writable                │ screen has writable [ID] element      │
│                                     │                                       │
│ ── Memory ──                        │                                       │
│ memory_stored_by_action             │ remember verb stored a key            │
│ memory_value_min_length             │ stored value >= N chars               │
│ memory_value_not_url                │ stored value isn't just a URL         │
│ memory_value_not_title              │ stored value != focused window title  │
│                                     │                                       │
│ ── Composites (expand internally) ──│                                       │
│ chain_is_launch                     │ hotkey(win+r) → write → press(enter) │
│ chain_is_navigation                 │ ctrl+l/addr → write → press(enter)   │
│ chain_is_save                       │ hotkey(ctrl+s) + done_when=save       │
│ chain_wrote_and_submitted           │ write + press(enter)/click(send)      │
│                                     │                                       │
└─────────────────────────────────────┴───────────────────────────────────────┘
```

## Implementation Sequence (Revised — Unified)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  PHASE 1: Foundation (next session)                                         │
│  ─────────────────────────────────                                          │
│    1. Add "rules" array to wiring-schema.json                               │
│    2. Write evaluate_rules() in server.py (~60 lines)                       │
│    3. Write _check_condition() dispatch (~40 lines)                         │
│    4. Wire into node_verify (replace _verify_preflight_* calls)             │
│    5. Add 7 initial verify-phase rules to wiring.json                       │
│    6. Test: same goals produce same outcomes                                │
│    7. Add self-modify ops (add_rule, update_rule, remove_rule)              │
│                                                                             │
│  PHASE 2: Guards migration                                                  │
│  ────────────────────────                                                   │
│    8. Add act-phase rules replacing unsafe_* functions                      │
│    9. Wire into node_act (replace unsafe_* calls)                           │
│   10. Remove unsafe_* functions                                             │
│   11. Remove task classifiers (_is_browser_*, etc.)                         │
│   12. Remove or replace normalize_action_chain with reject rule             │
│   13. Test: same goals, guards still fire                                   │
│                                                                             │
│  PHASE 3: Learning verification                                             │
│  ──────────────────────────────                                             │
│    14. Update self_modify role prompt to know about rule ops                │
│    15. Run a goal that triggers self_modify                                 │
│    16. Verify it emits a valid add_rule patch                               │
│    17. Verify the rule fires on subsequent runs                             │
│                                                                             │
│  PHASE 4: UI integration                                                    │
│  ───────────────────────                                                    │
│    18. Add "Rules" panel to left rail in wiring-editor.html                 │
│    19. Show rule hit/miss on verify SSE events                              │
│    20. Add timing to SSE events for performance visibility                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Self-Critique of This Plan

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITIQUE #1: "Are 30 condition primitives too many?"                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  CONCERN: Each primitive is a Python function. 30 functions = 150-240       ║
║  lines. That's more than some of the code being replaced.                   ║
║                                                                             ║
║  COUNTER: Each primitive is 3-8 lines, trivially testable, and REUSED       ║
║  across all rules. The 280 lines being replaced are tangled, duplicative,   ║
║  and untestable in isolation.                                               ║
║                                                                             ║
║  DECISION: Start with ~15 primitives (the ones needed for initial rules).   ║
║  Add more only when self_modify needs them. YAGNI for rare conditions.      ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITIQUE #2: "What if the evaluator itself needs to be learned?"           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  CONCERN: If a pattern can't be expressed with existing primitives,         ║
║  self_modify is stuck. It can't add new Python condition functions.          ║
║                                                                             ║
║  COUNTER: The primitives cover ALL current hardcoded patterns. They         ║
║  are designed from the PROVEN patterns in the existing code. If new         ║
║  patterns emerge that need new primitives, that's a human-session task      ║
║  (add one 5-line function). The self_modify path handles 95% of cases.      ║
║                                                                             ║
║  DECISION: Accept this limitation. Primitives grow slowly with human        ║
║  sessions. Rules grow autonomously via self_modify. Good tradeoff.          ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITIQUE #3: "Should normalize_action_chain really be removed?"            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  CONCERN: The normalizer catches real model mistakes. Removing it means     ║
║  more retries until the model learns. Each retry = 300s+.                   ║
║                                                                             ║
║  COUNTER: The act prompt ALREADY has the navigation rules. If the model     ║
║  still forgets ctrl+l, the prompt is weak — fix the PROMPT. Silently        ║
║  fixing in Python means the model never gets the error signal it needs      ║
║  to improve its reasoning. You're paying 50 lines of Python to hide a       ║
║  prompt problem that should take 1 line to fix in the role text.            ║
║                                                                             ║
║  COMPROMISE: Don't remove Day 1. Convert to reject rule first. If           ║
║  reject causes >3 extra retries on navigation goals, strengthen the         ║
║  act prompt. Remove normalize_action_chain only after prompt proves          ║
║  sufficient. Track via traces.                                              ║
║                                                                             ║
║  DECISION: Phase 2 converts to reject rule. Observe for 1-2 goals.         ║
║  If model handles it → delete normalizer. If not → fix prompt first.        ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITIQUE #4: "Is unifying guards+preflights into one 'rules' array smart?" ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  CONCERN: Different phases have different semantics. Mixing them in one     ║
║  array could confuse self_modify or the human operator.                     ║
║                                                                             ║
║  COUNTER: The "phase" field clearly separates them. The evaluator only      ║
║  looks at rules matching the requested phase. Unified array means           ║
║  ONE schema definition, ONE set of self-modify ops, ONE UI panel.           ║
║  Simpler > separated.                                                       ║
║                                                                             ║
║  ALTERNATIVE considered: separate "preflights" and "act_guards" arrays.     ║
║  This means: 2 schema definitions, 2 sets of ops (add_preflight +          ║
║  add_guard), 2 UI panels, 2 evaluator entry points. More complexity         ║
║  for zero functional benefit.                                               ║
║                                                                             ║
║  DECISION: Unified "rules" array with "phase" field. Single system.         ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITIQUE #5: "First-match-wins ordering — can self_modify break it?"       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  CONCERN: add_rule appends to end. If a deny rule should fire before a      ║
║  confirm rule but gets added later, the confirm rule wins incorrectly.      ║
║                                                                             ║
║  SOLUTION: Evaluation order is: all deny rules first, then confirm rules,   ║
║  regardless of array position. Python sorts by verdict before evaluating.   ║
║  This means: deny always wins over confirm. Self_modify can't break this.  ║
║                                                                             ║
║  Within same verdict type: array order = priority. Self_modify adds to      ║
║  end = lowest priority. Safe default. Operator can reorder via UI.          ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITIQUE #6: "986-line HTML — should it grow or be refactored?"            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  CONCERN: Adding rules panel + timing + diff view could push to 1200+.     ║
║                                                                             ║
║  COUNTER: 1200 lines for a full dev workbench is SMALL. The file is         ║
║  well-structured (CSS block, HTML block, JS block). It's readable.          ║
║  There's no maintenance burden — it's a tool, not a product.                ║
║                                                                             ║
║  The real question: does single-file become unnavigable at 1500 lines?      ║
║  Answer: No. VS Code folds sections. grep works. No imports to trace.       ║
║  The zero-dep advantage outweighs the "long file" concern until ~3000 LOC. ║
║                                                                             ║
║  DECISION: Keep single-file. Grow as needed. Only split if a clear          ║
║  independent component emerges (unlikely for <2000 LOC).                    ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---
---

# ANALYSIS: Fallback Removal Audit

## What "Fallbacks" Exist

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #1: LLM parse retries with temperature bump                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: call_node() lines 548-565                                        ║
║  Behavior: If LLM output doesn't parse as valid JSON with correct           ║
║  record_type, retry with higher temperature (up to 2 retries).              ║
║                                                                             ║
║  VERDICT: KEEP. This is mechanical retry logic, not semantic fallback.      ║
║  A 4B model sometimes produces malformed JSON. Retrying with higher         ║
║  temperature is a proven recovery mechanism. It doesn't interpret           ║
║  content — just checks "is this valid JSON with the right record_type?"     ║
║                                                                             ║
║  HOWEVER: The limit (llm_parse_retries: 2) is in wiring.json.              ║
║  Self_modify can adjust it. This is correctly placed.                       ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #2: Planner retry on parse failure                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: node_planner() — signals "retry_plan" with counter               ║
║  Behavior: If planner output doesn't parse, retry (up to planner_retries).  ║
║  After max retries: "plan_failed" signal → bus_post → satisfied(false).     ║
║                                                                             ║
║  VERDICT: KEEP. Same as above — structural retry for parse failures.        ║
║  Not a semantic fallback. It doesn't guess what the plan should be.         ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #3: normalize_action_chain() — SILENT CORRECTION                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: server.py lines 793-842                                          ║
║  Behavior: Silently injects ctrl+l, clears targets, appends Enter.          ║
║                                                                             ║
║  VERDICT: REMOVE (already discussed above).                                 ║
║  This IS a semantic fallback. It compensates for model mistakes without     ║
║  signaling the error. Replace with reject rule that teaches the model.      ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #4: verb_normalize in act config                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: node_act() line ~1016, reads from wiring.act.verb_normalize      ║
║  Config:   [{"from":"press","to":"hotkey","when_target_contains":"+"}]      ║
║  Behavior: If model emits press "ctrl+s" instead of hotkey "ctrl+s",        ║
║            automatically converts to hotkey.                                ║
║                                                                             ║
║  VERDICT: KEEP — this is ALREADY in wiring.json (good!). It's              ║
║  mechanical normalization of equivalent verbs, not semantic correction.      ║
║  "press ctrl+s" and "hotkey ctrl+s" mean the same thing mechanically.       ║
║  The model isn't "wrong" — the vocabulary is ambiguous. This resolves       ║
║  ambiguity, not errors.                                                     ║
║                                                                             ║
║  Self_modify can extend it (add more normalizations). Correctly placed.     ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #5: Run dialog special cases in node_act execution                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: node_act() lines ~1006-1020                                      ║
║  Behavior:                                                                  ║
║    - If focused="Run" and write has target → clear target (write to field)  ║
║    - If after Win+R and write target == write value → clear target           ║
║    - If press has no key and prior write exists → assume "enter"            ║
║    - If click "ok" in Run dialog → convert to press "enter"                 ║
║                                                                             ║
║  VERDICT: BORDERLINE. These handle model confusion about Run dialog:        ║
║    - Model says write target="notepad" value="notepad" (target is wrong)    ║
║    - Model says press "" after a write (forgot to specify enter)            ║
║    - Model clicks "OK" button in Run instead of pressing Enter              ║
║                                                                             ║
║  These are TASK-SPECIFIC (Run dialog) but also GENERIC (any Win+R use).     ║
║                                                                             ║
║  DECISION: Convert to declarative normalizations in wiring.json             ║
║  under act.verb_normalize (already exists). They're mechanical              ║
║  translations, not semantic corrections:                                    ║
║    - "write to Run dialog always targets the open field"                    ║
║    - "empty press after write = press enter"                                ║
║    - "click OK in dialog = press enter"                                     ║
║                                                                             ║
║  These could be wiring rules like:                                          ║
║    {"when":"focused_run_dialog","press_empty":"enter"}                       ║
║    {"when":"click_ok_in_dialog","convert":"press_enter"}                     ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #6: Scroll enrichment in desktop.py                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: desktop.py observe() — scroll_enrich_* config                    ║
║  Behavior: If probe finds fewer elements than scroll_enrich_min,            ║
║  scroll the window up/down and re-probe to find hidden elements.            ║
║                                                                             ║
║  VERDICT: KEEP. This is mechanical observation enrichment, controlled       ║
║  entirely by wiring.json observe config. Not a semantic fallback.           ║
║  Config already in wiring: scroll_enrich_min, scroll_enrich_passes, etc.    ║
║  Self_modify can tune via set_observe op. Correctly placed.                 ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  FALLBACK #7: Dense probe in desktop.py                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  Location: desktop.py observe() — dense_probe_min_px config                 ║
║  Behavior: If initial probe finds too few elements, re-probe with           ║
║  smaller step size over full screen.                                        ║
║                                                                             ║
║  VERDICT: KEEP. Same as scroll enrichment — mechanical, config-driven.      ║
║                                                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## Summary: Fallback Audit Results

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  KEEP (mechanical, config-driven, not semantic):                            │
│    ✓ LLM parse retries with temperature bump                               │
│    ✓ Planner retry on parse failure                                         │
│    ✓ verb_normalize (wiring-configured)                                     │
│    ✓ Scroll enrichment (wiring-configured)                                  │
│    ✓ Dense probe (wiring-configured)                                        │
│                                                                             │
│  REMOVE (semantic, masks errors, task-specific):                            │
│    ✗ normalize_action_chain → reject rule                                   │
│                                                                             │
│  MIGRATE TO WIRING (mechanical but hardcoded):                              │
│    → Run dialog special cases → act.verb_normalize or reject rules          │
│                                                                             │
│  TOTAL REMOVABLE: ~60 lines                                                 │
│  Combined with guards/preflights migration: ~350 lines removed              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---
---

# COMPLETE REDUCTION SUMMARY

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  server.py TODAY:      2003 lines, 98 functions                             │
│                                                                             │
│  AFTER unified rules migration:                                             │
│                                                                             │
│    REMOVED:                                                                 │
│      Verify preflights (Python):    -160 lines                              │
│      Task classifiers:              -30 lines                               │
│      unsafe_* guards:               -42 lines                               │
│      normalize_action_chain:        -50 lines                               │
│      Run dialog special cases:      -15 lines                               │
│      Playback special case:         -8 lines                                │
│      ──────────────────────────────────────                                 │
│      TOTAL REMOVED:                 -305 lines                              │
│                                                                             │
│    ADDED:                                                                   │
│      evaluate_rules():              +15 lines                               │
│      _all_conditions_met():         +8 lines                                │
│      _check_condition() dispatch:   +20 lines                               │
│      Condition primitives (15):     +75 lines                               │
│      Self-modify ops (3):           +40 lines                               │
│      Validation for rules:          +15 lines                               │
│      ──────────────────────────────────────                                 │
│      TOTAL ADDED:                   +173 lines                              │
│                                                                             │
│    NET: -132 lines from server.py (2003 → ~1871)                            │
│         + all semantic logic now in wiring.json (learnable)                 │
│         + zero duplication (one evaluator, reusable conditions)             │
│         + zero task-specific Python                                         │
│         + zero app-name strings in Python                                   │
│                                                                             │
│  wiring.json GROWTH:                                                        │
│    Initial rules array: ~120 lines (7 verify + 3 act rules)                │
│    Schema addition: ~40 lines                                               │
│                                                                             │
│  wiring-editor.html:                                                        │
│    Rules panel: ~30 lines                                                   │
│    Timing display: ~35 lines                                                │
│    Preflight indicator: ~13 lines                                           │
│    TOTAL: +78 lines (986 → ~1064)                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
