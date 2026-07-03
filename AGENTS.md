# AGENTS.md — endgame-ai forensic instructions (chunk 1/6)

## Project Identity & Vocabulary

```
Python = body
desktop = world
wiring.json = nervous system
JSON records = bus
state.json = memory
runtime logs = nervous trace
Grok / LLM calls = reasoning organs
git = firmware memory
contract_check.py = immune system
```

**Do not reduce the project to "an agent."** The point is a graph of specialized organs that control a real desktop, verify reality, reflect after failure, and self-evolve through git under strict immune validation.

---

## Two Runs Identified (Forensic Evidence)

### Run A: The Destructive Self-Evolution Run (t=1783103923-1783104060)
- **Goal**: "Make a fast public demo... Use Opera browser only... find fresh AI news... publish X post... publish LinkedIn post... start ASCII chess with Grok"
- **Duration**: ~137 seconds
- **Total xAI Calls**: 13 brain calls (planner=1, execute=3, verify=3, reflect=2, self_modify=2, frame_action=0)
- **Signals**: step_ready→execute→verify(step_denied)→reflect(retry)→observe→execute→verify(step_confirmed)→scheduler→observe→execute→verify(step_denied)→reflect(retry)→...→reflect(escalate)→self_modify→ERROR(corrupt patch)
- **Stop Reason**: `git apply --check` failed: "corrupt patch at line 40" in self_modify unified diff
- **Cost**: ~939,503,000 USD ticks (≈$0.94) for self_modify call alone; total run ≈$2.50+
- **Failure Mode**: Self-modify produced syntactically valid but semantically broken diff (corrupt patch format). Immune system (contract_check.py) did NOT run because git apply failed first.

### Run B: The Post-Crash Retry Run (t=1783104076-1783104226)
- **Goal**: Same as Run A (organism restarted with same goal)
- **Duration**: ~150 seconds
- **Calls**: 14 brain calls (planner=1, execute=5, verify=5, reflect=3, self_modify=1)
- **Signals**: step_ready→execute→verify(step_denied)→reflect(retry)→observe→execute→verify(step_denied)→reflect(retry)→observe→execute→verify(step_denied)→reflect(retry)→observe→execute→verify(step_denied)→reflect(escalate)→self_modify→ERROR(corrupt patch at line 68)
- **Stop Reason**: Second `git apply --check` failed: "corrupt patch at line 68"
- **Cost**: ~977,465,500 USD ticks (≈$0.98) for second self_modify call
- **Failure Mode**: Same corrupt patch format issue. The self_modify organ generates unified diffs with malformed headers/line numbers.

---

## Critical Forensic Findings

### 1. The "Corrupt Patch" Root Cause
Both self_modify calls produced unified diffs that `git apply --check` rejected. The diffs had:
- Correct `diff --git a/desktop.py b/desktop.py` header
- But malformed chunk headers (`@@ -1400,30 +1400,20 @@ class Desktop:`) — line numbers likely wrong for current file state
- The self_modify organ hallucinates line numbers without reading the actual current file

### 2. The App Launch Race (Confirmed in Run A)
- t=1783103941: execute launches Opera via subprocess
- t=1783103946: verify runs immediately, sees NO Opera window (only PowerShell, Program Manager)
- t=1783103948: verify emits step_denied
- t=1783103956: observe runs again, NOW sees "Grok - Opera" focused
- **No configurable delay between execute and observe** — this is a systemic flaw

### 3. Shallow Desktop Tree (Confirmed)
- Hover scan `target_window_only=true` with `step_px=64` only captures window-level + immediate children
- No deep recursion into Chrome/Opera DOM — cannot see "Ask Grok anything" Edit control, X.com composer, etc.
- Execute generates hardcoded coordinates because tree lacks actionable element IDs

### 4. Opportunistic Progress Without Step Advance
- At t=1783103958, execute sees Opera focused but scheduler step still "Launch Opera"
- Execute returns `result = {'opera_visible': True...}` instead of launching
- Verify at t=1783103965 confirms step (because Opera now visible)
- But step_index never formally advanced — the organism "got lucky" but protocol didn't track it

### 5. Self-Modify Generates Compiling Stubs (Historical)
From HANDOVER.md: Prior run replaced `desktop.py`/`execute.py` with stubs that compiled but amputated body. This is WHY contract_check.py exists — but it never ran because git apply failed first.

### 6. No Frame_Action Usage
- `frame_action` node exists in topology with edges `execute.frame→frame_action` and `frame_action.framed→execute`
- NEVER triggered in either run (0 calls)
- Execute goes straight to verify or reflect

