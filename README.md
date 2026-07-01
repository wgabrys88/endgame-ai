# endgame-ai

**A living Windows desktop organism — not a traditional agentic CCA.**

Python is its mechanical body. `wiring.json` is its mutable genome. Nodes and brain transports are hot-swappable modules copied from `seed_*/` → `live_*/` at runtime. The ROD loop (Reason→Observe→Decide with pluggable reasoning feedback) in `brain.think()` is the core innovation enabling small models to self-evolve.

**No fallbacks. Fail-hard always. Self-modification = rewriting `wiring.json` AND writing new node files to `live_nodes/`.**

---

## Current Status (2026-07-01, commit 82e6ba6)

**Branch:** `unified-archBRAINZ` (clean, pushed)
**Phase:** 5B complete — Execute node working. Phase 5C in progress.

### What Works Today

| Component | Status | Details |
|-----------|--------|---------|
| **Transport System** | ✅ Verified | xAI (Grok API, native reasoning), OpenAI-compatible (LM Studio, two-pass), OpenCode CLI, file_proxy (human-in-loop) |
| **ROD Reasoning** | ✅ Verified | `TwoPassStrategy`, `SinglePassStrategy`, `NativeReasoningStrategy`, `CustomStrategy` — configurable per transport |
| **Hot-swappable Nodes** | ✅ Working | `seed_nodes/` → `live_nodes/` copied at startup, re-read every execution |
| **BaseNode ABC** | ✅ Done | Brain-calling nodes reduced to ~10 lines each |
| **Error Topology** | ✅ Done | `error` node + edges from all nodes, `halt` signal for clean exit |
| **Desktop Observation** | ✅ Working | UIA COM via `comtypes.gen.UIAutomationClient` — returns screen, elements, snapshot, focused_title |
| **Hover Scanning** | ✅ Added | `hover_scan()`, `dense_probe()`, `scroll_enrich()` in `Desktop` class |
| **Execute Node** | ✅ Working | Grok writes Python, `exec()` runs it with full desktop namespace (click, type_text, hotkey, scroll, focus_window, open_url, subprocess, ctypes, self-modify helpers) |
| **Scheduler Node** | ✅ Working | Step index management, plan completion detection |
| **Topology** | ✅ Updated | planner → scheduler → observe → execute → verify → reflect → self_modify → satisfied / error |
| **Workbench** | ✅ Working | Read-only dashboard at http://127.0.0.1:8800/ with topology graph, runtime log tail, wiring viewer, transport probe, brain test |

### What's Incomplete (Phase 5C)

| Component | Status | Needed |
|-----------|--------|--------|
| **Observe Filtering** | ❌ | Current observation returns full UIA tree (bloat). Needs filtering to actionable elements only + hover scan integration |
| **Verify Node** | ⚠️ Stub | Evidence-based intent judgment using screen, last_action, last_result, last_error |
| **Reflect Node** | ⚠️ Stub | Concrete diagnosis + specific suggestion, routes to retry/replan/escalate/give_up |
| **Self-Modify Node** | ⚠️ Stub | Output `wiring_patch` record with wiring_patches, node_writes, node_deletes |
| **Window Tokens** | ❌ | Stable W1..Wn tokens for visible windows across observations |
| **Element Classification** | ❌ | Role → action mapping (click/write/scroll) for execute targeting |
| **Bounded Desktop Tree** | ❌ | Optional UIA tree walk with depth/node limits |
| **Formatting (SCREEN text)** | ❌ | Human-readable formatted text for LLM context |

---

## Architecture Overview

### Core Files

| File | Role | Lines |
|------|------|-------|
| `brain.py` | Transport protocol, BaseTransport, ReasoningStrategy, `call()`/`think()`, config resolution | 508 |
| `nodes.py` | BaseNode ABC, `call_node()`, node loading, `build_execute_namespace()`, desktop helpers, wiring patch | ~250 |
| `organism.py` | Main loop, topology traversal, error routing, `--max-ticks` kill switch | 230 |
| `wiring.json` | Genome: transport, topology, prompts, reasoning config, observe config | ~200 |
| `desktop.py` | UIA COM, Element/Observation, **hover_scan/dense_probe/scroll_enrich**, action methods | ~780 |
| `seed_brains/*.py` | Transport implementations (xai, openai, opencode, file_proxy, browser_ai) | 5 files |
| `seed_nodes/*.py` | Node implementations (planner, observe, execute, scheduler, verify, reflect, self_modify, satisfied, error) | 9 files |

