# endgame-ai - Self-Rewiring Local Desktop Agent

This README is the bootstrap document for the next engineering session. It is
based on the repository, the live endgame-ai API, the current `state.json`, and
the LM Studio server log available on 2026-06-22 at about 22:42 Europe/Warsaw.

endgame-ai is a local Windows desktop ROD loop. A local LM Studio model plans,
acts on the desktop, verifies outcomes, reflects on failures, and can mutate its
own `prompts/wiring.json` through validated operations. Python is the mechanical
body. `wiring.json` is the mutable behavior layer. The local model supplies
judgment.

The system is currently usable and exploratory. In the active/persisted run it
tried multiple approaches, recovered from at least one bad navigation chain, and
kept moving despite an imprecise human goal. It is not yet fully reliable: the
latest run also proves a verification gap where the model treated a successful
`wait` action as proof that an external response had arrived.

---

## Status Snapshot

Repository state before this README rewrite:

```text
branch: validation-observation
tracked worktree before README edit: clean
latest commits:
  d370285 Complete fallback audit integration
  192852c Add wiring editor rule visibility
  161e2ad Migrate semantic guards to declarative rules
  e5481a4 Add declarative preflight rules
```

Important ignored runtime files exist and should not be treated as source:

```text
state.json
__pycache__/
prompts/wiring.backup.json
prompts/wiring.backup.20260622-221732.json
```

Current source sizes:

```text
server.py                  2059 lines
desktop.py                 1279 lines
actions.py                  200 lines
colony.py                    91 lines
wiring-editor.html         1148 lines
prompts/wiring.json        1047 lines
prompts/wiring-schema.json  269 lines
```

Live API facts from `GET http://127.0.0.1:9078/health`:

```text
ok: true
slot: 1
port: 9078
permissions: desktop_exec
nodes: entry, planner, scheduler, observe, act, verify, reflect,
       satisfied, bus_check, bus_post, moe_route, self_modify
capabilities: desktop_exec, rod_loop, self_modify, colony_delegate,
              trace_memory, step_debug, pause_resume, wiring_hot_reload,
              state_memory
```

`/health.run.running` was `false` at the snapshot, while `/state` and the LM
Studio log showed recent run activity. Treat `/health` and `/state` together;
do not infer run truth from only one field.

---

## Architecture

```text
Python: server.py, desktop.py, actions.py
  Mechanical body. It serves HTTP, runs the graph, observes UIA, executes
  desktop verbs, validates wiring patches, hot-reloads wiring, stores state,
  and performs generic rule evaluation.

prompts/wiring.json
  Mutable brain. It defines graph topology, prompt blocks, role prompts,
  runtime limits, observation config, MoE routing, act normalizers, and
  declarative rules. Semantic policy should live here.

prompts/wiring-schema.json
  Validation contract for wiring. It now includes the unified rules schema,
  act normalizer schema, and rule match condition vocabulary.

wiring-editor.html
  Zero-build browser workbench served by server.py. It shows topology, state,
  timings, filters, reasoning, and now rules/rule hits.

LM Studio on localhost:1234
  OpenAI-compatible local model server. Current loaded model:
  nvidia-nemotron-3-nano-4b@q6_k_xl.
```

The boundary remains the central engineering rule:

```text
Python checks structure.
Wiring expresses policy.
The model makes judgment when rules cannot prove the answer.
```

---

## Runtime Today

LM Studio facts from log and API:

```text
model path:
  C:\Users\px-wjt\.lmstudio\models\unsloth\NVIDIA-Nemotron-3-Nano-4B-GGUF\NVIDIA-Nemotron-3-Nano-4B-UD-Q6_K_XL.gguf

model id from /v1/models:
  nvidia-nemotron-3-nano-4b@q6_k_xl

server:
  HTTP listening on port 1234
  OpenAI-compatible endpoint: /v1/chat/completions
  OpenAI-compatible endpoint: /v1/models
  logs saved in C:\Users\px-wjt\.lmstudio\server-logs

llama.cpp runtime:
  n_parallel=2
  configured n_ctx=35664
  two slots, each n_ctx=17920
  prompt cache enabled, 8192 MiB limit
  context checkpoints enabled, max 32
```

The old README path `%USERPROFILE%\.cache\lm-studio\server-logs` is stale on
this machine. The actual path is:

```text
C:\Users\px-wjt\.lmstudio\server-logs\2026-06\2026-06-22.1.log
```

