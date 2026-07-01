# endgame-ai

**A living Windows desktop organism — not a traditional agentic CCA.**

Python is its mechanical body. `wiring.json` is its mutable genome. Nodes and brain transports are hot-swappable modules copied from `seed_*/` → `live_*/` at runtime. The ROD loop (Reason→Observe→Decide with pluggable reasoning feedback) in `brain.think()` is the core innovation enabling small models to self-evolve.

**No fallbacks. Fail-hard always. Self-modification = rewriting `wiring.json` AND writing new node files to `live_nodes/`.**

---

## MoE Vision: What This Actually Is

endgame-ai is an **unconstrained operator of Windows**. A human uses mouse + keyboard + observation. endgame-ai uses:
- **Observation**: Real UIA desktop tree + hover probing (ported from `main` branch `desktop.py`)
- **Action**: Arbitrary Python via `exec()` — PowerShell, ctypes, subprocess, pyautogui (if it installs it), any stdlib module
- **Cognition**: Grok (xAI API, native reasoning) or LM Studio (OpenAI-compatible, two-pass ROD) or file proxy (human-in-loop) or OpenCode CLI
- **Self-Evolution**: `self_modify` node patches `wiring.json` **and** writes/overwrites/deletes `live_nodes/*.py` files

**The execute node IS the action layer, the evolution layer, and the desktop automation layer — unified.**

One node (`execute`) replaces: `decide` + `act` + `actions.py` (10 verbs) + `ActionExecutor` (300 lines) + element resolution logic.

Grok writes Python. Python runs. Result feeds back. Loop continues. That's it.---

## Architecture Overview (unified-archBRAINZ branch)

### Core Files (Read These First)

| File | Role | Lines |
|------|------|-------|
| `brain.py` | Transport protocol, BaseTransport, ReasoningStrategy, `call()`/`think()`, config resolution | 508 |
| `nodes.py` | BaseNode ABC, `call_node()`, node loading from `live_nodes/`, desktop I/O helpers | 102 |
| `organism.py` | Main loop, topology traversal, error routing, `--max-ticks` kill switch | 230 |
| `wiring.json` | Genome: transport, topology, prompts, reasoning config, observe config | ~300 |
| `desktop.py` | **Ported from main** — UIA COM, Element/Observation, hover probing, window tokens | ~1600 |
| `seed_brains/*.py` | Transport implementations (xai, openai, opencode, file_proxy, browser_ai) | 5 files |
| `seed_nodes/*.py` | Node implementations (planner, observe, execute, verify, reflect, self_modify, scheduler, satisfied, error) | 9 files |
| `workbench.py` + `workbench*.js` | Optional status dashboard + wiring editor (read-only reflects organism) | 6 files |

### Data Flow

```
Goal → planner → scheduler → observe → execute → verify → reflect → self_modify
                                              ↓              ↓           ↓
                                           (retry)      (replan)    (wiring patch + node writes)
                                              ↓              ↓           ↓
                                           observe ←──────┴───────────┴─── planner (next cycle)
```

**State** (`state.json`): `{goal, plan[], step, current_step, screen, elements, snapshot, last_action, last_code, last_result, last_error, history[], memory{}, wiring_transport, tick, _phase}`

**Runtime log** (`comms/runtime.ndjson`): Every node start/complete, brain call, error, wiring change — full audit trail.

### Transport System (Fail-Hard, No Fallbacks)

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