### Data Flow

```
Goal → planner → scheduler → observe → execute → verify → reflect → self_modify
                                             ↓           ↓           ↓
                                          (retry)    (replan)   (wiring patch + node writes)
                                             ↓           ↓           ↓
                                          observe ←───┴───────────┴─── planner (next cycle)
```

**State** (`state.json`): `{goal, plan[], step, current_step, screen, elements, snapshot, last_action, last_code, last_result, last_error, history[], memory{}, wiring_transport, tick, _phase}`

**Runtime log** (`comms/runtime.ndjson`): Every node start/complete, brain call, error, wiring change — full audit trail.

---

## Transport System (Fail-Hard, No Fallbacks)

`wiring.json` → `model.transport` selects ONE transport. No fallback chain.

```json
"model": {
  "transport": "xai",
  "transport_config": {
    "xai": {"mode": "api", "api_key_env": "XAI_API_KEY", "model": "grok-build-0.1", "reasoning": {"enabled": true, "pattern": "native"}},
    "openai": {"base_url": "http://localhost:1234", "model": "nvidia-nemotron-3-nano-4b", "reasoning": {"enabled": true, "pattern": "two_pass"}},
    "opencode": {"executable": "opencode", "model": "opencode/nemotron-3-ultra-free"},
    "file_proxy": {"request_path": "comms/request.json", "response_path": "comms/response.json"},
    "browser_ai": {"documented_stub": true},
    "grok_cli": {"executable": "grok", "reasoning": {"enabled": true, "pattern": "native"}}
  },
  "global": {"timeout": 180, "raw_log": true, "reasoning_enabled": true}
}
```

**Reasoning patterns** (configurable per transport in wiring):
- `native` — Model returns reasoning field (Grok, OpenAI o1)
- `two_pass` — Call 1: reasoning, Call 2: inject reasoning → JSON (Nemotron 4B)
- `single_pass` — One call, extract JSON directly
- `custom` — Configurable injection template + extractor

---

## Node System (Hot-Swappable)

`seed_nodes/` → copied to `live_nodes/` on startup. **Re-read every execution.**

```python
# BaseNode contract (nodes.py)
class BaseNode(ABC):
    prompt_key: str = ""           # wiring["prompts"][prompt_key]
    expected_record_type: str = "" # validated against brain output
    
    @abstractmethod
    def signal_from_data(self, data: dict) -> str: ...
    @abstractmethod
    def patch_from_record(self, record: dict) -> dict: ...
    
    def run(self, ctx: dict) -> tuple[str, dict]: ...
```

**Execution**: `nodes.call_node(node_name, ctx)` → loads `live_nodes/{node_name}.py` → calls `run(ctx)` → returns `(signal, patch)`.

**Context passed to every node**:
```python
ctx = {
    "wiring": wiring,           # full wiring.json
    "state": dict(state),       # organism state snapshot
    "goal": goal_str,
    "node": current_node_name,
    # Desktop I/O helpers (from nodes.py):
    "observe_screen": ...,
    "execute_verb": ...,
    "last_observation_snapshot": ...,
    "get_focused_title": ...,
    "apply_wiring_patch": ...,
    "save_wiring": ...,
    "wiring_limit": ...,
}
```

---

## The Execute Node: Core Unification (✅ DONE)

**Replaces**: `decide.py` + `act.py` + `actions.py` (10 verbs) + `ActionExecutor` (300 lines)

### Execute Node Contract

```python
# seed_nodes/execute.py
def run(ctx):
    # Build prompt with step_goal, screen, elements, last_error, last_result
    # Call brain.think() with execute prompt
    # Execute returned code via exec() with build_execute_namespace(ctx)
    # Return signal ("verify" | "reflect" | "self_modify") + patch
```

### Namespace Builder (`nodes.py:build_execute_namespace`)

