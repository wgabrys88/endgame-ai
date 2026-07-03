# endgame-ai

**Local desktop organism** — Python body, desktop world, wiring.json nervous system, JSON records bus, git firmware memory.

---

## Architecture

```
Goal → planner → scheduler → observe → execute → verify → (step_confirmed→scheduler | step_denied→reflect)
reflect → (retry→observe | replan→planner | escalate→self_modify | give_up→satisfied)
self_modify → (modified→planner | modify_failed→reflect | error→error)
```

**Organs** (in `organism_nodes/`):
- `planner` — decomposes goal into verifiable steps
- `scheduler` — selects next unfinished step
- `observe` — fresh hover scan (Win32, cursor-shape grid)
- `execute` — generates Python, runs in capability runtime
- `frame_action` — ROD framing pass (optional, after failures)
- `verify` — judges step.done_when against observation
- `reflect` — routes retry/replan/escalate/give_up
- `self_modify` — produces git patches, validated by immune system
- `satisfied` — halt gate
- `error` — mechanical failure router

**Body** (core modules):
- `desktop.py` — Win32 hover scan, Excel grid (A1, B2...), cursor semantics (ibeam/hand/size/arr)
- `win32_api.py` — click, type, hotkey, scroll, window enum, cursor detection
- `winrt_ocr.py` — Windows built-in OCR (future)
- `nodes.py` — node loader, capability runtime, self-modify apply/commit
- `bus.py` — NodeOutput, signal validation, state briefs
- `brain.py` — transport selection (fail-hard), ROD pattern, stable prefix, JSONL logging
- `contract_check.py` — immune system (AST + wiring validation)
- `organism.py` — main loop, topology routing, pause/step control

---

## Self-Modification Pipeline

```
reflect.escalate → self_modify node → nodes.apply_evolution_patch() →
nodes.commit_self_evolution() → git commit [+ push] → reload wiring
```

**Validation order** (immune system):
1. Parse patch, validate read_files declared for ALL touched existing files
2. Validate unified_diffs (must name repo files, touched files in read_files)
3. Validate file_writes (new files or non-protected supporting files only)
4. Validate file_deletes (protected files cannot be deleted)
5. Validate wiring_patches (only allowed prefixes)
6. Snapshot touched paths for rollback
7. Apply unified diffs via `git apply --check` then `git apply`
8. Write new files atomically
9. Apply wiring patches in-memory + save wiring.json
10. Compile-check all modified `.py` files
11. **Run contract_check.py** (IMMUNE SYSTEM — critical)
12. Run user commands (must include `python contract_check.py`)
13. Re-run contract_check.py after commands
14. Commit + optional push

**Protected files** (require unified diffs, not full rewrites):
- `organism_nodes/*.py`
- `brain_transports/*.py`
- CORE_FILES: `brain.py`, `bus.py`, `desktop.py`, `nodes.py`, `organism.py`, `stop_check.py`, `contract_check.py`, `wiring.json`

---

## Desktop Observation (Win32 Hover Scan)

**Config** (`wiring.json:observe_config`):
```json
{
  "step_px": 60,
  "delay_ms": 0,
  "cell_size": 100,
  "max_elements": 200,
  "restore_cursor": true
}
```

**Output** (Excel grid):
```
A1=ibeam  B1=arr    H1=hand
A2=siz    B2=ibeam  H2=arr
...
```
- Cursor shape detection: `ibeam`=type, `hand`=click, `size`=resize, `arr`=default
- Universal: works on Win32, WPF, Electron, Chrome, Flutter
- No UIA/COM, no hierarchical tree, no DOM penetration needed

**Action index** (body-facing): same grid IDs + targeting data (px, py, hwnd, rect)

---

## Brain / Transport

**Single transport** (fail-hard): `wiring.json:model.transport = "xai"`

**Per-organ tuning** (`model.organs`):
| Organ | reasoning_effort | temperature | max_output_tokens |
|-------|------------------|-------------|-------------------|
| plan | medium | 0.35 | 2400 |
| action_frame | medium | 0.45 | 2200 |
| execution | low | 0.25 | 5000 |
| verification | none | 0.05 | 1200 |
| reflection | medium | 0.25 | 2400 |
| git_evolution_patch | high | 0.2 | 24000 |
| satisfied | none | 0.05 | 800 |

**ROD pattern** (Reasoning-Oriented Dialogue): two-pass for most organs, native for xAI verification/self_modify

**Logging**: `{timestamp}_brain.jsonl` — raw request/response + hyperparameters + usage + cost per call

**Stable prefix**: git `ls-files` snapshot for self_modify only (source grounding)

---

## Pause/Step Control (External)

Edit `comms/control.json`:
```json
{"mode": "pause", "step_token": 0}   # pause before next node
{"mode": "step", "step_token": 1}    # advance one node
{"mode": "run"}                      # resume
```

---

## Validation Pipeline (Mandatory After Any Change)

```bash
python -m compileall -q .
python -m json.tool wiring.json
python contract_check.py
```

---

## Extending the Organism

| Add | Steps |
|-----|-------|
| New organ | 1. Create `organism_nodes/new_organ.py` with `run(ctx)` + `DATASHEET`<br>2. Add to `wiring.json:topology.nodes`<br>3. Add edges in `topology.edges`<br>4. Add prompt in `prompts.new_organ` |
| New transport | 1. Create `brain_transports/new_transport.py` with `call(messages, cfg)`<br>2. Set `model.transport` in wiring.json |
| New capability | Add to `nodes.py:build_capability_runtime()` namespace |
| New wiring path | Add to `self_modify.wiring_allowed_new_prefixes` before self-modify can create it |

---

## Current State (2026-07-04)