---

## Cost Summary

| Run | Planner | Execute | Verify | Reflect | Self_Modify | Total Tokens | Est. Cost |
|-----|---------|---------|--------|---------|-------------|--------------|-----------|
| A   | 2,771   | ~6,500  | ~4,100 | ~4,900  | 68,317 + 69,964 | ~156,552 | ~$2.50+ |
| B   | ~2,771  | ~10,000 | ~6,800 | ~7,300  | 69,964       | ~166,799 | ~$2.70+ |

**Self-modify dominates cost** (68k-70k tokens each = ~45% of total) because it receives full workspace manifest + source fingerprints + immune contract + web_search enabled.
# AGENTS.md — endgame-ai forensic instructions (chunk 2/6)

## Architecture Overview (Verified from Code)

### Topology (from wiring.json → organism.py:next_node_for)
```
planner → scheduler → observe → execute → verify → (step_confirmed→scheduler | step_denied→reflect)
reflect → (retry→observe | replan→planner | escalate→self_modify | give_up→satisfied)
self_modify → (modified→planner | modify_failed→reflect | error→error)
error → (planner | reflect | halt)
frame_action: execute.frame → frame_action → (framed→execute | reflect→reflect | error→error)
```

### Key Entry Points (Verified)
- `organism.py:run()` — main loop, enforces `wait_before_node` for pause/step control
- `nodes.py:call_node()` — hot-swappable node loader, emits `bus.NodeOutput`
- `brain.py:think()` — ROD brain pattern (reasoning → second pass with reasoning feedback)
- `desktop.py:observe()` — primary sensor, uses UIA COM hover scan

### The Organism Loop (Verified Timeline from Run A)

| Tick | Time | Node | Signal | Key Event |
|------|------|------|--------|-----------|
| 0 | 1783103923.66 | planner | step_ready | Creates 5-step plan (Opera→Grok→X→LinkedIn→Chess) |
| 1 | 1783103938.90 | scheduler | step_ready | Selects step 0: "Launch Opera" |
| 2 | 1783103938.92 | observe | screen_ready | Fresh hover scan (Program Manager focused) |
| 3 | 1783103941.13 | execute | verify | Launches Opera via subprocess.Popen |
| 4 | 1783103946.39 | verify | step_denied | No Opera in desktop_tree (race!) |
| 5 | 1783103948.36 | reflect | retry | Diagnoses timing gap |
| 6 | 1783103956.59 | observe | screen_ready | Opera NOW visible (Grok - Opera focused) |
| 7 | 1783103958.18 | execute | verify | Sees Opera, returns success without action |
| 8 | 1783103963.31 | verify | step_confirmed | Confirms Opera launched |
| 9 | 1783103965.61 | scheduler | step_ready | Advances to step 1: "Query Grok for news" |
| 10 | 1783103965.62 | observe | screen_ready | Scan Opera window |
| 11 | 1783103966.56 | execute | verify | Types query into "Ask Grok anything" |
| 12 | 1783103972.46 | verify | step_confirmed | Confirms query sent |
| 13 | 1783103974.00 | scheduler | step_ready | Advances to step 2: "Navigate to x.com" |
| 14 | 1783103974.90 | observe | screen_ready | Scan Opera |
| 15 | 1783103974.90 | execute | verify | Calls open_url('opera', 'https://x.com') |
| 16 | 1783103979.84 | verify | step_denied | open_url fabricated success, still on Grok tab |
| 17 | 1783103981.81 | reflect | retry | Diagnoses open_url broken |
| ... | ... | ... | ... | Repeated retries fail |
| 18 | 1783104157.14 | reflect | escalate | Triggers self_modify |
| 19 | 1783104166.32 | self_modify | error | **Corrupt patch at line 40** |

---

## Bus Contract (Verified from bus.py + nodes)

### NodeOutput Structure
```python
@dataclass(frozen=True)
class NodeOutput:
    signal: str                    # Must exist in wiring.json topology edges
    patch: JsonDict = {}           # State updates
    record: JsonDict | None = None # LLM output with record_type + data
    evidence: JsonDict = {}        # Debug context
```

### Signal Validation
- `bus.validate_signal(wiring, node_name, signal)` — raises if signal not in topology edges
- Every LLM node inherits `BaseNode` with `prompt_key`, `expected_record_type`, `signal_from_data()`, `patch_from_record()`

