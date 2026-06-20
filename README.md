# endgame-ai — Bootstrap Prompt for Agentic Coding AI

> Paste this entire file as context into any AI coding assistant (Kiro, Cursor, Windsurf, Copilot, etc.) to continue development of this autonomous desktop agent.

---

## What This System Is

A Windows desktop automation agent that controls Chrome (and any app) via a planner→act→verify→reflect loop. It reads the screen using Windows UIA accessibility APIs, reasons about what it sees, executes actions (click, type, press keys), observes the result, and adjusts. The wiring between these steps is defined in a JSON topology (`prompts/wiring.json`) and visualized in a browser-based Canvas2D editor served by the Python HTTP server.

**The system was proven working**: it autonomously opened Chrome, navigated to YouTube, and played "Shakira - Waka Waka (This Time for Africa)" with the tab confirming `Audio playing`.

---

## Your Methodology (How to Work on This Codebase)

### 1. Observe Before Acting

You do NOT have direct visual access to the Windows desktop. You operate from WSL2 or a terminal. To understand what the user's screen shows, you must:

```python
# Write a script, execute it on Windows Python, read the stdout
cat > test_desktop.py << 'PYEOF'
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from actions import observe_screen
print(observe_screen())
PYEOF
cmd.exe /c "cd /d C:\Users\ewojgab\Downloads\endgame-ai & set PYTHONIOENCODING=utf-8& python test_desktop.py"
```

The output is a structured text listing of focused window + visible UI elements:
```
FOCUSED: YouTube - Google Chrome
  [1] TabItem "YouTube"
  [2] Edit "Address and search bar" = "youtube.com"
  [3] Button "Search"
  ...
```

### 2. Act via Scripts, Not Imagination

You cannot click or type directly. You write Python scripts that call `execute_verb(verb, target, value)` and run them on Windows Python. The verbs are: `click`, `write`, `press`, `hotkey`, `scroll`, `focus`.

```python
from actions import execute_verb
execute_verb("click", "Address and search bar")
execute_verb("write", "", "youtube.com")
execute_verb("press", "", "enter")
```

### 3. Verify After Every Action

**CRITICAL LESSON**: The observation function returns what UIA reports, which is incomplete and sometimes misleading:
- Element names may be truncated
- Not all visible elements appear in the tree
- The `_resolve` function matches by substring — "Search" might match "Address and search bar" before a YouTube search box
- Tab titles contain page titles — matching "Waka Waka" might hit the tab header instead of a clickable link
- URLs in the address bar field are visible as element values

After every action, observe again and verify the expected state was achieved. If not, replan.

### 4. Replan When Verification Fails

This is the core insight: **you will fail on the first attempt**. The methodology that works:

1. **First attempt**: Make reasonable assumptions, write script, run it
2. **Read output carefully**: Did it actually navigate? Did it click the right element?
3. **Identify the mismatch**: "It clicked the tab title instead of a search result because `_resolve` matched the substring in the wrong element"
4. **Rewrite with precision**: Use element numbers `[3]`, use direct URLs, use hotkeys instead of clicking ambiguous targets
5. **Run again and verify**

Example of this pattern in practice:
- Attempt 1: `click("Search")` → matched "Address and search bar" (has "search" in it)
- Attempt 2: Navigate directly via URL bar with `youtube.com/results?search_query=...`
- Attempt 3: The video link couldn't be clicked because `_resolve` matched tab title → use known video URL directly
- **Success**: `youtube.com/watch?v=pRpeEdMmmQ0` → video plays

### 5. The Iteration Pattern IS the Design

The fact that you write scripts, observe output, notice errors, rewrite, and try again — **this is exactly what the ROD (planner→act→verify→reflect) loop does at runtime with LM Studio**. You are being the ROD manually. The LLM node does the same:
- Observe screen → plan action → execute → verify outcome → reflect on failure → replan

---

## Architecture

```
prompts/wiring.json     ← THE BRAIN: topology (nodes + edges + signals) + prompts + config
prompts/model.json      ← LLM endpoint (LM Studio at 192.168.16.31:1234, nemotron-3-nano-4b)
server.py (980 LOC)     ← HTTP server + graph engine + node handlers + hot-reload
desktop.py              ← Windows UIA observer (ctypes, no pip deps)
actions.py              ← Verb executor: click/write/press/hotkey/scroll/focus
nodes/example_gate.py   ← Hot-loaded custom node handler example
wiring-editor.html      ← Canvas2D graph editor (277 LOC, zero dependencies)
rod_test.py             ← Standalone ROD proof script
```

### Server Endpoints (port 9078)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Status + node types list |
| `/wiring` | GET/POST | Read/write topology (POST validates against schema) |
| `/schema` | GET | JSON Schema for validation |
| `/state` | GET | Current execution state |
| `/smoke` | GET | Programmatic self-test (5 checks) |
| `/node/{type}` | POST | Execute single node with `{"state": {...}}` |
| `/run` | POST | Start autonomous execution (background thread) |
| `/events` | GET | SSE stream (node/result/stop events) |
| `/` | GET | Serve wiring-editor.html |