### Working
- Full organism loop: planner → scheduler → observe → execute → verify → reflect
- Win32 hover scan: 55 elements, 17 cells with cursor semantics (ibe/siz/han/arr)
- Verify correctly denies false success (app launch race fixed with `post_execute_delay_ms: 3000`)
- Brain logging: single JSONL with full request/response + cost tracking
- Contract check passes on current codebase
- Self-modify pipeline structurally complete (git apply → contract_check → commit)

### Known Issues (Priority Order)

| Priority | Issue | Evidence |
|----------|-------|----------|
| **P0** | Self-modify corrupt patch | Both historic runs died at `git apply --check` (line numbers hallucinated) |
| **P0** | App launch race | Verify runs before app appears → step_denied (fixed with 3s delay) |
| **P1** | `open_url` fabricates success | Returns `navigated: true` but tab unchanged |
| **P1** | Start menu needs `down+enter` | Typing + Enter submits search, doesn't launch app |
| **P1** | `focus_window` activates wrong window | EnumWindows order-dependent |
| **P2** | `frame_action` never triggered | 0 calls in any run; execute never returns FRAME |
| **P2** | Opportunistic progress without step advance | Execute acts for next step while scheduler on current |
| **P3** | Verify over-confirms content | Confirms by window title, not content readback |

---

## Planned Self-Modify Test: Delete `desktop_old.py`

**Goal**: Use self-modify organ to delete the stale 1355-line UIA backup file (`desktop_old.py`) as a validation of the self-modification pipeline.

**Why this tests the system**:
- Real git patch generation (unified diff for deletion)
- Immune system validation (contract_check.py must pass after)
- Rollback on failure (wired in `apply_evolution_patch`)
- Cost verification (~$1 per self-modify call)
- Recovery path test (`modify_failed` → `reflect`)

**Mental simulation before execution**:
1. Reflect escalates with diagnosis: "desktop_old.py is dead code, 1355 lines, not imported anywhere"
2. Self-modify receives: workspace manifest (includes desktop_old.py), git context, immune contract
3. Self-modify produces patch:
   ```diff
   diff --git a/desktop_old.py b/desktop_old.py
   deleted file mode 100644
   index <hash>..0000000
   --- a/desktop_old.py
   +++ /dev/null
   @@ -1,1355 +0,0 @@
   -# 1355 lines of UIA/COM code...
   ```
4. `apply_evolution_patch`:
   - Validates read_files includes `desktop_old.py`
   - `git apply --check` passes (deletion is simple)
   - File deleted atomically
   - `python -m compileall -q .` passes
   - `python contract_check.py` passes (desktop_old.py not in REQUIRED_FILES)
   - Commit + push
5. Next run: organism loads without desktop_old.py

**Risk**: Low. File is not imported, not in REQUIRED_FILES, not in topology. Pure deletion.

**Cost**: ~68k-70k tokens (~$0.95) for self-modify call with web_search + stable prefix.

**Execution**: Will run when explicitly requested with `python -m organism "Delete desktop_old.py via self-modify" --max-ticks 5`

---

## File Ownership Map

| Path | Purpose | Critical |
|------|---------|----------|
| `organism.py` | Main loop, topology routing | YES |
| `brain.py` | Transport, ROD, stable prefix, logging | YES |
| `nodes.py` | Node loader, capability runtime, self-modify apply | YES |
| `bus.py` | NodeOutput, signals, state briefs | YES |
| `desktop.py` | Win32 hover scan, actions | YES |
| `contract_check.py` | Immune system (AST + wiring) | YES |
| `organism_nodes/*.py` | Organ implementations | YES |
| `brain_transports/xai.py` | Active transport | YES |
| `wiring.json` | Topology, prompts, model config | YES |
| `state.json` | Mutable runtime state | YES |
| `comms/control.json` | External pause/step | YES |

---

## Quick Start

```bash
# Set API key
$env:XAI_API_KEY = "your-key"

# Run a task
python -m organism "Open Notepad and type hello" --max-ticks 10

# Pause before next node
echo '{"mode": "pause", "step_token": 0}' > comms/control.json

# Step one node
echo '{"mode": "step", "step_token": 1}' > comms/control.json

# Resume
echo '{"mode": "run"}' > comms/control.json

# Validate after changes
python contract_check.py
```

---

## Cost Reference (Historic Runs)

| Run | Planner | Execute | Verify | Reflect | Self_Modify | Total | Est. Cost |
|-----|---------|---------|--------|---------|-------------|-------|-----------|
| A (destructive) | 2,771 | ~6,500 | ~4,100 | ~4,900 | 138,281 | ~156,552 | ~$2.50 |
| B (retry) | ~2,771 | ~10,000 | ~6,800 | ~7,300 | 69,964 | ~166,799 | ~$2.70 |

**Self-modify dominates** (45% of tokens) — receives full workspace manifest + source fingerprints + immune contract + web_search.

---

## Line Counts (Core)

```
brain.py:              772
nodes.py:              852
organism.py:           248
desktop.py:            495
win32_api.py:          352
winrt_ocr.py:          190
contract_check.py:     313
bus.py:                193
stop_check.py:          85
organism_nodes/:      ~14k (10 nodes)
brain_transports/:     383 (4 files)
TOTAL:                 ~6,080 lines (excluding tests)
```

---

## Principles

1. **Fail-hard**: one transport, no fallbacks; git apply fails → stop
2. **Immune system first**: contract_check.py runs before commit, always
3. **Unified diffs required** for existing protected Python files
4. **Read before write**: self-modify must declare read_files for every touched file
5. **Desktop tree is spatial grid**: plan actions around Excel cell references
6. **Pause/step is external**: edit `comms/control.json`, no sleeps in code
7. **Self-modify corrupt patch blocks ALL evolution** — fix this first or nothing else matters