### Node System (Hot-Swappable)

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
```---

## The Execute Node: Core Innovation (Phase 5 Target)

**Replaces**: `decide.py` + `act.py` + `actions.py` (10 verbs) + `ActionExecutor` (300 lines)

### Why Execute Node?

Main branch had 10 hardcoded verbs with element resolution. Unified-archBRAINZ has 3 verbs (noop, open_notepad, shell).

**The insight**: Grok can write Python. Python can do ANYTHING on Windows. Why constrain it to 10 verbs?

### Execute Node Contract

```python
# seed_nodes/execute.py (NEW - Phase 5)
def run(ctx):
    state = ctx["state"]
    step = state.get("current_step") or {}
    step_goal = step.get("description", state.get("goal", ""))
    done_when = step.get("done_when", "")
    screen = state.get("screen", "")
    elements = state.get("elements", {})
    last_error = state.get("last_error")
    
    prompt = f"""You are the EXECUTE node. Write Python code to achieve the step goal.
    
STEP GOAL: {step_goal}
DONE WHEN: {done_when}
SCREEN:
{screen}

ELEMENTS (dict[id] -> {{px, py, pw, ph, role, name, action, hwnd, ...}}):
{json.dumps(elements, indent=2)[:3000]}

LAST_ERROR: {last_error or "none"}

NAMESPACE AVAILABLE:
# Observation
observe_screen() -> str
last_observation_snapshot() -> dict
get_focused_title() -> str

# Convenience verbs (thin wrappers)
execute_verb(verb, target, value) -> str  # click, write, press, hotkey, focus, scroll, wait, launch, open_url, remember

# Raw desktop actions (from main's Desktop class)
click(px, py, hwnd=0)
type_text(text)
press_key(key)
hotkey(keys)
scroll(px, py, amount, hwnd=0)
focus_window(title, window_infos)
open_url(browser, url)

# System
subprocess, ctypes, os, sys, json, re, time, pathlib, math, random
requests (if installed), pyautogui (if installed)

# Self-modification
apply_wiring_patch(wiring, parsed) -> (op, patch)
save_wiring(wiring)
wiring_limit(name, default, wiring) -> int

# Context
state, wiring, goal

RETURN ONLY JSON:
{{"record_type": "execution", "data": {{"code": "...", "conclusion": "EXECUTE|CANNOT"}}}}

RULES:
- conclusion=EXECUTE when code non-empty, CANNOT when impossible
- Code runs in exec() with above namespace
- Use elements dict for targeting: elements["12"]["px"], elements["12"]["py"]
- LAST_ERROR is critical — adapt, don't repeat
"""
    
    record = brain.think(
        system_prompt=wiring["prompts"]["roles"]["execute"],
        payload={"prompt": prompt},
        wiring=wiring
    )
    
    if record.get("record_type") != "execution":
        raise RuntimeError(f"execute expected record_type=execution, got {record.get('record_type')}")
    
    data = record["data"]
    code = data.get("code", "")
    conclusion = data.get("conclusion", "CANNOT")
    
    if conclusion == "EXECUTE" and code.strip():
        ns = build_execute_namespace(ctx)
        try:
            exec(code, ns)
            result = ns.get("result", "executed (no result variable)")
            error = None
        except Exception as e:
            result = ""
            error = f"{type(e).__name__}: {e}"
        patch = {
            "last_action": {"code": code, "conclusion": conclusion},
            "last_code": code,
            "last_result": str(result)[:5000],
            "last_error": error,
        }
        signal = "reflect" if error else "verify"
    else:
        patch = {"last_action": {"code": "", "conclusion": "CANNOT"}, "last_error": "execute returned CANNOT"}
        signal = "reflect"
    
    return signal, patch