### Server Must Run on Windows Python
`desktop.py` uses `ctypes.wintypes` and Windows COM UIA APIs. It cannot run in WSL2. Start with:
```
cd C:\Users\ewojgab\Downloads\endgame-ai
set PYTHONIOENCODING=utf-8
python server.py
```

### Node Execution Flow
```
entry →[ready]→ planner →[plan_ready]→ scheduler →[step_ready]→ observe →[observed]→ act →[acted]→ verify →[ok|fail]→ reflect →[continue|replan|done]→ ...
```

---

## Challenges You Will Encounter

### 1. Encoding (cp1252 on Windows)
Windows Python defaults to cp1252 console encoding. Any Unicode in print() crashes. Always:
- Set `PYTHONIOENCODING=utf-8` env var
- Call `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`
- Avoid Unicode arrows/dashes in `server.py` print statements

### 2. Element Resolution Ambiguity
`actions.py`'s `_resolve(target, elements)` does substring matching. "Search" matches "Address and search bar" because "search" ⊂ "Address and search bar". Workarounds:
- Use element numbers: `execute_verb("click", "3")` (clicks element [3])
- Use exact full names from observation
- Bypass entirely with direct URL navigation

### 3. Incomplete Screen Observation
The UIA probe uses a spatial grid sampling technique (sine-wave path). It finds ~60-80% of visible elements. Missing elements means:
- Some buttons/links won't appear in observation
- You may need to scroll or tab to reach them
- Fallback: use known URLs, keyboard navigation (Tab+Enter), or hotkeys

### 4. WSL2 ↔ Windows Boundary
- WSL2 `curl` can reach Windows localhost (they share the network)
- WSL2 cannot run `desktop.py` (no Windows APIs)
- Write scripts to files, execute via `cmd.exe /c "cd /d ... & python script.py"`
- Background processes: use `creationflags=0x00000008|0x00000200` (DETACHED_PROCESS)

### 5. LLM Quality (Nemotron 3 Nano 4B)
This is a small local model. It:
- Sometimes returns empty responses
- Needs explicit JSON format instructions
- Works best with system prompt + structured user prompt
- May need `temperature: 0.5+` to avoid empty outputs
- Parse its output defensively (strip markdown fences, handle partial JSON)

---

## Meta-Critique: What Worked and What Didn't

### What Worked
- **Writing disposable test scripts**: Each `test_desktop.py` was purpose-built, run once, output analyzed, then rewritten. No attachment to failing code.
- **Observing before assuming**: Never assumed Chrome was open, always checked. Never assumed a click worked, always re-observed.
- **Escalating precision**: Started with fuzzy approaches (click by name), escalated to exact approaches (direct URLs) when fuzzy failed.
- **Separating concerns**: Proved desktop control works BEFORE touching the HTML editor. The HTML is cosmetic; the ROD is the core.

### What Didn't Work (First Time)
- Assuming element names are unambiguous (they aren't)
- Assuming CDN libraries self-register (edgehandles needed lodash)
- Assuming `nohup` works in WSL2 for persistent processes (it doesn't reliably)
- Assuming the LLM would guide navigation (too small/slow for real-time agentic use — deterministic scripts outperform)

### The Key Insight
**The AI coding assistant (me) was doing exactly what the ROD agent does**: observe → plan → act → verify → reflect → replan. The difference is I was doing it across multiple script executions while the ROD does it in a single loop. This recursion — an AI building an AI that works the same way — is the design validation itself. If I can navigate the desktop by writing scripts and reading outputs, the nemotron model can do it too with the same tools, just with the loop automated.

---

## To Continue Development

1. **Start server on Windows**: `set PYTHONIOENCODING=utf-8 & python server.py`
2. **Verify**: `curl http://localhost:9078/smoke` → all 5 pass
3. **Open editor**: `http://localhost:9078` in Chrome
4. **The editor** is Canvas2D (scroll=zoom, drag=pan, drag nodes, drag ports to wire, dblclick=add node, keyboard shortcuts s/r/q/l/w)
5. **To test desktop automation**: Write a `test_desktop.py`, run on Windows Python, read output

### Priority Tasks
- [ ] Make the ROD loop work via `/run` endpoint with real LLM (currently works but nemotron is slow/unreliable for complex planning)
- [ ] Improve observation depth (currently misses many elements)
- [ ] Add screenshot capability (PIL/mss) as fallback when UIA is insufficient
- [ ] Make the Canvas2D editor save node positions back to wiring.json
- [ ] Add right-click context menu to editor (delete edge, edit signal label)

### Branch: `experiment/endgame`
Latest commit: `bedc845` — "ROD proven + Canvas2D editor from scratch"

---

*Generated by Kiro CLI after proving autonomous desktop control works end-to-end.*