### Record Schemas (from brain.py:_RECORD_DATA_SCHEMAS)
| record_type | Required data fields |
|-------------|---------------------|
| plan | next_signal, intent[] |
| execution | conclusion, code |
| verification | next_signal, success, reasoning |
| reflection | next_signal, lesson, diagnosis |
| git_evolution_patch | summary, rationale, read_files, unified_diffs, file_writes, file_deletes, wiring_patches, commands, expected_validation |
| satisfied | next_signal: "halt" |

---

## Critical Conventions (Verified from Code)

### 1. Pause/Step Control is EXTERNAL
Edit `comms/control.json`:
```json
{"mode": "pause", "step_token": 0}   # pause before next node
{"mode": "step", "step_token": 1}    # advance one node
{"mode": "run"}                      # resume
```
Organism polls at `organism.py:wait_before_node`. **Do not add sleeps in code.**

### 2. Transport Selection = Fail-Hard
`wiring.json:model.transport = "xai"` — exactly one transport, no fallbacks.
Per-organ tuning in `model.organs.{plan,action_frame,execution,verification,reflection,git_evolution_patch,satisfied}`

### 3. Stable Prefix = Source Grounding
`brain.py:StablePrefix` builds git `ls-files` snapshot of all `.py/.json/.md` + special names.
Only included for organs with `stable_prefix.enabled=true` OR `for_record_types` match (default: `git_evolution_patch`)

### 4. Stop Mechanism
`stop_check.py` — `stop.txt` in repo root signals all processes to exit.
`register_pid(name)` writes `pids/{name}.pid`
Call `check_stop("context")` at chokepoints.
# AGENTS.md — endgame-ai forensic instructions (chunk 3/6)

## Self-Modification Pipeline (Verified from nodes.py + organism.py)

### Trigger Chain
```
reflect.escalate → self_modify node runs → nodes.apply_evolution_patch() → 
nodes.commit_self_evolution() → git commit [+ push] → reload wiring
```

### apply_evolution_patch() Validation Steps (Exact Order)