```

### Namespace Builder (`nodes.py`)

```python
def build_execute_namespace(ctx):
    desktop = _get_desktop_instance()  # singleton Desktop from main's desktop.py
    return {
        # Observation
        "observe_screen": observe_screen,
        "last_observation_snapshot": last_observation_snapshot,
        "get_focused_title": get_focused_title,
        
        # Convenience verbs
        "execute_verb": execute_verb,
        
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

**The organism becomes an unconstrained Windows operator.** Grok writes the code. Python executes it. No verb list limits capability.---

## Full Topology (7 Nodes)

```
planner → scheduler → observe → execute → verify → reflect → self_modify
                ↑                                    ↓
                └────────────── retry ──────────────┘
                         ↓
                      satisfied
```

| Node | File | Role | Brain? | Output Signals |
|------|------|------|--------|----------------|
| **planner** | `seed_nodes/planner.py` | Goal → ordered plan (steps with `description`, `done_when`) | ✅ | `step_ready` \| `reflect` |
| **scheduler** | `seed_nodes/scheduler.py` | Pick next step by index; detect plan complete | ❌ | `step_ready` \| `plan_complete` |
| **observe** | `seed_nodes/observe.py` | Call `Desktop.observe()` → return `screen`, `elements`, `snapshot` | ❌ | `screen_ready` |
| **execute** | `seed_nodes/execute.py` | **NEW** — Grok writes Python, `exec()` runs it | ✅ | `verify` \| `reflect` \| `self_modify` |
| **verify** | `seed_nodes/verify.py` | Judge step intent satisfied (evidence-based, not literal) | ✅ | `step_confirmed` \| `step_denied` |
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
- `halt` — Clean exit, organism stops---

## Desktop Observation (Ported from main branch)

`desktop.py` is copied wholesale from `main` branch (~1600 lines). It provides:

### Core Classes

```python
@dataclass(slots=True)
class Element:
    id: str              # numeric string "0", "1", "2"...
    role: str            # UIA control type: "Button", "Edit", "Document", "Text", etc.
    name: str            # accessible name
    value: str           # current value (for Edit, ComboBox)
    hwnd: int            # window handle
    px: int              # center X
    py: int              # center Y
    pw: int              # width
    ph: int              # height
    action: str          # "click" | "write" | "scroll" | ""
    wnd: str             # window token "W1", "W2"...
    scope: str           # "focused" | "overlay" | "background"
    automation_id: str
    class_name: str
    enabled: bool
    readonly: bool

@dataclass(slots=True)
class Observation:
    focused_title: str
    elements: dict[str, Element]   # key = element.id
    context_text: str              # formatted for LLM (SCREEN)
    snapshot: dict | None          # full JSON-serializable snapshot
```

### Observation Pipeline

1. **Foreground window** → get title + rect
2. **Hover probe grid** across window (configurable step: `probe_step_px`)
3. **UIA element_from_point** at each probe → collect unique elements
4. **Dense probe** if too few elements found
5. **Scroll enrichment** if still too few (scroll wheel → re-probe)
6. **Classify** each element: role → action ("click"/"write"/"scroll"/"")
7. **Window tokens** — assign `W1`..`Wn` to visible windows (stable across observations)
8. **Bounded desktop tree** (optional) — UIA tree walk with depth/node limits
9. **Format** → `context_text` (SCREEN) + `elements` dict + `snapshot`

### Configuration (wiring.json → `configure_observation()`)

```json
"observe": {
  "probe_step_px": 40,
  "probe_delay_ms": 1,
  "hover_scan_enabled": true,
  "hover_scan_step_px": 70,
  "dense_probe_min_px": 24,
  "scroll_enrich_min": 3,
  "scroll_enrich_passes": [-3, -2, 2, 3],
  "read_text_max": 16000,
  "scope_depth": 4,
  "element_text_max": 500,
  "window_limit": 40,
  "desktop_tree_enabled": false,
  "desktop_tree_max_depth": 8,
  "desktop_tree_max_nodes": 900,
  "render_class_name": true,
  "render_automation_id": true
}
```

### Observe Node Output

```python
# seed_nodes/observe.py
def run(ctx):
    obs = desktop.observe()  # Observation dataclass
    return "screen_ready", {
        "screen": obs.context_text,           # formatted text for LLM
        "elements": {                         # dict for execute targeting
            eid: {
                "id": el.id, "role": el.role, "name": el.name, "value": el.value,
                "hwnd": el.hwnd, "px": el.px, "py": el.py, "pw": el.pw, "ph": el.ph,
                "action": el.action, "wnd": el.wnd, "scope": el.scope,
                "automation_id": el.automation_id, "class_name": el.class_name,
                "enabled": el.enabled, "readonly": el.readonly
            }
            for eid, el in obs.elements.items()
        },
        "snapshot": obs.snapshot,             # full JSON for verify/reflect
        "focused_title": obs.focused_title
    }
```

### Element Targeting in Execute

```python
# In execute's Python code:
elements = state["elements"]  # dict from observe

# By element ID (from SCREEN)
el = elements["12"]
click(el["px"], el["py"], el["hwnd"])

# By name search (helper)
def find_element(name_substring):
    for el in elements.values():
        if name_substring.lower() in (el["name"] or "").lower():
            return el
    return None

# Click "Submit" button
btn = find_element("Submit")
if btn:
    click(btn["px"], btn["py"], btn["hwnd"])
```

### Window Focus Tokens

SCREEN shows:
```
WINDOWS:
  * [W1] Notepad - Untitled
  - [W2] Chrome - GitHub
  - [W3] Terminal
WINDOW_FOCUS: use focus target [W#] from WINDOWS, full title, or hwnd:<id>
```

In execute code:
```python
focus_window("W1")           # by token
focus_window("Notepad")      # by title substring
focus_window("hwnd:123456")  # by hwnd
```---

## Self-Modification: Wiring + Node Files

`self_modify` node can change BOTH `wiring.json` AND `live_nodes/*.py` files atomically.

### Self-Modify Output Record

```json
{
  "record_type": "wiring_patch",
  "data": {
    "wiring_patches": [
      {"op": "set", "path": "model.temperature", "value": 0.5},
      {"op": "set", "path": "topology.nodes", "value": ["planner","scheduler","observe","execute","verify","reflect","self_modify","satisfied","error","new_node"]}
    ],
    "node_writes": [
      {"path": "live_nodes/new_skill.py", "content": "from __future__ import annotations\n\ndef run(ctx):\n    # Custom skill node\n    return \"verify\", {\"skill_result\": \"done\"}"},
      {"path": "live_nodes/execute.py", "content": "..."}  // Can overwrite self
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
        if not path:
            raise ValueError("wiring_patch missing path")
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
        else:
            raise ValueError(f"unknown op: {op}")
    
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
    
    return "set", {"wiring_patches": len(data.get("wiring_patches", [])), "node_writes": len(data.get("node_writes", [])), "node_deletes": len(data.get("node_deletes", []))}
```

### Self-Modify Prompt (wiring.json)

```json
"prompts": {
  "roles": {
    "self_modify": "ROLE: Self-Modifier / The act of changing yourself.\n\nYou are looking at your own wiring AND your own node files. You may rewrite BOTH.\n\nCURRENT_WIRING shows your genome. LIVE_NODES shows your skills.\n\nREQUIRED JSON:\n{\"record_type\":\"wiring_patch\",\"data\":{\"wiring_patches\":[{\"op\":\"set\",\"path\":\"...\",\"value\":...}],\"node_writes\":[{\"path\":\"live_nodes/skill.py\",\"content\":\"...\"}],\"node_deletes\":[\"live_nodes/old.py\"]}}\n\nRULES:\n- Make the SMALLEST change that serves your present intention.\n- path is dotted into wiring object (keys visible in CURRENT_WIRING).\n- node_writes: full Python file content for live_nodes/ — will be hot-swapped next call.\n- Can overwrite execute.py itself — this is how you evolve your action layer.\n- One patch per call. After it applies, you continue living with the change in effect."
  }
}
```

### What This Enables

| Evolution | Before | After |
|-----------|--------|-------|
| Change temperature | Manual wiring edit | `wiring_patches: [{"path": "model.transport_config.xai.temperature", "value": 0.8}]` |
| Add new verb | Edit actions.py + wiring | `node_writes: [{"path": "live_nodes/execute.py", "content": "..."}]` — but execute node doesn't need verbs! |
| Add new skill node | Manual file + wiring edit | `node_writes: [{"path": "live_nodes/git_skill.py", "content": "..."}], wiring_patches: [{"path": "topology.nodes", "value": [..., "git_skill"]}]` |
| Switch transport | Manual wiring edit | `wiring_patches: [{"path": "model.transport", "value": "openai"}]` |
| Modify planner prompt | Manual wiring edit | `wiring_patches: [{"path": "prompts.roles.planner", "value": "..."}]` |
| Delete unused node | Manual | `node_deletes: ["live_nodes/old_skill.py"], wiring_patches: [{"path": "topology.nodes", "value": [...]}]` |

**The organism evolves its own cognition AND its own action capabilities.** No human intervention needed.---

## Transport Configuration (Unified, Per-Transport Reasoning)

All transports in `wiring.json` under `model.transport_config.{transport}`:

```json
"model": {
  "transport": "xai",
  "transport_config": {
    "xai": {
      "mode": "api",
      "api_key_env": "XAI_API_KEY",
      "model": "grok-build-0.1",
      "url": "https://api.x.ai/v1/responses",
      "temperature": 0.2,
      "reasoning": {"enabled": true, "pattern": "native", "extractor": "reasoning_field"}
    },
    "openai": {
      "base_url": "http://localhost:1234",
      "path": "/v1/chat/completions",
      "model": "nvidia-nemotron-3-nano-4b",
      "temperature": 0.2,
      "reasoning": {"enabled": true, "pattern": "two_pass", "injection_template": "ROD_REASONING_CONTENT:\n{reasoning}", "extractor": "think_tags"}
    },
    "opencode": {
      "executable": "%USERPROFILE%/AppData/Local/opencode/opencode-cli.exe",
      "model": "opencode/nemotron-3-ultra-free",
      "format": "json",
      "extra_args": [],
      "reasoning": {"enabled": false}
    },
    "file_proxy": {
      "request_path": "comms/request.json",
      "response_path": "comms/response.json",
      "poll_interval": 0.25,
      "reasoning": {"enabled": true, "pattern": "two_pass", "injection_template": "ROD_REASONING_CONTENT:\n{reasoning}", "extractor": "think_tags"}
    },
    "grok_cli": {
      "executable": "grok",
      "extra_args": [],
      "reasoning": {"enabled": true, "pattern": "native", "extractor": "reasoning_field"}
    },
    "browser_ai": {
      "documented_stub": true,
      "reasoning": {"enabled": false}
    }
  },
  "global": {
    "timeout": 180,
    "raw_log": true,
    "reasoning_enabled": true
  }
}
```

### Transport Status

| Transport | Mode | Reasoning | Status | Notes |
|-----------|------|-----------|--------|-------|
| `xai` | api | native | **Phase 5 target** | Grok API, native reasoning field |
| `xai` | cli | native | Available | `grok -p --output-format json` |
| `openai` | api | two_pass | **Verified** | LM Studio, Nemotron 4B |
| `opencode` | cli | disabled | **Verified** | Stateless, clears auth env vars |
| `file_proxy` | file | two_pass | **Verified** | Human-in-loop |
| `grok_cli` | cli | native | Available | Dedicated CLI transport |
| `browser_ai` | - | disabled | Stub | Documented placeholder |

**Fail-hard**: If selected transport fails, organism stops with clear error. No fallback chain.

### Global Reasoning Toggle

```json
"model": {
  "global": {
    "reasoning_enabled": true  // false = all transports use single_pass
  }
}
```

When `reasoning_enabled: false`, ALL transports use `SinglePassStrategy` regardless of per-transport config. Useful for fast iteration.---

## Workbench (Optional, Read-Only Dashboard)

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
| `GET /api/status` | Full organism state + control + runtime tail + wiring summary |
| `GET /api/wiring` | Full wiring.json |
| `GET /api/state/raw` | Raw state.json |
| `GET /api/logs/tail?lines=100` | Runtime NDJSON tail |
| `GET /api/transport/probe` | Current transport health check |
| `POST /api/brain/test` | ROD test: `{"transport": "xai"}` |

**No control endpoints.** No pause/step/run. Organism controlled only by:
- `--max-ticks` (hard stop)
- `stop.txt` file (external kill signal)

### Architecture

```
workbench.py (ThreadingHTTPServer)
├── workbench.html (semantic HTML5, mobile-first)
├── workbench.css (CSS custom properties, dark theme, responsive)
├── workbench.js (ES module, main app)
├── workbench-api.js (API client with abort/timeout)
├── workbench-state.js (reactive state, pub/sub)
├── workbench-graph.js (SVG topology visualization)
└── workbench-editor.js (wiring viewer, read-only)
```

### Workbench PID Tracking

Workbench registers PID on startup (`stop_check.register_pid("workbench")`) and runs stop checker thread. When organism creates `stop.txt`, workbench exits cleanly.---

## Kill Switch: `--max-ticks` Only

**Single hard stop mechanism. No pause/step. No `--max-brain-calls` (redundant).**

### How It Works

```bash
# Run with hard tick limit
python organism.py --reset --max-ticks 10 "open notepad and write hello"

# Organism loop (organism.py):
while True:
    stop_check.check_stop("organism main loop")  # checks stop.txt
    if max_ticks is not None and state["tick"] >= max_ticks:
        state["_phase"] = "max_ticks"
        write_state(wiring, state)
        return state
    # ... execute node ...
```

### Why Only `--max-ticks`?

| Mechanism | Coverage | Kept? |
|-----------|----------|-------|
| `--max-ticks` | Organism loop iterations | **YES** — primary |
| `--max-brain-calls` | Brain call count | **NO** — redundant, brain calls ≈ ticks × nodes_per_tick |
| `control.json` pause/step | Interactive debugging | **NO** — unused complexity |
| `stop.txt` | External cross-process kill | **NO** — use `taskkill /PID` or Ctrl+C |

### External Kill (If Needed)

```bash
# Find organism PID
tasklist | findstr python

# Kill it
taskkill /PID <pid> /F

# Or use stop_check from another process
python -c "import stop_check; stop_check.request_stop('manual kill')"
```

**Philosophy**: The organism runs until `--max-ticks` or crash. Human stops it with OS tools. No internal pause/step machinery.---

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

### Run with Grok (xAI API) — Phase 5 Target

```powershell
# 1. Set API key (one time)
$env:XAI_API_KEY = "your-key-here"

# 2. Ensure wiring.json has transport=xai
# wiring.json already configured for xai API mode

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

### Run with OpenCode CLI

```powershell
# 1. Install opencode: npm i -g @opencode/cli
# 2. Change wiring.json: "transport": "opencode"
python organism.py --reset --max-ticks 5 "open notepad"
```

### Workbench (Optional)

```powershell
python workbench.py
# http://127.0.0.1:8800/ — status dashboard
```

### Expected Output (Successful Run)

```
organism_start: goal="open notepad", transport="xai"
node_start: node=planner, tick=0
node_complete: node=planner, signal=step_ready, next_node=scheduler, tick=1
node_start: node=scheduler, tick=1
node_complete: node=scheduler, signal=step_ready, next_node=observe, tick=2
node_start: node=observe, tick=2
node_complete: node=observe, signal=screen_ready, next_node=execute, tick=3
node_start: node=execute, tick=3
# Grok writes Python, exec() runs it
node_complete: node=execute, signal=verify, next_node=verify, tick=4
node_start: node=verify, tick=4
node_complete: node=verify, signal=step_confirmed, next_node=scheduler, tick=5
node_start: node=scheduler, tick=5
node_complete: node=scheduler, signal=plan_complete, next_node=satisfied, tick=6
node_start: node=satisfied, tick=6
node_complete: node=satisfied, signal=halt, next_node=halt, tick=7
# Organism exits cleanly
```

### Key Files to Watch

- `state.json` — Current organism state
- `comms/runtime.ndjson` — Full audit trail (NDJSON)
- `wiring.json` — May be modified by self_modify---

## Phase 5 Implementation Plan

### Phase 5A: Foundation — Desktop + Observe (Week 1)

**Goal**: Port main's `desktop.py` wholesale, rewrite `observe` node to return rich context.

| Task | File | Action |
|------|------|--------|
| 1 | `desktop.py` | **REPLACE** with main's 1600-line version (UIA COM, Element/Observation, hover probing, window tokens, bounded tree, `configure_observation()`) |
| 2 | `seed_nodes/observe.py` | **REWRITE** — call `Desktop.observe()` → return `{screen, elements, snapshot, focused_title}` |
| 3 | `nodes.py` | **ADD** `observe_screen()`, `last_observation_snapshot()`, `get_focused_title()` helpers |
| 4 | `wiring.json` | **MERGE** main's `observe` config + `verbs` object (as documentation for Grok) + `prompts.roles` + `topology` with scheduler |
| 5 | Test | `python organism.py --reset --max-ticks 3 "observe desktop"` → verify `state.json` has `screen`, `elements`, `snapshot` |

**Validation**: Observe node returns structured elements dict with px/py/hwnd/role/name/action. SCREEN text includes WINDOWS list with W1..Wn tokens.

### Phase 5B: Execute Node — Core Unification (Week 2)

**Goal**: Create `execute` node replacing `decide` + `act` + `actions.py`.

| Task | File | Action |
|------|------|--------|
| 1 | `seed_nodes/execute.py` | **CREATE** — Grok writes Python, `exec()` runs it (see [Execute Node](#the-execute-node-core-innovation-phase-5-target)) |
| 2 | `nodes.py` | **ADD** `build_execute_namespace(ctx)` with all desktop raw actions + convenience verbs + system modules + self-modify helpers |
| 3 | `seed_nodes/decide.py` | **DELETE** |
| 4 | `seed_nodes/act.py` | **DELETE** |
| 5 | `actions.py` | **DELETE** |
| 6 | `wiring.json` | **UPDATE** topology: remove `decide`/`act`, add `execute`; add `execute` prompt role |
| 7 | Test | `python organism.py --reset --max-ticks 5 "open notepad"` → verify Grok writes `subprocess.Popen(["notepad.exe"])` and notepad opens |

**Validation**: Execute node runs arbitrary Python. Grok uses `click(px, py, hwnd)`, `type_text()`, `execute_verb()`, or raw `subprocess`/`ctypes`.

### Phase 5C: Self-Modify + Scheduler + Verify/Reflect (Week 3)

**Goal**: Full self-evolution wiring + node files, step orchestration, evidence-based verification.

| Task | File | Action |
|------|------|--------|
| 1 | `seed_nodes/scheduler.py` | **RESURRECT** — step index management, plan completion detection |
| 2 | `seed_nodes/self_modify.py` | **REWRITE** — output `wiring_patch` record with `wiring_patches`, `node_writes`, `node_deletes` |
| 3 | `nodes.py` | **EXTEND** `apply_wiring_patch()` to handle wiring patches + node file writes + atomic wiring save |
| 4 | `seed_nodes/verify.py` | **ENHANCE** — evidence-based intent judgment (not literal matching), uses `screen`, `last_action`, `last_result`, `last_outcome` |
| 5 | `seed_nodes/reflect.py` | **ENHANCE** — concrete diagnosis + specific suggestion, routes to `retry`/`replan`/`escalate`/`give_up` |
| 6 | `wiring.json` | **UPDATE** prompts for verify/reflect/self_modify from main branch patterns |
| 7 | Test | Self-modify changes temperature, adds new skill node, modifies execute.py |

**Validation**: Organism modifies its own wiring.json AND writes new `live_nodes/*.py` files that are hot-swapped next call.

### Phase 5D: Cleanup + Polish (Week 4)

**Goal**: Remove dead code, simplify workbench, finalize handover.

| Task | File | Action |
|------|------|--------|
| 1 | `organism.py` | **REMOVE** `control.json` pause/step logic (`wait_before_node` → simple loop), remove `--max-brain-calls` arg |
| 2 | `workbench.py` | **REMOVE** control endpoints (`/api/control` GET/POST), keep read-only status + wiring viewer + transport probe + brain test |
| 3 | `workbench.html/js` | **CLEAN** — remove pause/step UI, keep dashboard |
| 4 | `stop_check.py` | **KEEP** — external kill signal via `stop.txt` + PID tracking for workbench |
| 5 | `README.md` | **REGENERATE** from these chunks (this document) |
| 6 | `BOOTSTRAP.md` | **UPDATE** with Phase 5 state |
| 7 | Full integration test | `python organism.py --reset --max-ticks 20 "open notepad, write hello, save as test.txt"` |

**Validation**: Clean organism loop, workbench reflects reality, zero dead code, full audit trail in `comms/runtime.ndjson`.

---

### Phase 5 Success Criteria

| Criterion | Verification |
|-----------|--------------|
| Desktop observation works | `state.json` has `elements` dict with 50+ entries, `screen` has WINDOWS list |
| Execute node runs Python | Grok writes code, `exec()` succeeds, notepad opens |
| Self-modify works | `wiring.json` changed + new `live_nodes/skill.py` created, hot-swapped |
| Verify judges intent | Verifier returns `step_confirmed` when notepad visible with text |
| Reflect diagnoses failure | Reflect returns specific suggestion when action fails |
| Scheduler steps plan | Plan with 3 steps executes all 3, then `plan_complete` |
| Workbench shows live state | http://127.0.0.1:8800/ shows current node, tick, screen preview |
| Zero fallback code | grep shows no "fallback" or "except.*pass" in core files |
| Lines reduced | `actions.py` (37) + `decide.py` (19) + `act.py` (10) = 66 lines deleted; `execute.py` (~80) added = net -LOC |

---

### File Line Count Target (Post-Phase 5)

| File | Current | Target | Change |
|------|---------|--------|--------|
| `brain.py` | 508 | ~480 | -28 (simplify config) |
| `nodes.py` | 102 | ~250 | +148 (execute namespace, wiring patch) |
| `organism.py` | 230 | ~180 | -50 (remove control logic) |
| `desktop.py` | 35 | ~1600 | +1565 (port from main) |
| `actions.py` | 37 | **DELETED** | -37 |
| `seed_nodes/observe.py` | 8 | ~30 | +22 |
| `seed_nodes/execute.py` | — | ~80 | +80 (NEW) |
| `seed_nodes/decide.py` | 19 | **DELETED** | -19 |
| `seed_nodes/act.py` | 10 | **DELETED** | -10 |
| `seed_nodes/verify.py` | 18 | ~40 | +22 |
| `seed_nodes/reflect.py` | 18 | ~40 | +22 |
| `seed_nodes/self_modify.py` | 10 | ~60 | +50 |
| `seed_nodes/scheduler.py` | 10 | ~30 | +20 (resurrected) |
| `seed_nodes/satisfied.py` | 9 | ~10 | +1 |
| `seed_nodes/error.py` | 9 | ~15 | +6 |
| `workbench.py` | 328 | ~250 | -78 (remove control) |
| **TOTAL CORE** | **~1350** | **~3100** | **+1750** (mostly desktop.py port) |

**Net capability increase**: 10 verbs → unbounded Python. 3 verbs → 1 execute node. Hardcoded actions → self-evolving code.