---

## The Two-Pass Reasoning Loop

The two-pass loop is still intact. Every LLM node is called once to think and
then called again with the first pass reasoning plus:

```text
DECIDE NOW: emit exactly one content JSON object for this role. No prose.
```

The log proves this pattern. Planner, act, verify, reflect, and self_modify
requests include the static role prompt and then a second request containing
`ROD_REASONING_CONTENT`.

This is still a good design for small local models. It catches some first-pass
impulses, preserves reasoning across nodes, and makes failures inspectable. Do
not remove it for latency alone. Prefer preflight/rule hits to remove whole LLM
calls when the outcome is mechanically provable.

---

## ROD Loop

Current graph shape:

```text
goal_inbox -> moe_route -> planner -> scheduler -> bus_check -> observe -> act -> verify
                                                                       |        |
                                                                       |        v
                                                                       +---- reflect
                                                                              |
                                                                              v
                                                                         self_modify
```

Key node responsibilities:

```text
planner      converts GOAL into 1-10 observable subtasks
scheduler    selects current step or completion
bus_check    polls for interrupt goals
observe      captures UIA screen text and action targets
act          emits and executes desktop verb chains
verify       confirms or denies step completion
reflect      diagnoses failure and chooses retry/replan/escalation
self_modify  proposes validated wiring mutations after escalation
```

The graph still has retry, replan, and self-modify escalation paths. The final
read-only `/state` API snapshot before this README commit had:

```text
step: 0
current_step: Navigate to https://thegrok.ai using ctrl+l then write the URL and press enter.
done_when: The browser is on TheGrok AI homepage.
retries: 0
replan_count: 1
_cycle: 133
_resume_node: act
last_outcome: OK: wait : waited 5000 ms
last_error: ""
```

Earlier in the same investigation the persisted state was on `Wait for AI
response` with repeated waits, empty memory, and a verifier false confirmation.
That earlier evidence is preserved below because it is the clearest proven
remaining bug.

The run goal was intentionally imprecise:

```text
use thegrok tab in chrome to have a 2 turns conversation with the grok ai about
current geopolitical situation by making a followup question after the first one
where the second one will be dependent on the response to the first one, then
write the result of the conversation into notepad window and then your task will
be completed
```

Observed behavior:

- It planned a multi-step browser/chat/notepad task.
- It used Chrome and Notepad windows visible in the UIA screen.
- It attempted URL navigation and question submission.
- It hit a network error for `thegrok.ai`.
- It drifted to a Google search for `geopolitical tensions`.
- It recognized some failures and retried/replanned.
- It repeatedly waited for a response while memory stayed empty.
- It eventually accepted a wait outcome as completion evidence, which is wrong.

The human observation that it is "acting great" is partly supported: it is
trying different approaches and recovering from some mistakes. The truthful
engineering read is: exploration and guard behavior improved, but completion
proof is still too weak for external-response tasks.

---

## MoE / Colony Routing

This repository uses a practical local MoE/colony routing layer, not a mixture
of model weights. The current `wiring.moe` config is:

```json
{
  "required_permission": "desktop_exec",
  "delegate_keywords": ["chrome", "browser"],
  "default_exec_slot": 1
}
```

`/health` reports `colony_delegate: true`, and the topology contains
`moe_route`, `bus_check`, and `bus_post`. The active instance is slot 1 with
`desktop_exec`. For this session, the MoE value is routing and isolation between
desktop-capable slots, not multiple specialized LLMs.

Next MoE work should be evidence-driven:

- Log whether a goal was handled locally or delegated.
- Record slot, permission, and bus messages in state/history.
- Avoid routing by brittle app keywords when the same signal can be expressed
  through permissions and available windows.

---

## Observation

Observation is UIA based and mechanical. The act circuit is the only circuit
that receives `SCREEN`.

Current observe config:

```text
min_elements: 3
wait_retries: 6
wait_ms: 750
probe_step_px: 40
hover_scan_enabled: true
hover_scan_step_px: 70
dense_probe_min_px: 24
scroll_enrich_min: 3
scroll_enrich_passes: [-3, -2, 2, 3]
scope_depth: 4
element_text_max: 500
read_text_max: 16000
render_focused_first: true
render_class_name: false
render_automation_id: true
render_window_per_element: false
desktop_tree_enabled: false
```