1. **Parse patch** from `git_evolution_patch` record data
2. **Validate read_files declared** for ALL touched existing files
3. **Validate unified_diffs** — each diff must name repo files, touched files must be in read_files
4. **Validate file_writes** — only for NEW files or non-protected supporting files
5. **Validate file_deletes** — protected files (CORE_FILES, organism_nodes/*, brain_transports/*) cannot be deleted
6. **Validate wiring_patches** — only allowed prefixes from `self_modify.wiring_allowed_new_prefixes`
7. **Snapshot all touched paths** for rollback
8. **Apply unified diffs** via `git apply --check` then `git apply`
9. **Write new files** atomically
10. **Apply wiring patches** in-memory + save wiring.json
11. **Compile-check** all modified `.py` files
12. **Run contract_check.py** (IMMUNE SYSTEM — critical!)
13. **Run user commands** (must include `python contract_check.py`)
14. **Re-run contract_check.py** after commands
15. **Commit + optional push** to origin

### Protected Files (Require Unified Diffs, Not Full Rewrites)
- `organism_nodes/*.py`
- `brain_transports/*.py`
- CORE_FILES: `brain.py`, `bus.py`, `desktop.py`, `nodes.py`, `organism.py`, `stop_check.py`, `contract_check.py`, `wiring.json`

### Immune System: contract_check.py (Verified)

**Validates:**
1. Required files exist + meet minimum byte sizes
2. AST-checks required top-level defs/classes in core modules:
   - `brain.py`: `think`, `load_json`, `atomic_write_json`, `append_ndjson`, `root_path`, `last_fresh_observation`
   - `bus.py`: `emit`, `coerce_node_output`, `validate_signal`, `datasheet`, `state_brief`, `observation_brief`, `update_failure_streak`
   - `desktop.py`: `get_desktop`, `observe`, `observe_screen`, `last_desktop_tree`, `last_action_index`, `get_focused_title`, `Desktop` class with 11 methods
   - `nodes.py`: `call_node`, `apply_evolution_patch`, `commit_self_evolution`, `prepare_self_evolution`, `build_capability_runtime`, `git_head_sha`, `git_worktree_status`
   - `organism.py`: `run`, `main`, `next_node_for`, `write_state`, `runtime_event`
3. All topology nodes exist + have `run(ctx)` + `DATASHEET`
4. All topology edges reference known nodes
5. Per-organ model tuning keys valid (`reasoning_effort` in {none,low,medium,high}, `max_output_tokens` ≥ 200, `temperature` 0-2)
6. `self_modify.web_search.enabled=true` + required domains (github.com, raw.githubusercontent.com)

**FAILS THE RUN IF ANY CHECK FAILS** — this is the immune system.

---

## The Corrupt Patch Bug (Forensic Finding)

### What Happened in Both Runs
Self-modify generated unified diffs with:
- Correct file path: `diff --git a/desktop.py b/desktop.py`
- **Wrong line numbers in chunk header**: `@@ -1400,30 +1400,20 @@ class Desktop:`
- The self_modify organ **hallucinates line numbers** without reading the actual current file state
- `git apply --check` rejects with "corrupt patch at line 40" / "corrupt patch at line 68"

### Why This Is Critical
1. **contract_check.py never runs** — git apply fails first
2. **Self-modify cannot actually evolve the organism** — both runs died here
3. **The organ has no feedback loop** — it doesn't learn from the git apply failure

### Root Cause in Code
`nodes.py:apply_evolution_patch()` calls:
```python
for args in (["apply", "--check", "--whitespace=nowarn", "-"], ["apply", "--whitespace=nowarn", "-"]):
    cp = subprocess.run(["git", *args], cwd=ROOT, input=diff_text, ...)
```
But self_modify never receives the git apply error to retry with corrected line numbers.

### Fix Required
Self-modify must either:
- Read the actual file first to compute correct line numbers, OR
- Use a different patch format (e.g., full file replacement for small files), OR
- Catch git apply failure and retry with corrected patch

---

## Web Search in Self-Modify (Verified)
- `wiring.json:model.transport_config.xai.web_search.enabled = true`
- Allowed domains: `github.com`, `raw.githubusercontent.com`, `api.github.com`
- Passed via `request_config={"web_search": ...}` in brain.think() call
- **Advisory only** — local repo + contract_check.py are authoritative
# AGENTS.md — endgame-ai forensic instructions (chunk 4/6)

## Desktop Observation System (Verified from desktop.py)

### observe(config) → Fresh Hover Scan
Returns:
- `desktop_tree_text` — semantic indented tree for brain consumption
- `focused_title` — window title of foreground window
- `observation_artifact` — path to raw JSON in `comms/observations/`
- `fresh_scan: true` — always fresh in this version

### Hover Scan Configuration (from wiring.json:observe_config.observe_config.hover_scan)
```json
{
  "mode": "cursor_hover",        // "cursor_hover" (moves mouse) or "point_probe" (no move)
  "restore_cursor": true,
  "step_px": 64,                 // grid step in pixels
  "delay_ms": 1,                 // delay between probes
  "target_window_only": true,    // CRITICAL: only scans foreground window
  "min_size_px": 6,
  "max_elements": 240,
  "full_screen_step_px": 64
}
```

### Tree Depth = FLAT (Window → Direct Children Only)
**No deep recursion into nested elements.**
- Chrome/Opera: only sees Window → Pane/Group → maybe 1-2 levels
- Cannot see: "Ask Grok anything" Edit, X.com composer, LinkedIn editor, etc.
- Action elements only at window-immediate-child level

### Scan Modes Observed in Logs
1. **Full screen** (`target_window_only=false`): 13 raw elements, 1 actionable (Desktop List)
2. **Target window** (`target_window_only=true`): 3-11 raw elements, 0-4 actionable
3. **Opera with Grok**: 0 actionable elements (Chrome DOM not penetrated)
4. **GitHub Desktop**: 7-8 actionable (Buttons, ComboBoxes, Document)

### Critical Bug: No Delay Between Execute → Observe
**Code path**: `organism.py:run()` → `execute` node completes → immediately `verify` node → `observe` node
**No configurable wait** for app launch / page load
**Result**: Verify runs before app appears → step_denied → reflect/retry → works on 2nd observe
**Fix needed**: Add `post_execute_delay_ms` in wiring.json, consumed by organism loop

### Observation Artifacts
Each observe writes `comms/observations/{timestamp_ms}.json` with:
- Full raw UIA element tree
- Semantic desktop tree (brain-facing)
- Action index (body-facing targeting data: px, py, hwnd, rect)

---

## Capability Runtime (Verified from nodes.py:build_capability_runtime())

### Available in Execute Namespace
```python
# Node-based actions (use element IDs from action_index)
click_node(id)
scroll_node(id, amount)
node_by_id(id)
action_nodes(action=None)

# Raw coordinate actions
click(x, y, hwnd=0)
type_text(text)
press_key(key)
hotkey(keys)
scroll(x, y, amount, hwnd=0)
focus_window(target)  # target: "W1", "title substring", or "hwnd:12345"
open_url(browser, url)

# pyautogui-compatible facade (dependency-free)
pyautogui.click(x, y)
pyautogui.write(text)
pyautogui.press("enter")
pyautogui.hotkey("ctrl", "l")
pyautogui.scroll(-3, x, y)
pag = pyautogui  # alias

# Stdlib modules
subprocess, ctypes, os, sys, json, re, time, pathlib, math, random, types

# Context
state, wiring, goal, last, fresh_observation, desktop_tree_text, focused_title
```

### pyautogui Facade Implementation
```python
class _PyAutoGuiCompat:
    def click(self, x, y, clicks=1, interval=0.0, hwnd=0): ...
    def write(self, text, interval=0.0): ...      # types char-by-char via type_text
    def press(self, key, presses=1, interval=0.0): ...
    def hotkey(self, *keys): ...                  # presses modifiers + key + releases
    def scroll(self, clicks, x=None, y=None, hwnd=0): ...
    def sleep(self, seconds): time.sleep(seconds)
```

---

## Desktop Tree Structure (Verified from Observations)

### Semantic Tree (Brain-Facing)
```json
{
  "id": "W0",
  "role": "Screen",
  "focused_title": "Grok - Opera",
  "root": {
    "id": "W0",
    "role": "Screen",
    "name": "Screen",
    "children": [
      {"id": "W1", "role": "Window", "name": "Grok - Opera", "focused": true, "children": []},
      {"id": "W2", "role": "Window", "name": "Windows PowerShell", "children": []},
      ...
    ]
  }
}
```

### Action Index (Body-Facing — Same IDs, Full Targeting Data)
```json
{
  "e_0_972_374": {
    "id": "e_0_972_374",
    "parent_id": "W1",
    "role": "Button",
    "name": "Thinking about your request...",
    "action": "click",
    "px": 1225, "py": 255,
    "hwnd": 0,
    "rect": {"left": 969, "top": 246, "right": 1481, "bottom": 265},
    "enabled": true, "focused": false,
    "automation_id": "", "class_name": "...", "runtime_id": []
  }
}
```

### Rendered Tree Text (What Brain Sees)
```
(W0) Screen Screen
  (W1) Window Grok - Opera [FOCUSED]
    Button Thinking about your request... [click]
    Edit Ask Grok anything [write]
    Button Model select [click]
    Button Dictation (Ctrl+D) [click]
  (W2) Window Windows PowerShell
  (W3) Window Program Manager
```

---

## Failure Modes in Desktop Observation

1. **Chrome/Opera DOM opaque** — hover scan cannot penetrate Chromium's UIA implementation
2. **Target window only** — misses taskbar, start menu, other windows
3. **Step_px=64** — coarse grid misses small buttons/inputs
4. **No deep recursion** — nested panes/groups not explored
5. **Focus detection unreliable** — "has_focus" often wrong for Chrome children
# AGENTS.md — endgame-ai forensic instructions (chunk 5/6)

## Complete Failure Mode Taxonomy (From Both Runs)

### 1. App Launch Race (CONFIRMED)
- **Pattern**: execute launches app → verify runs immediately → desktop_tree doesn't show app → step_denied
- **Occurrences**: Run A tick 4, Run B ticks 4, 8, 12, 16
- **Root Cause**: No delay between execute completion and next observe
- **Evidence**: Run A t=1783103946 verify sees no Opera; t=1783103956 observe sees Opera
- **Fix**: Add `post_execute_delay_ms` in wiring.json, consumed by organism loop before next node

### 2. Shallow Desktop Tree (CONFIRMED)
- **Pattern**: Hover scan only returns window + immediate children; Chrome/Opera DOM not penetrated
- **Evidence**: Opera observations show 0-3 actionable elements; "Ask Grok anything" Edit never appears
- **Impact**: Execute must use hardcoded coordinates; cannot target by element ID
- **Fix**: Increase `step_px`, add deep recursion option, or integrate CDP for Chrome

### 3. Opportunistic Progress Without Step Advance (CONFIRMED)
- **Pattern**: Execute sees app focused, performs action for NEXT step while scheduler still on CURRENT step
- **Evidence**: Run A t=1783103958 execute returns `{'opera_visible': True}` for step "Launch Opera" but actually typed query
- **Impact**: Step index doesn't advance; verify confirms current step by luck
- **Fix**: Execution record should signal `progress: "advanced_beyond_current_step"`

### 4. Self-Modify Corrupt Patch (CONFIRMED - BOTH RUNS DIED HERE)
- **Pattern**: Self-modify generates unified diff with wrong line numbers → `git apply --check` fails
- **Run A**: "corrupt patch at line 40"
- **Run B**: "corrupt patch at line 68"
- **Root Cause**: Self-modify hallucinates line numbers without reading actual file
- **Impact**: contract_check.py NEVER RUNS — git apply fails first
- **Fix**: Self-modify must read file first, compute correct line numbers, or use full-file replacement

### 5. Open_URL Fabricates Success (CONFIRMED)
- **Pattern**: `open_url('opera', 'https://x.com')` returns `{'ok': True, 'navigated': True}` but desktop_tree still shows Grok tab
- **Evidence**: Run A t=1783103979 verify step_denied: "open_url fabricated success, still on Grok tab"
- **Root Cause**: open_url uses `subprocess.Popen(['start', '', url], shell=True)` → returns immediately without verification
- **Fix**: open_url must verify navigation (wait + observe) or return honest "launched" not "navigated"

### 6. Focus_Window Activates Wrong Window (CONFIRMED)
- **Pattern**: Focus by title substring via EnumWindows activates wrong window (GitHub Desktop instead of Opera)
- **Evidence**: Run B self_modify rationale: "activated wrong window (GitHub Desktop) despite exact title in fresh tree for W2"
- **Root Cause**: EnumWindows order-dependent; doesn't use fresh observation hwnd
- **Fix**: Use `last_action_index` hwnd/title from fresh hover scan (self_modify #2 attempted this)

### 9. Start Menu Search Selection Broken (CONFIRMED - LATEST RUN)
- **Pattern**: Execute types into Start menu search but doesn't select result; Enter just submits search query, doesn't launch app
- **Evidence**: Latest run reflection: "explicit down-arrow + enter to select result, or ensure start menu is fully open before typing"
- **Root Cause**: Start menu search shows results list; typing + Enter submits search, doesn't select first result. Need `Down` arrow + `Enter` to launch
- **Impact**: App launch appears to fail (Opera never appears) even though search executed
- **Fix**: Execute must send `hotkey("down")` then `press_key("enter")` after typing search query, with adequate delay for results to populate

### 7. No Frame_Action Usage (CONFIRMED)
- **Pattern**: frame_action node exists in topology, never triggered (0 calls in both runs)
- **Impact**: Execute goes straight to verify/reflect without framing pass
- **Root Cause**: Execute never returns `FRAME` conclusion; `_should_frame()` logic too restrictive
- **Fix**: Lower frame threshold, or make frame_action mandatory after failures

### 8. Verify Over-Confirms Content (CONFIRMED)
- **Pattern**: Verify confirms step based on window title + last_action, not actual content readback
- **Evidence**: Run A verify confirms "query sent" based on "Ask Grok anything" focused, not actual response visible
- **Fix**: Verify should read clipboard / UIA text pattern for content verification

---

## MoE (Mixture of Experts) Meta-Analysis

### The Organism as System-Level MoE
```
                    Input: Goal + State + Observation
                              ↓
                    Router: wiring.json topology
                              ↓
        ┌─────────┬──────────┼──────────┬──────────┐
        ↓         ↓          ↓          ↓          ↓
    Planner  Execute   Verify    Reflect  Self-Modify
   (decompose) (act)   (judge)  (diagnose) (evolve)
        └─────────┴──────────┼──────────┴──────────┘
                              ↓
                    Bus: JSON records
                              ↓
                    State: state.json
```

### Organ Competence Assessment

| Organ | Strength | Critical Weakness | Evidence |
|-------|----------|-------------------|----------|
| **Planner** | Decomposes goal into verifiable steps | Overfits to Opera; steps too coarse for browser work | 5 steps for complex demo; no sub-steps for "navigate to x.com → login → compose → publish" |
| **Execute** | Generates working Python; adapts to observation | Uses hardcoded coords; fabricates success; no frame usage | `open_url` fabricates; `result = {'opera_visible': True}` when already visible |
| **Verify** | Denies false success (app launch race); strict reasoning | Over-confirms content; no deep readback | Confirmed query sent by title only; denied Opera launch correctly |
| **Reflect** | Correctly classifies retry vs escalate; good diagnosis | Escalates too late (after 3-4 retries); no frame attempt | Run A: 2 retries then escalate; Run B: 3 retries then escalate |
| **Self-Modify** | Identifies systemic issues; proposes targeted fixes | **Corrupt patch format**; no feedback from git apply failure | Both runs died at git apply; never reached contract_check |

### The Fatal Loop
```
Execute fails → Verify denies → Reflect retries (3-4x) → Reflect escalates
     ↓
Self-Modify proposes fix → Git apply FAILS (corrupt patch) → Error node → HALT
     ↓
contract_check.py NEVER RUNS → No immune validation → No learning → Same bug next run
```

### What Must Be Fixed First (Priority Order)

1. **P0: Self-modify corrupt patch** — blocks ALL evolution, both runs died here
2. **P0: App launch race delay** — causes false failures, wastes LLM calls
3. **P1: Open_url honesty** — fabricates success, breaks trust
4. **P1: Focus_window reliability** — activates wrong window
5. **P2: Frame_action integration** — unused safety net
6. **P2: Deep desktop tree** — limits browser automation
7. **P3: Opportunistic progress protocol** — step index desync
# AGENTS.md — endgame-ai forensic instructions (chunk 6/6)

## Actionable Fix Checklist (Priority Order)

### P0: Self-Modify Corrupt Patch (BLOCKS ALL EVOLUTION)
- [ ] In `nodes.py:apply_evolution_patch()`: add pre-flight read of target file to compute correct line numbers
- [ ] Or: allow full-file replacement for files < 500 lines (bypass unified diff line numbers)
- [ ] Or: catch `git apply` failure, parse error, retry with corrected patch
- [ ] **Test**: Run self_modify with a known-good diff → verify contract_check.py runs

### P0: App Launch Race Delay
- [ ] Add `post_execute_delay_ms` to `wiring.json` (default: 3000)
- [ ] In `organism.py:run()`: after execute node, before next node, `time.sleep(delay/1000)`
- [ ] Make delay configurable per-step via `step.post_execute_delay_ms` in plan
- [ ] **Test**: Launch Notepad → verify waits 3s → observe sees Notepad → step_confirmed on first try

### P1: Open_URL Honesty
- [ ] In `desktop.py:open_url()`: after `Popen`, wait for window + verify URL in title/tree
- [ ] Return `{"ok": True, "action": "open_url", "launched": True, "verified": False}` initially
- [ ] Add `verify_navigation(browser, url)` helper for execute to call after open_url
- [ ] **Test**: open_url('opera', 'https://x.com') → returns launched=True → verify_navigation confirms

### P1: Focus_Window Reliability
- [ ] In `desktop.py:focus_window()`: prioritize `last_action_index` hwnd lookup (already in self_modify #2 patch)
- [ ] Remove EnumWindows callback; use fresh observation data only
- [ ] Support exact title match via `last_action_index` Window nodes
- [ ] **Test**: focus_window("Takeda-Insilico AI Drug Deal - Grok - Opera") → activates W2 not W1

### P1: Start Menu Search Execution (NEW - FROM LATEST RUN)
- [ ] In execute node prompt or capability runtime: document start menu pattern requires `hotkey("down")` + `press_key("enter")` after typing search
- [ ] Add `wait_for_start_menu_results` helper or pattern in capability runtime
- [ ] Ensure adequate delay between Win key press and typing (start menu animation)
- [ ] **Test**: Execute launches Opera via start menu → down-arrow + enter → verify sees Opera window

### P2: Frame_Action Integration
- [ ] In `execute.py:_should_frame()`: return True after ANY step_denied (not just CANNOT/FRAME)
- [ ] Or: make frame_action mandatory after first verify failure
- [ ] **Test**: Step denied → frame_action runs → returns action_frame → execute uses it

### P2: Deep Desktop Tree (Configurable)
- [ ] Add `hover_scan.max_depth` (default: 1, current behavior)
- [ ] Add `hover_scan.recurse_into` list of control_types (Pane, Group, Document)
- [ ] **Test**: max_depth=3 → sees "Ask Grok anything" Edit in Opera

### P3: Opportunistic Progress Protocol
- [ ] Add `progress` field to execution record: `"advanced_beyond_current_step" | "on_track"`
- [ ] In scheduler: if progress=advanced_beyond_current_step, advance step_index + confirm
- [ ] **Test**: Execute types query during "Launch Opera" step → progress=advanced → scheduler advances

---

## Wiring.json Key Sections (Verified)

```json
{
  "model": {
    "transport": "xai",
    "transport_config": {
      "xai": {
        "model": "grok-4.3",
        "reasoning": {"enabled": true, "effort": "low"},
        "web_search": {"enabled": true, "allowed_domains": ["github.com", "raw.githubusercontent.com", "api.github.com"]}
      }
    },
    "global": {"timeout": 180, "raw_log": true, "reasoning_enabled": true},
    "stable_prefix": {"enabled": false, "for_record_types": ["git_evolution_patch"]},
    "organs": {
      "plan": {"reasoning_effort": "medium", "temperature": 0.35, "max_output_tokens": 2400},
      "action_frame": {"reasoning_effort": "medium", "temperature": 0.45, "max_output_tokens": 2200},
      "execution": {"reasoning_effort": "low", "temperature": 0.25, "max_output_tokens": 5000},
      "verification": {"reasoning_effort": "none", "temperature": 0.05, "max_output_tokens": 1200},
      "reflection": {"reasoning_effort": "medium", "temperature": 0.25, "max_output_tokens": 2400},
      "git_evolution_patch": {"reasoning_effort": "high", "temperature": 0.2, "max_output_tokens": 24000, "timeout": 360, "web_search": {"enabled": true}},
      "satisfied": {"reasoning_effort": "none", "temperature": 0.0.05, "max_output_tokens": 800}
    }
  },
  "paths": {"nodes": "organism_nodes", "brains": "brain_transports", "state": "state.json", "control": "comms/control.json", "runtime_log": "comms/runtime.ndjson"},
  "topology": {"cycle_start": "planner", "nodes": [...], "edges": {...}},
  "prompts": {"planner": "...", "execute": "...", "verify": "...", "reflect": "...", "self_modify": "...", "frame_action": "...", "scheduler": "...", "satisfied": "..."},
  "self_modify": {
    "context_mode": "checked_out_branch",
    "git": {"remote": "origin", "push_after_commit": true},
    "web_search": {"enabled": true, "allowed_domains": ["github.com", "raw.githubusercontent.com", "api.github.com"]},
    "wiring_allowed_new_prefixes": ["self_modify.", "model.stable_prefix.", "model.organs.", "limits.", "prompts."]
  },
  "observe_config": {"hover_scan": {"mode": "cursor_hover", "step_px": 64, "delay_ms": 1, "target_window_only": true}}
}
```

---

## Validation Pipeline (MANDATORY Before/After Any Change)

```bash
# 1. Syntax check
python -m compileall -q .

# 2. JSON schema validation
python -m json.tool wiring.json

# 3. Immune system (contract_check.py) — THE REAL VALIDATOR
python contract_check.py
```

**Run these after ANY self-modify or manual edit to core files.**

---

## File Ownership Map (Verified)

| Path | Owner | Purpose | Critical |
|------|-------|---------|----------|
| `organism.py` | Main loop | Step control, state, topology routing | YES |
| `brain.py` | LLM chokepoint | Transport selection, ROD pattern, stable prefix, logging | YES |
| `nodes.py` | Node runtime | Loader, BaseNode, capability runtime, self-modify apply/commit | YES |
| `bus.py` | Protocol | NodeOutput, signal validation, datasheets, state briefs | YES |
| `desktop.py` | Body/sensors | UIA COM, hover scan, action helpers, tree rendering | YES |
| `contract_check.py` | Immune system | Static AST + wiring validation | YES |
| `organism_nodes/*.py` | Organs | One file per topology node, exports `run(ctx)` + `DATASHEET` | YES |
| `brain_transports/*.py` | Transports | Single `call(messages, cfg)` export, no fallbacks | YES |
| `wiring.json` | Nervous system | Topology, prompts, model config, self-modify rules | YES |
| `state.json` | Memory | Mutable runtime state (tick, step, last_*, plan, trees) | YES |
| `comms/control.json` | External control | `mode: run\|pause\|step`, `step_token` | YES |

---

## Extending the Organism (Verified Patterns)

### 1. New Organ
```bash
# 1. Create organism_nodes/new_organ.py with run(ctx) + DATASHEET
# 2. Add to wiring.json:topology.nodes
# 3. Add edges in topology.edges
# 4. Add prompt in prompts.new_organ
```

### 2. New Transport
```bash
# 1. Create brain_transports/new_transport.py with call(messages, cfg)
# 2. Set model.transport in wiring.json
```

### 3. New Capability
```bash
# Add to nodes.py:build_capability_runtime() namespace → available to execute immediately
```

### 4. New Wiring Path
```bash
# Add to self_modify.wiring_allowed_new_prefixes before self-modify can create it
```

---

## Critical Reminders (Burn These In)

- **NEVER trust compilation alone** — `contract_check.py` is the real validator
- **Unified diffs REQUIRED** for existing protected Python files (`organism_nodes/`, `brain_transports/`, core files)
- **Read before write** — `self_modify` must declare `read_files` for every touched existing file
- **No fallback transports** — wiring selects exactly one, failure = hard error
- **Desktop tree is SHALLOW** — plan actions around window-level + immediate children visibility
- **Pause/step is EXTERNAL** — edit `comms/control.json`, don't add sleeps in code
- **Self-modify corrupt patch blocks ALL evolution** — fix this first or nothing else matters