```python
def build_execute_namespace(ctx):
    desktop = _get_desktop_instance()
    return {
        # Observation
        "observe_screen": observe_screen,
        "last_observation_snapshot": last_observation_snapshot,
        "get_focused_title": get_focused_title,
        
        # Convenience verbs
        "execute_verb": execute_verb,  # click, write, press, hotkey, focus, scroll, wait, launch, open_url, remember
        
        # Raw desktop actions
        "click": desktop.click,
        "type_text": desktop.type_text,
        "press_key": desktop.press_key,
        "hotkey": desktop.hotkey,
        "scroll": desktop.scroll,
        "focus_window": desktop.focus_window,
        "open_url": desktop.open_url,
        
        # System
        "subprocess": subprocess,
        "ctypes": ctypes,
        "os": os, "sys": sys, "json": json, "re": re, "time": time,
        "pathlib": pathlib, "math": math, "random": random,
        
        # Self-modification
        "apply_wiring_patch": apply_wiring_patch,
        "save_wiring": save_wiring,
        "wiring_limit": wiring_limit,
        
        # Context
        "state": ctx["state"],
        "wiring": ctx["wiring"],
        "goal": ctx["goal"],
        
        # Desktop module
        "desktop": desktop,
    }
```

### What This Enables

| Task | Before (10 verbs) | After (execute node) |
|------|-------------------|---------------------|
| Open Notepad | `launch` verb | `subprocess.Popen(["notepad.exe"])` |
| Click button | `click` verb + element resolution | `click(el["px"], el["py"], el["hwnd"])` |
| Type in field | `write` verb + element resolution | `click(...)`, `type_text("hello")` |
| Complex multi-step | Multiple verb calls | Single Python script with loops, conditionals |
| Install pyautogui | Impossible | `subprocess.run([sys.executable, "-m", "pip", "install", "pyautogui"])` |
| Read clipboard | Impossible | `ctypes` + `OpenClipboard` + `GetClipboardData` |
| Any Windows API | Impossible | `ctypes.windll.user32.*`, `ctypes.windll.kernel32.*` |
| Self-modify wiring | Stub only | `apply_wiring_patch()`, `save_wiring()` in executed code |
| Write new node file | Impossible | `pathlib.Path("live_nodes/new_skill.py").write_text(code)` |

**The organism becomes an unconstrained Windows operator.** Grok writes the code. Python executes it. No verb list limits capability.

---

## Full Topology (9 Nodes)

```
planner → scheduler → observe → execute → verify → reflect → self_modify
                       ↑                              ↓
                       └────────────── retry ─────────┘
                                ↓
                          satisfied
```

| Node | File | Role | Brain? | Output Signals |
|------|------|------|--------|----------------|
| **planner** | `seed_nodes/planner.py` | Goal → ordered plan (steps with `description`, `done_when`) | ✅ | `step_ready` \| `reflect` |
| **scheduler** | `seed_nodes/scheduler.py` | Pick next step by index; detect plan complete | ❌ | `step_ready` \| `plan_complete` |
| **observe** | `seed_nodes/observe.py` | Call `Desktop.observe()` → return `screen`, `elements`, `snapshot` | ❌ | `screen_ready` |
| **execute** | `seed_nodes/execute.py` | Grok writes Python, `exec()` runs it | ✅ | `verify` \| `reflect` \| `self_modify` |
| **verify** | `seed_nodes/verify.py` | Judge step intent satisfied (evidence-based) | ✅ | `step_confirmed` \| `step_denied` |
| **reflect** | `seed_nodes/reflect.py` | Diagnose failure, choose recovery path | ✅ | `retry` \| `replan` \| `escalate` \| `give_up` |
| **self_modify** | `seed_nodes/self_modify.py` | Patch wiring.json AND/OR write `live_nodes/*.py` files | ✅ | `modified` \| `modify_failed` |
| **satisfied** | `seed_nodes/satisfied.py` | Goal complete / rest state | ❌ | `halt` |
| **error** | `seed_nodes/error.py` | Mechanical error handler (no brain) | ❌ | `planner` \| `reflect` \| `halt` |

### Topology Edges (wiring.json)

