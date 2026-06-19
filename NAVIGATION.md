# Navigation Knowledge — How to Improve Desktop Automation

Observations from testing and building this system. These are patterns that help
the LLM navigate a real Windows desktop successfully.

---

## Chrome Navigation Patterns

### Opening Chrome
1. If Chrome is already running → `focus "Chrome"` (window title match)
2. If not running → `hotkey win+r` → `write chrome` → `press enter`
3. Never write "google.com" in the Run dialog — write "chrome" first

### Navigating to a URL
1. Focus Chrome window first
2. `hotkey ctrl+l` to select address bar (more reliable than clicking it)
3. `write URL` — full URL including https://
4. `press enter`

### Chrome elements the system struggles with
- Address bar: sometimes labeled "Address and search bar", sometimes by URL content
- Tab targets: use exact tab title text from SCREEN
- The "New Tab" button is often not in the UIA tree — use `hotkey ctrl+t` instead
- Chrome's omnibox auto-suggestions interfere — press Escape before typing if old text shows

### What helps
- After focusing Chrome, wait for screen capture before acting
- Use keyboard shortcuts over clicking for Chrome navigation (more reliable):
  - `ctrl+l` → address bar
  - `ctrl+t` → new tab
  - `ctrl+w` → close tab
  - `alt+left` → back
  - `F5` → refresh

---

## General Windows Navigation

### The Win+R Pattern (most reliable app launch)
1. `hotkey win+r` — opens Run dialog
2. Wait for "Run" or "Open:" to appear in SCREEN
3. `write appname` — just the executable name (notepad, chrome, calc, cmd)
4. `press enter` — launches the app
5. NEVER press enter before writing the app name
6. NEVER write the goal text into Run — only the app executable name

### Focus vs Launch
- If app is visible in SCREEN → `focus "WindowTitle"` (no need to re-launch)
- If app is NOT in screen → launch via Win+R
- After focus, verify the window is actually in foreground before acting

### Element ID Targeting
- SCREEN shows elements as `[ID] Type "Name" (state)`
- Use the [ID] number or the "Name" text as target
- Partial name match works — "Notepad" matches "Untitled - Notepad"
- For unnamed elements, use the numeric ID

### Common Failures and Solutions
| Problem | Cause | Fix |
|---------|-------|-----|
| Same action repeats | LLM doesn't read SCREEN changes | Advance hints in guards |
| Click targets miss | Element moved after observation | Re-observe before click |
| Write goes to wrong field | Focus wasn't on the right element | Click target first |
| App not launching | Typed in wrong place | Ensure Run dialog is visible |
| DONE claimed prematurely | No evidence on screen yet | premature_done guard |

---

## How This Knowledge Should Be Encoded

These patterns should be captured in three places:

### 1. In prompts (unified.txt)
The LAUNCH section already encodes Win+R flow rules. Add Chrome-specific patterns
when Chrome navigation is consistently failing.

### 2. In guards (wiring.json)
`advance_hints` already handle the Win+R flow. Add Chrome-specific hints:
```json
{"verb": "hotkey", "target_contains": ["ctrl+l"], "screen_contains": ["chrome"], "hint": "NEXT: write URL in address bar"}
{"verb": "write", "screen_contains": ["chrome", "address"], "hint": "NEXT: press enter to navigate"}
```

### 3. In planner.txt
The planner should know standard sequences. Future improvement: inject
known-good sequences for common goals (open browser → URL) as examples
in the planner prompt.

---

## Testing Observations

### What the HTML Interface Shows
- `http://127.0.0.1:9077` loads the visual graph editor
- Nodes highlight green as they fire (SSE observation)
- Sidebar shows live state: current node, goal, response count
- Node Log shows signal flow history
- Click any node to inspect its type and configuration
- 🚀 Run: browser drives graph (step-by-step via HTTP)
- 🤖 Auto: server drives graph (POST /run, observe via SSE)
- ⚡ Interrupt: inject new goal mid-execution
- ⏩ Step: manual single-node advance

### What I Learned from Building the System
1. The LLM needs FULL screen context — truncation causes hallucination of targets
2. History feedback is critical — without it, the LLM repeats failed actions endlessly
3. Guards must be aggressive — the LLM will happily repeat win+r 10 times
4. Verification must be a separate LLM call with fresh screen — combining with act causes
   the LLM to confirm its own actions without evidence
5. The planner should output concrete desktop actions, not abstract descriptions
6. Keyboard shortcuts are more reliable than click targets for standard operations
7. The observe → act → verify cycle MUST have a fresh observation before verify —
   otherwise verify confirms based on stale screen data

---

## Future Improvements (wiring-only, no code changes)

1. Add `hotkey ctrl+l` hint after Chrome focus in advance_hints
2. Add Chrome URL-typing sequence to planner.txt as an example
3. Add `inspect` verb support — deeper re-observation when verify is uncertain
4. Add screen-change detection — if screen didn't change after action, auto-retry
5. Time-based pressure — if 60s pass without step advancement, escalate to replan

---

## Real LLM Performance (nvidia-nemotron-3-nano-4b via LM Studio)

- Simple response (1 word): ~7s
- Planner (goal decomposition): ~28s
- Act (decide action from screen): ~20-30s estimated
- Verifier (check evidence): ~20s estimated

A full cycle (plan + N * (act + verify)) with 4 steps will take ~4-5 minutes.
This is acceptable for autonomous operation but means:
- Guard loops are expensive (each blocked attempt costs 20-30s)
- Replanning costs ~30s
- Bus_check is instant (no LLM)
- Observe is instant (UIA capture)

For faster iteration during development, use `--no-desktop` mode with mock screen data.

---

## Chrome UIA Accessibility (discovered 2026-06-20)

### Problem
Chrome does NOT expose page content (buttons, inputs, text) via Windows UIA by default.
Even with `--force-renderer-accessibility`, React/JSX dynamic DOM is invisible.

### Solution
1. Launch Chrome with `--force-renderer-accessibility` (keeps default profile)
2. Add native HTML elements OUTSIDE the React root (`<nav>`, `<button>`, `<span>`)
3. Use `aria-label` on every interactive element
4. Use `role="toolbar"`, `role="status"`, `aria-live="polite"`

### What Works
- Native `<button aria-label="Step">` → visible as `Button "Step"` in UIA
- Native `<span role="status">` → visible as `StatusBar "Status"` with text content
- Chrome's `prompt()` dialog → visible as `Window "127.0.0.1:9077 says"` with `Edit "Goal:"` + `Button "OK"`

### What Does NOT Work
- React-rendered buttons (even with aria-label in JSX)
- SVG/Canvas elements (React Flow graph nodes)
- Dynamic DOM content inside `<div id="root">`

### Chrome Launch (preserves default profile)
```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --force-renderer-accessibility
```
No --user-data-dir needed when using default profile.