The latest persisted screen showed Chrome focused on Google results, with
actionable IDs for the address bar, Google search box, tabs, bookmarks, and
buttons. It also showed Notepad and LM Studio in the window list. Probe stats
from state:

```text
primary_step=40
primary_points=357
primary_found=0
hover_step=70
hover_points=405
hover_found=49
classified_nodes=42 in one snapshot
```

Mechanical observation enrichment should stay in Python. It is config-driven,
generic, and does not decide task success.

---

## Measured Performance

The previous README's `6.14 tok/s` generation figure is stale for the current
LM Studio run. Recent LM Studio `print_timing` lines show:

```text
generation/eval speed: usually about 24-25 decoded tokens/s
cached prompt eval:    often about 480-558 prompt tokens/s
initial prompt eval:   seen at about 158 tokens/s before cache warmed
recent total times:    about 4.3s to 18.9s per LLM call in sampled lines
```

Log summary during the investigation while the file was still growing:

```text
server log bytes at 2026-06-22 22:48:06: 2637591
chat completion POST requests from the 22:42 scan: at least 148
generated predictions from the 22:42 scan: at least 147
latest timing line in the 22:42 scan: 2026-06-22 22:42:08
```

Role prompt occurrences in the log scan:

```text
ROLE: Planner      16
ROLE: Act          46
ROLE: Verifier     18
ROLE: Reflector    62
ROLE: Self_modify   6
```

Those are text occurrences in request bodies, not exact node-call counters.

LM Studio also prints lines like `Done reasoning. Reasoned for 6644.96 seconds`.
Those numbers do not match wall-clock timings and should not be used as elapsed
time. Use `print_timing` `total time`, prompt tokens, completion tokens, and
token/s lines for performance analysis.

Highest leverage remains:

```text
1. Skip verifier LLM calls with conservative verify rules.
2. Reject unsafe act chains before desktop execution.
3. Tighten prompts where the model repeats bad reasoning.
4. Reorder ACT prompt blocks if log evidence shows attention waste.
```

---

## Self-Modify

Self-modify is enabled and exposed by `/health`. Current allowed operations:

```text
add_node, update_node, remove_node
add_edge, remove_edge
add_rule, update_rule, remove_rule
set_guard, set_limit, set_observe
set_prompt_base, set_role, append_role_rule
set_reasoning
```

Self-modify behavior in `server.py`:

- Reads `prompts/wiring.json`.
- Writes `prompts/wiring.backup.json`.
- Writes timestamped backups such as `prompts/wiring.backup.YYYYMMDD-HHMMSS.json`.
- Calls the self_modify LLM node.
- Validates the mutation with `validate_wiring`.
- Writes the new wiring and hot-reloads `WIRING`.
- Pushes an SSE `wiring_modified` event.

The current log proves self_modify prompts appeared, and `/health` proves the
ops are available. This investigation did not prove a successful live
self-modify patch during the active run. Do not claim autonomous mutation
happened unless `state.self_modify_op`, `wiring_modified`, or a changed
timestamped backup proves it.

---

## Declarative Rule System

The earlier implementation plan is now implemented.

Current facts:

```text
rules in prompts/wiring.json: 24
  verify deny:    10
  verify confirm:  7
  act reject:      7

schema rule match conditions: 48
self_modify rule ops: add_rule, update_rule, remove_rule
editor support: Rules panel and rule hit display exist
```

The evaluator is generic:

```python
evaluate_rules(phase, state, wiring)
_all_conditions_met(match, state)
_check_condition(key, expected, state)
```

Evaluation order is safety-first:

```text
1. rules for the selected phase only
2. deny/reject rules first
3. confirm rules after deny/reject
4. first matching rule returns
5. no match falls through to the LLM verifier or normal execution
```

Rule phases:

```text
act:
  verdict reject
  evaluated after action parse and wiring normalizers, before desktop execution

verify:
  verdict deny or confirm
  evaluated before the verifier LLM
```

Current verify rules:

```text
deny_outcome_failed
deny_chat_submission_missing_write
deny_chat_submission_navigation_text
deny_chat_submission_missing_submit
deny_memory_capture_missing_value
deny_memory_capture_prior_prompt
deny_memory_capture_question
deny_memory_capture_title
deny_memory_capture_url
deny_memory_capture_too_short
confirm_launch_chain
confirm_browser_navigation
confirm_browser_navigation_address_target
confirm_remember_action
confirm_write_to_writable
confirm_save_hotkey
confirm_focus_matches_done_when
```