```json
"topology": {
  "cycle_start": "planner",
  "nodes": ["planner","scheduler","observe","execute","verify","reflect","self_modify","satisfied","error"],
  "edges": {
    "planner": {"step_ready": "scheduler", "reflect": "reflect", "error": "error"},
    "scheduler": {"step_ready": "observe", "plan_complete": "satisfied", "error": "error"},
    "observe": {"screen_ready": "execute", "error": "error"},
    "execute": {"verify": "verify", "reflect": "reflect", "self_modify": "self_modify", "error": "error"},
    "verify": {"step_confirmed": "scheduler", "step_denied": "reflect", "error": "error"},
    "reflect": {"retry": "observe", "replan": "planner", "escalate": "self_modify", "give_up": "satisfied", "error": "error"},
    "self_modify": {"modified": "planner", "modify_failed": "reflect", "error": "error"},
    "satisfied": {"halt": "halt"},
    "error": {"planner": "planner", "reflect": "reflect", "halt": "halt"}
  }
}
```

### Signal Semantics

- `step_ready` — Next plan step available, go observe
- `plan_complete` — All steps done, goal achieved
- `screen_ready` — Observation captured, ready for execute
- `verify` — Execute succeeded (no exception), go verify
- `reflect` — Execute failed OR verify denied, diagnose
- `self_modify` — Escalation: rewire or write new nodes
- `step_confirmed` — Verifier: intent satisfied, next step
- `step_denied` — Verifier: intent NOT satisfied, diagnose
- `retry` — Same step, try again with diagnosis
- `replan` — Whole plan wrong, new plan needed
- `escalate` — Cannot recover, modify self (wiring/nodes)
- `give_up` — Unrecoverable, rest
- `modified` — Self-modify succeeded, new wiring active
- `modify_failed` — Self-modify failed, diagnose
- `halt` — Clean exit, organism stops

---

## Desktop Observation (Current Implementation)

`desktop.py` uses `comtypes.gen.UIAutomationClient` (~780 lines). It provides:

### Core Classes

```python
@dataclass
class Element:
    name: str
    control_type: str
    control_type_id: int
    automation_id: str
    class_name: str
    process_id: int
    rect: Rect
    is_enabled: bool
    is_offscreen: bool
    has_focus: bool
    framework_id: str
    runtime_id: list[int]
    window_handle: int
    children: list["Element"]

@dataclass
class Observation:
    timestamp: float
    screen_width: int
    screen_height: int
    focused_element: Element | None
    root_elements: list[Element]
    active_window: Element | None
    focused_title: str
```

### Current Observation Pipeline

1. **Screen size** via `GetSystemMetrics`
2. **Root element** via `GetRootElement()`
3. **Focused element** via `FindFirst(TreeScope_Descendants, true_condition)` + `HasKeyboardFocus`
4. **Active window** via `GetForegroundWindow()` + `ElementFromHandle()`
5. **Top-level windows** via `ControlViewWalker` (shallow tree, max_depth=3)
6. **Returns** screen, elements list, snapshot, focused_title

### Added: Hover Scanning (Phase 5C)

```python
def hover_scan(self, config: dict | None = None) -> list[Element]:
    """Grid probe across screen/window via ElementFromPoint."""
    # Config: step_px, delay_ms, target_window_only, min_size_px, max_elements
    # Returns deduplicated elements by runtime_id

def dense_probe(self, region: Rect, config: dict | None = None) -> list[Element]:
    """Dense probe a specific region (smaller step)."""

def scroll_enrich(self, config: dict | None = None) -> list[Element]:
    """Scroll and re-probe to discover more elements."""
```

### Configuration (wiring.json → `configure_observation()`)

```json
"observe_config": {
  "max_depth": 3,
  "include_offscreen": false,
  "max_elements": 500,
  "hover_scan_step_px": 40,
  "hover_scan_delay_ms": 1,
  "hover_scan_target_window_only": true,
  "hover_scan_min_size_px": 10,
  "hover_scan_max_elements": 100
}
```

### Observe Node Output (Current)

```python
# seed_nodes/observe.py
def run(ctx):
    obs = desktop.observe(config)
    return "screen_ready", {
        "screen": obs.get("screen"),
        "elements": obs.get("elements"),      # List of element dicts (full tree)
        "snapshot": obs.get("snapshot"),
        "focused_title": obs.get("focused_title"),
    }
```

**Problem**: Returns full UIA tree with thousands of nested elements, most with zero rects, no action classification, no window tokens. Wastes tokens.

---

## Self-Modification: Wiring + Node Files (Stub)

