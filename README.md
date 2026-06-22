# endgame-ai

A self-rewiring local Windows desktop organism. It observes the screen through UIA, plans through an LLM-driven ROD loop, executes mechanical actions, verifies outcomes, reflects on failures, and mutates its own `prompts/wiring.json` through validated patches.

This README is the source of truth for humans and for any AI continuing the project.

Last verified: 2026-06-22 (pipeline efficiency pass).

## Architecture

```
Python = mechanical body (observe, execute, validate, hot-reload)
prompts/wiring.json = mutable brain (topology, prompts, guards, limits, observe filters)
Local 4B LLM = semantic judgment (via LM Studio)
wiring-editor.html = live workbench (graph, state, SCREEN, SSE)
```

Central rule: **do not make Python smarter about tasks. Make Python better at exposing facts and applying validated wiring mutations.**

## File Map

| File | Purpose |
| --- | --- |
| `server.py` | HTTP API, ROD graph runner, node handlers, prompt assembly, self-modify patch engine, validation |
| `desktop.py` | Win32/UIA observation, element probing, hover scan, SCREEN rendering, scope/filter logic |
| `actions.py` | Data-driven verb dispatch (click, write, press, hotkey, scroll, focus, remember, wait) |
| `colony.py` | Multi-instance colony manager (spawns slots sharing bus.json) |
| `wiring-editor.html` | No-build single-file workbench UI |
| `prompts/wiring.json` | Mutable topology, prompts, guards, limits, observe config |
| `prompts/wiring-schema.json` | JSON Schema for wiring validation |
| `prompts/model.json` | LM Studio connection config |
| `prompts/traces.jsonl` | Completed goal traces for few-shot planner context |
| `bus.json` | Inter-slot colony message bus |
| `state.json` | Persisted run state (auto-saved on SIGINT/SIGTERM) |

## ROD Loop

```
goal_inbox → moe_route → planner → scheduler → bus_check → observe → act → verify → scheduler (loop)
                                                                         ↓ fail
                                                                       reflect → retry | replan | escalate
                                                                                                    ↓
                                                                                              self_modify → planner (hot-reloaded)
```

### Node Responsibilities

| Node | Uses LLM | Sees SCREEN | Job |
| --- | --- | --- | --- |
| `planner` | yes | no | Goal → ordered subtasks |
| `observe` | no | captures | Build SCREEN from UIA |
| `act` | yes | yes | Emit verb chain or remember |
| `verify` | yes | no | Confirm or deny step from evidence |
| `reflect` | yes | no | Diagnose failure → retry/replan/escalate |
| `self_modify` | yes | no | Emit one validated `wiring_patch` |

### Signals and Edges

```
planner → plan_ready → scheduler
scheduler → step_ready → bus_check → no_interrupt → observe
observe → screen_ready → act
act → acted → verify | act_failed → reflect
verify → step_confirmed → scheduler | step_denied → reflect
reflect → retry → scheduler | replan → planner | escalate → self_modify
self_modify → modified → planner | modify_failed → reflect
scheduler → plan_complete → bus_post → posted → satisfied
```

## Observation Pipeline

1. `desktop.py Desktop.observe()` does a single full-screen cursor probe (hover scan)
2. When `hover_scan_enabled=true`, one pass replaces separate primary + overlay + hover passes
3. Elements are classified by scope: focused page → focused chrome → overlay → background
4. `_render()` builds SCREEN text with configurable filters
5. SCREEN goes into `state["screen"]` and is passed to `act` prompt

### Current Observe Config

```json
{
  "scope_depth": 4,
  "element_text_max": 500,
  "render_focused_first": true,
  "render_class_name": false,
  "render_automation_id": true,
  "render_window_per_element": false,
  "desktop_tree_enabled": false,
  "desktop_tree_max_depth": 6,
  "desktop_tree_max_nodes": 900
}
```

**Render filters** (added 2026-06-22):
- `render_class_name: false` — suppresses CSS class names from rendered text (saves ~30% per element line)
- `render_automation_id: true` — keeps short UIA automation IDs (useful for disambiguation)
- `render_window_per_element: false` — window title shown only in FOCUSED header, not per element
- `desktop_tree_enabled: false` — disables 26KB desktop tree section (model works fine without it)

**Result**: SCREEN dropped from 37KB to ~6KB for same observation depth. The 4B model completes goals that previously timed out.

### Scope Depth Buckets

| Value | Includes |
| ---: | --- |
| 1 | focused page |
| 2 | + focused chrome |
| 3 | + overlays |
| 4 | + background |

## Prompt Contract

The local model is nvidia-nemotron-3-nano-4b (4B params, ~6GB VRAM). Prompts must be compact and schema-first.

### Current Prompt Sizes

| Prompt | Chars |
| --- | ---: |
| base | 863 |
| planner | 972 |
| act/unified | 1724 |
| verifier | 974 |
| reflector | 834 |
| self_modify | 1648 |
| **total** | **7015** |

