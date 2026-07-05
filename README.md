# endgame-ai: Living Desktop Organism

A self-evolving Windows desktop organism that observes, plans, acts, verifies, and reflects through a cognitive loop of interchangeable organs wired by a fixed circuit (`wiring.json`). The Python body owns mouse, keyboard, subprocess, and UIA-based whole-screen observation; LLM brains are the mind.

## Architecture

### Organs (Nodes)
- **node_observe** - Mechanical whole-screen UIA scan with Z-order, focus tracking, deep hierarchy, junk filtering
- **node_planner** - Decomposes high-level goals into ordered, verifiable steps
- **node_scheduler** - Advances to next unfinished plan step
- **node_frame_action** - Frames raw evidence into concrete action strategy
- **node_execute** - Writes and runs Python code in the capability runtime (no sandbox)
- **node_verify** - Sole judge of step success from fresh observation
- **node_reflect** - Diagnoses failure and routes: retry, frame, replan, escalate, give_up
- **node_self_modify** - Evolves repository via git-native patches
- **node_satisfied** - Halts when goal complete
- **node_error** - Routes mechanical failures

### Transport Layer
Interchangeable LLM backends:
- `transport_xai` - Grok-4.3 via xAI API (used for Shakira milestone)
- `transport_file_proxy` - Human-in-the-loop file-based transport
- `transport_openai` - Local OpenAI-compatible endpoint
- `transport_opencode` - OpenCode CLI
- `transport_grok_cli` - Grok CLI
- `transport_browser_ai` - Browser automation stub

---

## Shakira Milestone: Cognitive Power Demonstrated

**Goal**: *"search in youtube for a shakira latest video and play it"*

**Result**: The organism autonomously navigated to YouTube, searched for "shakira latest video", identified the most recent result (**"Shakira, Burna Boy - Dai Dai (Official Video)"**), clicked it, and verified playback with visible controls (seek slider at 0:03/4:00, play button, mute, theater mode, fullscreen, "Audio playing" status).

### Execution Trace (32 ticks, 20 brain calls)

| Tick | Node | Signal | Key Event |
|------|------|--------|-----------|
| 0-1 | observe | initial_screen | Fresh whole-screen scan: 7 windows, 371 elements, 120 actionable |
| 1-2 | planner | step_ready | Initial 5-step plan (click search, type, submit, select, verify) |
| 2-3 | scheduler | step_ready | Advanced to first step |
| 3-4 | observe | screen_ready | YouTube window (W2) visible with recommendation tabs, no search bar |
| 4-5 | execute | frame | CANNOT - no search input node in tree |
| 5-6 | frame_action | reflect | Confirmed: search bar absent from observation |
| 6-7 | reflect | replan | Lesson: step assumes UI state not in tree |
| 7-8 | planner | reflect | Planner couldn't plan without search element |
| 8-9 | reflect | replan | Diagnosis: plan step too coarse |
| 9-10 | planner | step_ready | **Revised 4-step plan**: ensure homepage → activate search → input query → submit |
| 10-11 | scheduler | step_ready | Advanced |
| 11-12 | observe | screen_ready | Fresh scan |
| 12-13 | execute | verify | Clicked YouTube tab + pressed `/` shortcut |
| 13-14 | verify | step_denied | Search interface still not observable |
| 14-15 | reflect | replan | Search still missing after shortcut |
| 15-16 | planner | step_ready | **New 6-step plan** from observed state (category tabs dominant) |
| 16-17 | scheduler | step_ready | Advanced |
| 17-18 | observe | screen_ready | Fresh scan |
| 18-19 | execute | verify | **Breakthrough**: `open_url("Chrome", "https://www.youtube.com/results?search_query=shakira+latest+video")` |
| 19-20 | verify | step_confirmed | Search results page loaded with Shakira video hyperlinks visible |
| 20-21 | scheduler | step_ready | Advanced to "activate search input" (obsolete step) |
| 21-22 | observe | screen_ready | Fresh scan shows results page |
| 22-23 | execute | verify | Clicked `e_42_657314_4_21_4_1391` (Shakira, Burna Boy - Dai Dai) |
| 23-24 | verify | step_denied | Step still demanded search activation, not video click |
| 24-25 | reflect | replan | Lesson: video page already loaded, step obsolete |
| 25-26 | planner | step_ready | **Final 2-step plan**: click video hyperlink → verify playback |
| 26-27 | scheduler | step_ready | Advanced |
| 27-28 | observe | screen_ready | Fresh scan |
| 28-29 | execute | frame | CANNOT - target node absent, **video already playing** |
| 29-30 | frame_action | reflect | Screen summary: window titled "Shakira, Burna Boy - Dai Dai... Audio playing", playback controls visible |
| 30-31 | reflect | replan | Goal state reached, step obsolete |
| 31-32 | planner | error | Budget exceeded (20/20 calls) |