`self_modify` node can change BOTH `wiring.json` AND `live_nodes/*.py` files atomically.

### Self-Modify Output Record (Target)

```json
{
  "record_type": "wiring_patch",
  "data": {
    "wiring_patches": [
      {"op": "set", "path": "model.transport_config.xai.temperature", "value": 0.8},
      {"op": "set", "path": "topology.nodes", "value": ["planner","scheduler","observe","execute","verify","reflect","self_modify","satisfied","error","new_node"]}
    ],
    "node_writes": [
      {"path": "live_nodes/new_skill.py", "content": "from __future__ import annotations\n\ndef run(ctx):\n    return \"verify\", {\"skill_result\": \"done\"}"},
      {"path": "live_nodes/execute.py", "content": "..."}
    ],
    "node_deletes": ["live_nodes/obsolete_skill.py"]
  }
}
```

### Application (in `nodes.py:apply_wiring_patch`)

```python
def apply_wiring_patch(wiring: dict, parsed: dict) -> tuple[str, Any]:
    data = (parsed or {}).get("data") or {}
    
    # 1. Apply wiring patches
    for patch in data.get("wiring_patches", []):
        op = patch.get("op", "set")
        path = patch.get("path", "")
        value = patch.get("value")
        parts = path.split(".")
        cur = wiring
        for part in parts[:-1]:
            if not isinstance(cur.get(part), dict):
                cur[part] = {}
            cur = cur[part]
        if op == "set":
            cur[parts[-1]] = value
        elif op == "delete":
            cur.pop(parts[-1], None)
    
    # 2. Write node files
    for write in data.get("node_writes", []):
        path = pathlib.Path(write["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(write["content"], encoding="utf-8")
    
    # 3. Delete node files
    for delete_path in data.get("node_deletes", []):
        pathlib.Path(delete_path).unlink(missing_ok=True)
    
    # 4. Atomic write wiring.json
    save_wiring(wiring)
    return "set", {...}
```

---

## Workbench (Read-Only Dashboard)

**Reflects organism reality. No control over organism.**

Run: `python workbench.py` → http://127.0.0.1:8800/

### UI Features
- **Status Panel**: Current node, tick, phase, goal, transport, last error
- **Topology Graph**: SVG visualization with current node highlighted, signal edges
- **Runtime Log Tail**: Live NDJSON stream from `comms/runtime.ndjson`
- **Wiring Viewer**: Read-only JSON with syntax highlighting
- **Transport Probe**: Health check for current transport
- **Brain Test**: ROD falsification test (2 calls) for any transport

### API Endpoints (Read-Only)

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Full organism state + runtime tail + wiring summary |
| `GET /api/wiring` | Full wiring.json |
| `GET /api/state/raw` | Raw state.json |
| `GET /api/logs/tail?lines=100` | Runtime NDJSON tail |
| `GET /api/transport/probe` | Current transport health check |
| `POST /api/brain/test` | ROD test: `{"transport": "xai"}` |

**No control endpoints.** Organism controlled only by `--max-ticks` (hard stop).

---

## Kill Switch: `--max-ticks` Only

**Single hard stop mechanism. No pause/step. No `--max-brain-calls` (redundant).**

```bash
# Run with hard tick limit
python organism.py --reset --max-ticks 10 "open notepad and write hello"

# Organism loop (organism.py):
while True:
    stop_check.check_stop("organism main loop")
    if max_ticks is not None and state["tick"] >= max_ticks:
        state["_phase"] = "max_ticks"
        write_state(wiring, state)
        return state
    # ... execute node ...
```

---

## Quick Start

### Validation (Run First)

```powershell
# Syntax check all core files
python -m py_compile brain.py nodes.py organism.py workbench.py desktop.py

# Syntax check all seed nodes and brains
python -c "
import py_compile, pathlib
for d in ['seed_nodes','seed_brains']:
    for p in pathlib.Path(d).glob('*.py'):
        py_compile.compile(str(p), doraise=True)
print('All syntax OK')
"
```

### Run with Grok (xAI API)

```powershell
# 1. Set API key (one time)
$env:XAI_API_KEY = "your-key-here"

# 2. Ensure wiring.json has transport=xai (default)
# 3. Run
python organism.py --reset --max-ticks 5 "open notepad and write 'hello from grok'"
```