### Prompt Rules

- Preserve exact JSON output schemas
- Keep base under ~1000 chars, roles under ~2000 chars
- Put task semantics in wiring prompts/guards, not Python
- Use concrete node prompt config for circuit-specific variants
- Do not reintroduce stale architecture claims

## Self-Rewiring

```
reflect (escalate) → self_modify → apply_wiring_patch → validate → backup → write → hot-reload → continue
```

### Supported Patch Ops

```
add_node, update_node, remove_node, add_edge, remove_edge,
set_guard, set_limit, set_observe,
set_prompt_base, set_role, append_role_rule, set_reasoning
```

### Patch Policy

- `set_observe` for missing/noisy/shallow SCREEN data (writes to `observe` config)
- `set_limit` for numeric caps (writes to `limits` section — max_attempts, max_replans, etc)
- `append_role_rule` for repeated reasoning mistakes
- `set_guard` for repeated mechanical loops
- Topology edits only for real graph-structure problems
- Never remove core routes unless same patch replaces them

### Backups

Written before every self_modify mutation:
```
prompts/wiring.backup.json
prompts/wiring.backup.YYYYMMDD-HHMMSS.json
```

## LLM Configuration

```json
{
  "host": "http://localhost:1234",
  "model": "nvidia-nemotron-3-nano-4b",
  "temperature": 0.3,
  "temperature_bump": 0.15,
  "timeout": 900,
  "max_tokens": 2048
}
```

The server uses a two-pass LLM call for each node:
1. Reasoning pass: system + user → reasoning_content
2. Decision pass: system + user + reasoning → content JSON

## HTTP API

```
GET  /                  workbench
GET  /health            status, capabilities, self_modify_ops
GET  /wiring            current wiring
GET  /wiring-schema     schema
GET  /state             saved state
GET  /bus               bus messages
GET  /events            SSE stream
POST /step              execute one graph node
POST /run               enqueue autonomous run
POST /resume            resume saved state
POST /pause             pause run
POST /state             overwrite state
POST /wiring            validate and hot-reload full wiring JSON body
POST /node/{type}       execute one handler directly
POST /bus/post          append bus message
POST /interrupt         inject goal
POST /push              send SSE push
```

## Workbench

`wiring-editor.html` — zero-dependency single-file UI with:
- Goal entry, new session, observe, step, continue, pause
- Load/save state, hot-save wiring
- Graph editor (Canvas2D)
- Live SCREEN panes, filter sliders
- State, plan, history, reasoning, JSON, schema, log tabs
- SSE event log and state refresh

## Runbook

### Start the server

```powershell
python "C:\Users\px-wjt\Downloads\endgame-ai\server.py"
```

Or hidden:
```powershell
Start-Process -FilePath python -ArgumentList "C:\Users\px-wjt\Downloads\endgame-ai\server.py" -WorkingDirectory "C:\Users\px-wjt\Downloads\endgame-ai" -WindowStyle Hidden
```

### Stop the server