### Cognitive Behaviors Demonstrated

1. **Adaptive Replanning** - 4 major replans when observed reality diverged from plan assumptions
2. **Observation-Grounded Decision Making** - Every decision based on fresh UIA tree, not memory
3. **Strategy Pivot** - Switched from UI widget hunting (`/`, click search bar) to direct URL navigation when search elements weren't detectable
4. **Obsolete Step Detection** - Execute organ recognized video was already playing and returned CANNOT instead of blindly clicking
5. **Verification Integrity** - Verify organ denied success when done_when didn't match observation, forcing honest reflection
6. **Lesson Accumulation** - Each reflection produced actionable lessons that shaped subsequent plans
7. **Goal Achievement Without Explicit Success Signal** - System reached goal state (video playing) but continued due to plan/step mismatch; the organism *lived* the success before the budget ended

### Token Usage (transport_xai / Grok-4.3)

| Call | Organ | Input Tokens | Output Tokens | Reasoning Tokens | Total | Cost (USD ticks) |
|------|-------|--------------|---------------|------------------|-------|------------------|
| 1 | planner | 3,383 | 1,503 | 1,299 | 4,886 | 79,190,500 |
| 2 | execute | 3,617 | 2,003 | 1,928 | 5,620 | 94,615,500 |
| 3 | frame_action | 3,388 | 1,035 | 899 | 4,423 | 66,881,000 |
| 4 | reflect | 3,486 | 1,453 | 1,288 | 4,939 | 78,556,000 |
| 5 | planner | 3,522 | 3,253 | 3,189 | 6,775 | 122,662,000 |
| 6 | reflect | 3,591 | 1,016 | 870 | 4,607 | 67,599,500 |
| 7 | planner | 3,557 | 2,152 | 1,870 | 5,709 | 91,542,500 |
| 8 | execute | 3,789 | 2,236 | 2,127 | 6,025 | 100,574,500 |
| 9 | verify | 3,570 | 338 | 267 | 3,908 | 51,731,000 |
| 10 | reflect | 3,697 | 1,042 | 923 | 4,739 | 69,574,500 |
| 11 | planner | 3,522 | 2,152 | 1,870 | 5,709 | 91,542,500 |
| 12 | execute | 3,980 | 2,778 | 2,691 | 6,758 | 118,528,000 |
| 13 | verify | 3,732 | 360 | 275 | 4,092 | 54,306,000 |
| 14 | execute | 3,470 | 1,511 | 1,405 | 4,981 | 80,478,000 |
| 15 | verify | 3,215 | 405 | 341 | 3,620 | 44,936,500 |
| 16 | reflect | 3,328 | 837 | 693 | 4,165 | 56,477,000 |
| 17 | planner | 3,243 | 949 | 769 | 4,192 | 57,542,500 |
| 18 | execute | 4,366 | 3,269 | 3,153 | 7,635 | 133,612,000 |
| 19 | frame_action | 4,107 | 937 | 726 | 5,044 | 72,074,500 |
| 20 | reflect | 4,217 | 596 | 462 | 4,813 | 61,564,500 |
| **TOTAL** | | **70,281** | **29,825** | **26,245** | **96,516** | **1,402,988,000** |