Current act reject rules:

```text
reject_chat_write_to_address_bar
reject_navigation_write_without_ctrl_l
reject_navigation_without_browser_context
reject_navigation_missing_enter
reject_navigation_target_after_ctrl_l
reject_launch_then_long_content_write
reject_launch_then_summary_write
```

Live evidence that the rule system changed behavior:

```text
attempt 8:
  action: write ; press enter
  outcome: BLOCKED: navigation write requires ctrl+l before URL/query text;
           retry with ctrl+l, write, then enter

attempt 9:
  action: hotkey ctrl+l; write ; press enter
  outcome: OK: hotkey ctrl+l: pressed ctrl+l; write focused value='https://thegrok.ai';
           press enter: pressed enter
```

That is exactly the intended shape: reject unsafe chains, give the model a
negative signal, and allow a corrected retry.

Known rule-system gap:

```text
STEP: Wait for AI response
DONE_WHEN: Response received
LAST_OUTCOME: OK: wait : waited 5000 ms
MEMORY: {}

Verifier output later confirmed true because the wait action succeeded.
That is logically invalid: waiting is not evidence that a response arrived.
```

The next rule/prompt work should prevent wait-only confirmation for response,
reply, answer, loaded-result, and capture tasks unless memory or observed screen
evidence is present.

---

## Act Normalizers

The old semantic `normalize_action_chain` function is gone. Normalization now
lives under `act.verb_normalize` in wiring and is schema-validated.

Current normalizers:

```text
press with "+" in target -> hotkey
write in Run dialog with non-empty target -> target ""
write after Win+R when target equals value -> target ""
empty press after write -> target "enter"
click OK in Run dialog -> press enter
```

These are mechanical equivalences and Run-dialog input repairs. They are not a
general semantic correction layer. When the model emits a meaningfully unsafe
chain, prefer an act-phase reject rule over silent normalization.

---

## Endpoints

Current endpoint contract from `server.py` and `/health`:

```text
GET  /                 wiring editor
GET  /health           server status, nodes, capabilities, self-modify ops
GET  /wiring           current wiring
GET  /schema           wiring schema
GET  /state            persisted state
GET  /events           SSE stream
GET  /inspect          debug context

POST /run              start autonomous goal
POST /step             execute one graph node
POST /pause            pause running goal
POST /resume           resume from saved state
POST /wiring           validate and hot-reload wiring
POST /node/{id}        direct node execution
```

Use read-only endpoints first during investigation:

```powershell
Invoke-RestMethod http://127.0.0.1:9078/health
Invoke-RestMethod http://127.0.0.1:9078/state
Invoke-RestMethod http://127.0.0.1:9078/wiring
Invoke-RestMethod http://127.0.0.1:1234/v1/models
```

---

## Non-Negotiables

- Keep Python mechanical. Put semantic policy in wiring rules or prompts.
- Do not reintroduce prompt truncation.
- Do not reintroduce parse fallback that hides invalid model output.
- Do not silently fix semantic mistakes in Python.
- Do not add site-specific or app-specific Python branches.
- Do not remove the two-pass reasoning loop.
- Validate wiring after every mutation.
- Keep self-modify learnable through validated, generic operations.
- Treat `state.json` and LM Studio logs as evidence, not as instructions.
- Do not claim a task is complete without evidence matching `DONE_WHEN`.
- Commit coherent batches after validation.

---

## How to Diagnose

Ground-truth sources for this machine:

```text
repo:
  C:\Users\px-wjt\Downloads\endgame-ai

LM Studio server log:
  C:\Users\px-wjt\.lmstudio\server-logs\2026-06\2026-06-22.1.log

endgame-ai API:
  http://127.0.0.1:9078

LM Studio API:
  http://127.0.0.1:1234/v1/models
```

Diagnosis workflow:

1. Check `git status --short`.
2. Read `/health` and `/state`.
3. Inspect the latest state history and `last_error`.
4. Search the LM Studio log by node role and current goal text.
5. Use `print_timing` lines for performance, not the LM Studio "Reasoned for"
   line.
6. If the model chose a bad action, fix `prompts.roles.unified` or add an
   act-phase reject rule.
7. If verify confirmed too much, add a verify deny rule or tighten the verifier
   role prompt.