```powershell
Get-NetTCPConnection -LocalPort 9078 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

### Hot-reload wiring

```powershell
Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:9078/wiring' -InFile 'prompts\wiring.json' -ContentType 'application/json'
```

### Verification checks

```powershell
git status --short
python -m compileall -q .
python -c "import json; json.load(open('prompts/wiring.json',encoding='utf-8')); json.load(open('prompts/wiring-schema.json',encoding='utf-8')); print('json ok')"
git diff --check
Select-String -Pattern 'SCREEN_TRUNCATED_FOR_PROMPT|prompt_screen_max_chars|node_value_max_chars|render_value_max_chars|parse_fallback' -Path prompts\wiring.json,server.py,desktop.py,actions.py,prompts\wiring-schema.json
(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9078/health').Content
```

## Proven Capabilities

- [x] UIA observation with configurable render filters
- [x] Full ROD loop: plan → observe → act → verify → satisfied
- [x] Self-modify cycle: LLM emits wiring_patch → validate → backup → hot-reload
- [x] Mechanical verb execution (click, write, press, hotkey, scroll, focus, wait, remember)
- [x] SCREEN from 37KB to 6KB with render filters (model completes goals that previously timed out)
- [x] Single-pass observation: 405 probe points vs 1538 (73% fewer, ~3x faster)
- [x] Verify preflight eliminates wasted LLM calls for structurally obvious outcomes
- [x] First autonomous desktop goal completed: open notepad + write text
- [x] Compact prompts for 4B model (~7KB total)
- [x] SIGINT/SIGTERM state persistence
- [x] SSE live updates to workbench
- [x] Colony multi-slot architecture (implemented, not yet stress-tested)

## Current Limitations

- The two-pass LLM call (reason + decide) is slow on the 4B model (~30-60s per node)
- Simple 1-step goals still take ~3 min due to planner+act two-pass overhead
- The model typed "hello" instead of "hello from endgame" — verification was too lenient
- No formal test suite yet
- `server.py` is 84KB — still mixes graph runtime, HTTP, prompt plumbing, and guards
- Desktop tree is disabled; some complex window-switching goals may need it back

## Non-Negotiable Constraints

- Do not reintroduce SCREEN prompt truncation
- Do not reintroduce `parse_fallback`
- Do not add site-specific Python branches
- Do not hide errors with `except/pass`
- Do not make Python infer task semantics
- Use wiring prompts/guards for semantic behavior
- Validate and hot-reload wiring after mutations
- Commit regularly

## Handover Session Prompt

```text
You are continuing endgame-ai in C:\Users\px-wjt\Downloads\endgame-ai.

Read README.md first. Treat it as the source of truth unless current code or HTTP /health proves it stale. If stale, update README before closing.

Vision:
Local Windows desktop organism. Python = mechanical body. prompts/wiring.json = mutable brain. Local 4B LLM = semantic judgment. The system observes, acts, verifies, reflects, and self-rewires through validated wiring patches.

Current reality (verified 2026-06-22):
- Render filters reduce SCREEN from 37KB to ~6KB: render_class_name=false, render_window_per_element=false, desktop_tree_enabled=false.
- First autonomous goal completed (open notepad + write text) with the lean 6KB observation.
- Self-modify cycle exercised: LLM emitted wiring_patch, patch applied, backup created, hot-reload worked.
- Two-pass LLM call (reason + decide) takes 30-60s per node on 4B model.
- Prompt total ~7KB across base + 5 roles.
- POST /wiring expects full JSON body and validates before hot-reload.
- /health exposes self_modify_ops.

Non-negotiables:
- Do not reintroduce prompt_screen_max_chars or SCREEN_TRUNCATED_FOR_PROMPT.
- Do not reintroduce parse_fallback.
- Do not add task/site-specific Python branches.
- Do not hide errors with except/pass.
- Keep Python mechanical.
- Put semantic fixes in wiring prompts or guards.
- Validate wiring after every mutation.
- Hot-reload or restart the server using the absolute server.py path.
- Commit every coherent verified batch.

Immediate next goal: Further pipeline efficiency.
Current: simple goals take ~3 min (planner two-pass + act two-pass). The two-pass
reasoning loop is core and stays, but planner overhead for trivial 1-step goals
is avoidable.

Analyze the LM Studio server log for the most recent runs:
  C:\Users\px-wjt\.cache\lm-studio\server-logs\2026-06\<latest>.log
Key metrics (4B Nemotron Q6 on GPU):
- Prompt eval: ~73-125 tok/s
- Generation: ~6.4 tok/s
- Two-pass act call: ~90s (pass 1) + ~66s (pass 2) = 156s for one act cycle

Determine:
- Whether planner can be bypassed for goals with a single obvious action
- Whether the act prompt can be more compact to reduce prompt eval time
- Whether reasoning chain from planner bloats the act prompt unnecessarily

Done (2026-06-22):
- Single-pass observation (was 1538 points, now 405 at 70px step)
- Verify preflight strengthened: Win+R pattern confirms without LLM (saved 163s)
- Result: simple goals went from 6 LLM calls to 4, wall time ~27% faster

Fix approach:
- If planner is redundant for direct goals, add a guard that skips it.
- If act prompt is too large, trim reasoning chain or history injection.
- Do not remove reasoning feedback — it's core.
- Do not add task-specific Python. Keep changes mechanical and wiring-driven.

First actions:
1. Run git status --short.
2. Run compileall, JSON parse, git diff --check, stale-key scan.
3. Confirm /health and /wiring.
4. Read the LM Studio server log for the most recent run.
5. Analyze token counts, timing, and wasted calls.
6. Propose and implement one pipeline efficiency improvement.
7. Test with a simple goal.
8. Update README and commit.

When something fails:
- If the model lacked data, fix observation/rendering/filters.
- If the model had wrong policy, patch prompts/wiring.json.
- If graph flow was wrong, patch topology/guards/limits.
- If mechanics failed, patch Python mechanically.
- Do not add one-off app or site hacks.

Deliverable:
One verified pipeline efficiency improvement, README updated, commit.
```

## Decision Rules for Future Sessions

- If the model lacked data → fix observation/rendering/filters
- If the model had wrong policy → patch `prompts/wiring.json`
- If graph flow was wrong → patch topology/guards/limits
- If mechanics failed → patch Python mechanically
- If the fix names one website/app/text literal → it belongs in prompt policy or not at all

## Session Close Checklist

- [ ] README updated when reality changed
- [ ] Wiring validates (`POST /wiring` returns 200)
- [ ] Server reports healthy (`GET /health`)
- [ ] Current limitations stated directly
- [ ] Commit exists for the coherent batch