### Run with LM Studio (OpenAI-compatible)

```powershell
# 1. Start LM Studio local server at http://localhost:1234
# 2. Load model (e.g., nvidia-nemotron-3-nano-4b)
# 3. Change wiring.json: "transport": "openai"
python organism.py --reset --max-ticks 5 "open notepad"
```

### Run with File Proxy (Human-in-Loop, No Model)

```powershell
# 1. Change wiring.json: "transport": "file_proxy"
python organism.py --reset --max-ticks 5 "open notepad"

# 2. Watch comms/request.json appear
# 3. Write response to comms/response.json
# 4. Organism continues
```

### Workbench (Optional)

```powershell
python workbench.py
# http://127.0.0.1:8800/ — status dashboard
```

---

## Next Immediate Tasks (Phase 5C)

| Priority | Task | File | Description |
|----------|------|------|-------------|
| 1 | **Filter observation output** | `desktop.py`, `seed_nodes/observe.py` | Return only actionable elements (non-zero rect, interactive roles), integrate hover_scan, add window tokens W1..Wn, classify role→action |
| 2 | **Format SCREEN text** | `desktop.py` | Human-readable formatted text for LLM: WINDOWS list, focused element, key elements with px/py/hwnd |
| 3 | **Implement Verify** | `seed_nodes/verify.py` | Evidence-based: check screen for step completion (e.g., "Notepad window visible", "text 'hello' present") |
| 4 | **Implement Reflect** | `seed_nodes/reflect.py` | Concrete diagnosis from last_error + last_result + screen, specific suggestion, route to retry/replan/escalate/give_up |
| 5 | **Implement Self-Modify** | `seed_nodes/self_modify.py` | Output wiring_patch record, use apply_wiring_patch + save_wiring |
| 6 | **Test Complex Goal** | — | `python organism.py --reset --max-ticks 20 "open Opera, go to linkedin.com, write post about Grok desktop, post to X"` |

---

## Handover Prompt for Next Session

> **Context**: endgame-ai Phase 5B complete. Execute node working — Grok writes Python, `exec()` runs it with full desktop namespace. Topology: planner→scheduler→observe→execute→verify→reflect→self_modify. All transports verified (xAI native, OpenAI two-pass, OpenCode, file_proxy). Workbench running.
>
> **Current Block**: Observe node returns full UIA tree (bloat). Needs filtering to actionable elements + hover scan integration + window tokens + SCREEN formatting.
>
> **Next Goal**: Implement filtered observation with hover_scan, then complete verify/reflect/self_modify nodes. Test with real goal: "open Opera, make LinkedIn + X posts about Grok desktop".
>
> **Key Files to Modify**:
> - `desktop.py` — add filtering, window tokens, SCREEN formatting, integrate hover_scan into observe()
> - `seed_nodes/observe.py` — return filtered elements dict keyed by id with px/py/hwnd/role/action
> - `seed_nodes/verify.py` — evidence-based judgment
> - `seed_nodes/reflect.py` — concrete diagnosis + recovery routing
> - `seed_nodes/self_modify.py` — wiring_patch output
> - `wiring.json` — update observe_config, prompts

---

## File Line Count (Current)

| File | Lines | Status |
|------|-------|--------|
| `brain.py` | 508 | ✅ Stable |
| `nodes.py` | ~250 | ✅ Stable |
| `organism.py` | 230 | ✅ Stable |
| `desktop.py` | ~780 | ⚠️ Needs filtering/formatting |
| `seed_nodes/planner.py` | 18 | ✅ Done |
| `seed_nodes/scheduler.py` | 15 | ✅ Done |
| `seed_nodes/observe.py` | 16 | ⚠️ Needs filtering |
| `seed_nodes/execute.py` | ~100 | ✅ Working |
| `seed_nodes/verify.py` | 18 | ❌ Stub |
| `seed_nodes/reflect.py` | 18 | ❌ Stub |
| `seed_nodes/self_modify.py` | 10 | ❌ Stub |
| `seed_nodes/satisfied.py` | 9 | ✅ Done |
| `seed_nodes/error.py` | 26 | ✅ Done |
| `workbench.py` + JS | ~500 | ✅ Working |

**Net capability**: 10 hardcoded verbs → unbounded Python via execute node. Self-evolving code via self_modify.