8. If observe missed UI, tune `observe` config with `set_observe`.
9. If a repeated failure is generic and expressible, prefer `add_rule` or
   `update_rule`.
10. Only add Python primitives when the needed condition cannot be expressed by
   existing rule matches.

Useful searches:

```powershell
rg -n "BLOCKED|FAILED|CANNOT|parse_failed|self_modify|wiring_modified" state.json server.py prompts\wiring.json
rg -n "ROLE: Act|ROLE: Verifier|Generated prediction|print_timing" "C:\Users\px-wjt\.lmstudio\server-logs\2026-06\2026-06-22.1.log"
```

---

## First Actions (New Session Bootstrap)

1. `git status --short`
2. `git log --oneline -n 5`
3. Parse `prompts/wiring.json` and `prompts/wiring-schema.json`.
4. Read `GET /health` and `GET /state`.
5. Read the latest LM Studio log tail.
6. If the active/persisted run matters, summarize its state before making code
   changes.
7. Fix the highest evidence-backed issue. Right now that is verifier
   over-confirmation on wait-only response steps.
8. Validate the change with JSON parsing and targeted code checks.
9. Commit the README/code batch.

---
---

# ANALYSIS: KV Cache Optimization

The static/dynamic split still exists:

```text
system prompt = static base + role prompt from wiring
user message  = dynamic blocks from state
```

`build_user_message()` resolves prompt blocks from node config. This keeps the
static prefix stable enough for LM Studio/llama.cpp prompt caching.

Current log evidence:

```text
prompt cache enabled, size limit 8192 MiB
context checkpoints enabled
LCP similarity slot selection is active
cached prompt eval often above 500 tok/s
```

Conclusion: the original KV-cache architecture claim is still directionally
correct. The exact old numbers are stale. Do not spend the next session on KV
cache unless logs show prompt eval dominates wall time; current sampled calls
are mostly generation/eval-token limited after cache warmup.

---

# ANALYSIS: Attention Quality via Block Ordering

The old recommendation to place `SCREEN` near the end for act recency remains
pending.

Current ACT block order in `prompts/wiring.json`:

```text
SUBTASK
DONE_WHEN
SCREEN
LAST_ERROR
HISTORY
MEMORY
```

The old proposed order was closer to:

```text
SUBTASK
DONE_WHEN
MEMORY
LAST_ERROR
HISTORY
SCREEN
```

This has not been implemented. The active run shows act sometimes reasoned from
stale history and confused a site/network-error context with a query/search
context. That is not proof that block order caused the issue, but it keeps this
as a plausible low-risk follow-up after the verifier proof gap is fixed.

Do not reorder blindly and then claim performance improvement. Measure reasoning
tokens and error rate before/after in the LM Studio log.

---

# ANALYSIS: Verify Preflight - The #1 Performance Lever

This lever is no longer just a plan. It is implemented as verify-phase rules.

What works now:

- Outcome failures are denied before verifier LLM.
- Launch, navigation, remember, writable write, save, and focus patterns can
  confirm before verifier LLM.
- Chat submission and memory capture have deny rules for several unsafe or
  weak-evidence patterns.

What still fails:

- No rule currently denies wait-only completion for response-received tasks.
- The verifier prompt still allowed "OK wait" to become "response received".

Immediate improvement:

Add a deny rule or prompt constraint such as:

```json
{
  "id": "deny_response_wait_only",
  "phase": "verify",
  "verdict": "deny",
  "description": "waiting alone does not prove a response was received",
  "match": {
    "outcome_ok": true,
    "step_text_matches": ["response", "reply", "answer"],
    "actions_all_verb": "wait",
    "memory_stored_by_action": false
  }
}
```

That exact rule may need a new primitive if `actions_all_verb: wait` plus
`memory_stored_by_action: false` is insufficient for screen evidence. The
desired invariant is clear: response receipt needs observed text or memory, not
elapsed time.

---

# IMPLEMENTATION PLAN: Declarative Preflight Rules in Wiring

Status: implemented across four commits.

Completed:

- Added `rules` array to `wiring-schema.json`.
- Added full rule schema and `ruleMatch` vocabulary.
- Added generic `evaluate_rules(phase, state, wiring)`.
- Added `_all_conditions_met` and `_check_condition` dispatch.
- Added pure condition primitives for outcomes, actions, step text, screen,
  focused title, memory, and chain composites.