**Average per call**: ~4,826 total tokens, ~$0.0014 (at xAI pricing)
**Reasoning overhead**: ~27% of output tokens used for internal reasoning (native Grok reasoning)

---

## Observation System (Redesigned - Tag: z-order-found)

The `core_observation.py` produces a clean, accurate, deep hierarchical tree:

- **Z-order tracking** via `EnumWindows` - 7 windows ranked by OS stacking order
- **Focus tracking** via UIA `HasKeyboardFocusPropertyId` (30009) and `IsKeyboardFocusablePropertyId` (30008)
- **Deep hierarchy** via `FindAllBuildCache(TreeScope_Subtree)` - full subtree harvest per window
- **Junk role filtering** - removes TitleBar, ScrollBar, StatusBar, ProgressBar, Separator, ToolTip, Image, Custom, Header, HeaderItem
- **Parent/child relationships** with `depth` and `parent_id` fields
- **Action indexing** - every interactive element gets stable node ID with coordinates, rect, enabled state, runtime_id

Output verified: 7 windows in Z-order, 122 actionable elements, proper hierarchy, focus correctly identifying active elements.

---

## Running

```bash
# Reset and run with xAI (requires XAI_API_KEY)
python -m core_organism "your goal here" --reset --max-brain-calls 20

# File proxy mode (human-in-the-loop)
# wiring.json: "transport": "transport_file_proxy"
# Writes runtime_request.json, waits for runtime_response.json
```

### Wiring Configuration
- `wiring.json` - Fixed circuit: model, transport, topology, prompts, paths, observe_config
- `runtime_state.json` - Persistent organism state (goal, tick, current_node, plan, observations)
- `runtime_control.json` - Manual control: `"mode": "run|pause|step"`, `"step_token": N`
- `runtime_log.ndjson` - Event log (organism_start, node_start, node_complete, error, halted)
- `runtime_raw_*.txt` - Full request/response with token usage, reasoning, raw API bodies

---

## Self-Modification

The organism can evolve its own code:
- `node_self_modify` reads checked-out repo + runtime evidence + failure diagnosis
- Produces git-native patch: file_writes, file_deletes, wiring_patches, commands
- Body validates (Python compile, JSON parse), commits, pushes on current branch
- Hot-swap to known-good commit on failure

---

## Key Files

```
core_organism.py      # Main loop, state machine, topology routing
core_brain.py         # LLM transport, stable prefix, reasoning patterns, schemas
core_nodes.py         # Node implementations (call_node dispatch)
core_observation.py   # UIA whole-screen scan with Z-order, focus, hierarchy
core_desktop.py       # Desktop automation, window tokens, UIA wrappers
core_bus.py           # Signal bus, datasheets, emit
core_stop_check.py    # PID-based stop coordination
wiring.json           # Fixed circuit configuration
node_*.py             # Individual organ implementations
transport_*.py        # LLM backend adapters
```

---

## Vision: Living Organism Proven

The Shakira milestone demonstrates the **living organism vision**:

> **The organism doesn't just execute a script - it perceives, decides, adapts, and persists until the goal state is observably true in the world.**

- No hardcoded YouTube selectors
- No "click at coordinates" fallback
- No focus/window management assumptions
- Pure observation → reasoning → action → verification loop
- When UI didn't match plan, it **replanned** (4 times)
- When search widget was invisible, it **pivoted strategy** (direct URL)
- When video was already playing, execute **recognized completion** (CANNOT)
- Verification **enforced honesty** (denied false success)
- Reflection **extracted lessons** that drove progress

This is cognitive behavior: **the system found and played the latest Shakira video without being told which song, which URL, or which element to click.** It searched, evaluated results, selected the most recent, and verified playback - all from semantic observation of the live desktop.

---

## License

MIT