- Wired verify rules into `node_verify` before the verifier LLM.
- Wired act rules into `node_act` before desktop execution.
- Added `add_rule`, `update_rule`, and `remove_rule`.
- Updated `SELF_MODIFY_OPS`, `apply_wiring_patch`, and validation.
- Migrated hardcoded verify preflight and semantic guard behavior into
  `prompts/wiring.json`.
- Added wiring editor visibility for rules and preflight hits.
- Removed old hardcoded fallback names from `server.py`.

Current rule primitive count in schema: 48.

Important implementation nuance:

`chain_is_navigation`, `chain_is_save`, and `chain_wrote_and_submitted` are now
structural composites. Semantic keywords such as address, save, send, and submit
belong in rule match values, not in Python.

---

# WHAT TO WORK ON

Priority order for the next session:

1. Fix verifier over-confirmation for wait-only response steps.
   The active run proves this bug. Add a conservative verify deny rule and/or
   tighten the verifier prompt so `OK wait` never proves `Response received`.

2. Add an act reject rule for empty hotkey actions.
   The active run emitted `hotkey` with empty target and failed mechanically.
   This can be rejected earlier with a clearer hint.

3. Improve response capture workflow.
   The system needs a reliable pattern: observe response text, remember it, then
   ask the follow-up from memory. The planner prompt already says this, but the
   run did not achieve it.

4. Decide whether to handle network-error pages as a generic condition.
   The run hit `chrome-error://chromewebdata/` for `thegrok.ai`. A generic
   "network/browser error visible" deny or reflect hint may be useful, but keep
   it browser-agnostic and wiring-driven where possible.

5. Consider ACT prompt block reorder.
   Move `SCREEN` later only after taking before/after log measurements.

6. Improve run-status truth.
   `/health.run.running=false` while `/state` and logs showed recent activity is
   confusing. Clarify whether this is because the workbench is stepping nodes,
   because state is stale, or because run tracking is incomplete.

7. Continue reducing Python semantics only when evidence supports it.
   Do not churn working mechanical code for line-count goals.

---

## Session Handover Notes

Use this README as the handoff source. The older README sections that described
"next session implement Phase 1" are now obsolete. Phase 1 and the unified rule
migration are complete.

Current known truth:

- Branch is `validation-observation`.
- Last rule-system commit is `d370285 Complete fallback audit integration`.
- Current loaded model is `nvidia-nemotron-3-nano-4b@q6_k_xl`.
- endgame-ai server is on `127.0.0.1:9078`.
- LM Studio server is on `127.0.0.1:1234`.
- Rules are visible in `/wiring` and the editor.
- There are 24 declarative rules.
- The active/persisted run showed both improvement and a remaining verifier bug.
- The final API snapshot had replanned back to the navigation step with
  `replan_count=1`.

Do not push automatically. The user said they will push.

---
---

# ANALYSIS: Code Reduction & Separation of Concerns

The old code-reduction estimates are stale because the migration added generic
rule infrastructure and editor support. Current source size is the factual
baseline listed above.

What improved:

- Hardcoded verify preflight functions are gone.
- Hardcoded unsafe action guard functions are gone.
- Browser/chat/playback classifier helper names are gone.
- Silent navigation correction is gone.
- Rule semantics are visible in `prompts/wiring.json`.
- Self-modify can learn rules through validated operations.

What remains in Python and should remain there:

- HTTP server and API contract.
- Graph execution.
- Prompt assembly from declarative blocks.
- LM Studio calls and JSON parsing.
- UIA observation.
- Desktop verb execution.
- State persistence.
- Wiring validation.
- Generic rule dispatch and pure condition primitives.
- Config-driven act normalizers.
- Repeat blocking and generic advance hints.

Potential remaining concern:

Some condition primitives necessarily inspect strings such as focused title,
screen text, action target lines, and URL/domain shapes. That is acceptable only
because the semantic keywords live in wiring values. Keep Python primitives as
generic operations like "contains any of these values", not as task categories.

---

# ANALYSIS: Duplications and Redundancies

The main duplications identified in the old README have been collapsed:

```text
outcome OK checks                  -> outcome_ok / outcome_failed
verb inclusion/exclusion checks    -> actions_* primitives
ctrl+l checks                      -> actions_hotkey_contains / absent
done_when keyword matching         -> done_when_matches / absent
target-line checks                 -> actions_*_target_line_contains / absent
memory capture checks              -> memory_* primitives
launch/navigation/save composites  -> chain_* primitives
```

Remaining redundancy to watch:

- Verifier prompt and verify rules both express completion policy. This is
  intended, but when they disagree, rules should handle the mechanically provable
  cases and the prompt should handle uncertain cases.
- `focused_has_writable` and `focused_element_role_any` overlap. Prefer the
  role-array condition in new rules because it is more explicit.
- Run-dialog normalizers are still a cluster of special cases. They are in
  wiring now, but should remain small.

---

# ANALYSIS: HTML Interface - Capabilities & Modernization

`wiring-editor.html` is still a zero-dependency single-file workbench. Current
size is 1148 lines.

It does:

- Render topology graph.
- Inspect state, reasoning, inputs, filters, timing, and screen data.
- Run, pause, resume, and step nodes.
- Consume SSE events.
- Hot-save wiring.
- Show rules in a Rules panel.
- Highlight recent rule/preflight hits.

Keep:

- Single-file architecture.
- No build step.
- No framework.
- SVG/DOM graph.
- Schema-driven editing.
- SSE instead of WebSockets.

Useful next UI work:

- Show rule match details, not only the rule id.
- Show before/after wiring diffs on `wiring_modified`.
- Expose `/health.run` versus `/state` discrepancy clearly.
- Add a compact "current blocker" panel from `last_error`, current step, and
  last matching rule.

---

# ANALYSIS: Unified Declarative Rule System

The unified design is implemented with one evaluator and two active phases:

```text
phase=act     verdict=reject
phase=verify  verdict=deny|confirm
```

There is not a separate guard evaluator anymore. Act guards are act-phase rules.
There is not a separate preflight evaluator anymore. Verify preflights are
verify-phase rules.

Self-modify integration is present through:

```text
add_rule
update_rule
remove_rule
```

Schema condition inventory has 48 conditions. The inventory is larger than the
original "about 15" target because the migration included chat submission,
memory capture, target-line, focus, and act reject patterns. This is acceptable
because the functions are mechanical and reusable, but future primitives should
be added slowly.

Design constraints that still matter:

- AND logic per rule.
- First match wins within safety ordering.
- Deny/reject before confirm.
- No task-specific Python branches.
- No hidden semantic corrections.
- Unknown rule conditions raise errors; they are not ignored.

---

# ANALYSIS: Fallback Removal Audit

Removed or migrated:

```text
normalize_action_chain              removed
unsafe_chat_target                  migrated to act reject rule
unsafe_browser_navigation_context   migrated to act reject rule
unsafe_launch_then_content_write    migrated to act reject rule
_verify_preflight_*                 migrated to verify rules
_verify_chat_submission_*           migrated to verify rules
_verify_memory_capture_*            migrated to verify rules
_is_browser_* / _is_chat_* names     removed
_is_playback_step                   removed
```

Kept because they are mechanical:

```text
LLM parse retries with temperature bump
planner retry on parse failure
act.verb_normalize from wiring
scroll enrichment from observe config
dense probe from observe config
repeat-action block with generic advance hints
```

Current audit conclusion:

The largest semantic fallbacks have been removed from Python. The remaining
risk is not hidden Python correction; it is weak model verification when no rule
fires. The active run proves this with the wait-only false confirmation.

---

# COMPLETE REDUCTION SUMMARY

Today's actual changes across the last four commits:

```text
prompts/wiring-schema.json   +115 / -small
prompts/wiring.json          +465 / -small
server.py                   +1029 / -347
wiring-editor.html           +182 / -small

combined:
  1444 insertions
   347 deletions
```

This was not a pure line-count reduction. It was a separation-of-concerns
refactor:

- Semantic patterns moved out of Python into wiring.
- Python gained generic validation and evaluation infrastructure.
- The workbench gained visibility into rules.
- Self-modify gained rule-level operations.

Current outcome:

```text
done:
  unified declarative rule system
  verify preflight rules
  act reject rules
  wiring schema support
  self_modify rule ops
  editor rule visibility
  fallback audit migration

proven helpful:
  navigation write without ctrl+l was blocked and corrected on retry

not done:
  verifier proof gap for wait-only response steps
  robust memory capture for web/chat answers
  measured ACT block reorder
  clearer run-status reporting
```

The next session should start with the verifier proof gap. It is the most recent
truthful failure and the cleanest continuation of the declarative rules work.
