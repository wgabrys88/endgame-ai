# endgame-ai

> You are building a system that works like you work.

## The Prompt

You are an autonomous desktop agent. You cannot see the screen. You cannot click. You cannot type. What you CAN do: write a Python script, execute it, and read its stdout. That stdout contains a structured observation of the screen. Based on that observation, you reason about what action to take, write another script that performs that action, execute it, read the result, and observe again.

This is the ROD loop: **Read → Orient → Decide → Act → Verify → Reflect**.

When your action fails — and it WILL fail — you do not retry blindly. You read the observation, identify WHY it failed (wrong element matched, page didn't load, ambiguous target), change your approach, and try again with more precision.

You are not special. A 4-billion-parameter model running locally can do this same loop. The methodology works because:
1. Each step is small (one verb: click, write, press)
2. Verification is immediate (observe after every action)
3. Failure is expected and handled (replan, escalate precision)
4. The topology constrains the flow (no unbounded reasoning)

---

## Architecture: ROD → Slot → Colony

### ROD (single task, single desktop)
One loop executing one goal. Nodes connected by signals in a DAG:
```
goal_inbox →[ready]→ planner →[plan_ready]→ scheduler →[step_ready]→ observe →[observed]→ act →[acted]→ verify →[ok]→ reflect →[continue]→ observe
                                                                                                        →[fail]→ reflect →[replan]→ planner
                                                                                                                          →[done]→ satisfied
```
Each node is a function: `(state, config) → {signals, state_patch}`. Some call the LLM, some call the desktop, some are pure logic. All state flows through a single dict. All decisions are edge labels.

### Slot (one server, one port, one instance)
A running ROD is a slot. It binds to a port (`9077 + slot`), serves an HTML editor for its wiring topology, accepts goals via HTTP, and streams progress via SSE. The slot's brain lives in `prompts/wiring.json` — change the topology and the behavior changes. No code modification needed.

### Colony (future: N slots, one coordinator)
Multiple slots, each with their own goal, coordinated via a bus. Slot 1 might control Chrome while Slot 2 controls VS Code. A manager slot assigns goals based on priority. Each slot is an independent process with its own port.

---

## How the LLM Fits

The model (`nvidia-nemotron-3-nano-4b` at `192.168.16.31:1234`) is called by exactly 4 nodes:
- **planner**: receives goal → outputs plan (list of steps)
- **act**: receives screen + current step → outputs action JSON `{verb, target, value}`
- **verify**: receives screen + expected outcome → outputs ok/fail
- **reflect**: receives failure history → outputs replan/continue/done

Each call is: system prompt (from wiring.json) + user prompt (assembled from state fields) → structured JSON response. The model doesn't need to be smart. It needs to be constrained. The topology does the thinking; the model fills in blanks.

---

## Files

```
server.py              990 LOC  HTTP server + graph engine + all node handlers
desktop.py             437 LOC  Windows UIA screen reader (ctypes, zero deps)
actions.py             148 LOC  Verb executor: click/write/press/hotkey/scroll/focus
wiring-editor.html     277 LOC  Canvas2D topology editor (pan/zoom/drag/wire)
rod_test.py             91 LOC  Standalone proof: opens Chrome, plays YouTube video
prompts/wiring.json    471 LOC  THE BRAIN: topology + prompts + config + limits
prompts/model.json      14 LOC  LLM endpoint config
prompts/wiring-schema.json  JSON Schema for topology validation
nodes/example_gate.py    7 LOC  Hot-loadable custom node
start.sh                       Launch script
```

Total: **2550 lines**. Complete autonomous agent + visual editor + desktop control.

---

## How to Make This Work

```bash
# On Windows (required — desktop.py uses Windows APIs)
set PYTHONIOENCODING=utf-8
cd C:\Users\ewojgab\Downloads\endgame-ai
python server.py
# → http://localhost:9078
```

Verify: `curl http://localhost:9078/smoke` → 5/5 pass

Give it a goal:
```bash
curl -X POST http://localhost:9078/run -H 'Content-Type: application/json' -d '{"goal": "open notepad and type hello world"}'
```

Watch: `curl -N http://localhost:9078/events` (SSE stream)

---

## What Was Proven

An AI coding assistant (Kiro/Claude) controlled this system end-to-end:
1. Wrote `test_desktop.py` scripts
2. Executed them on Windows Python via `cmd.exe /c`
3. Read stdout containing screen observations
4. Noticed failures (wrong element clicked, encoding crash, address bar matched instead of search box)
5. Rewrote with more precision (direct URLs, explicit element numbers, encoding fixes)
6. Achieved goal: Chrome → YouTube → Shakira Waka Waka → Audio playing

**The AI was doing exactly what the ROD does.** The recursive insight: an AI built an AI agent by demonstrating the agent's methodology manually. The nemotron model needs to do the same thing — just faster, in a loop, guided by the topology.

---

## Challenges (Permanent, By Design)

| Challenge | Why it exists | How ROD handles it |
|-----------|--------------|-------------------|
| Element ambiguity | UIA names overlap ("Search" matches address bar) | Verify after act, replan with element numbers |
| Incomplete observation | Spatial probe misses ~20-40% of elements | Scroll, Tab, or use known URLs |
| Model outputs garbage | 4B params, sometimes empty/malformed | Retry with temperature bump, parse defensively |
| Action has no effect | Click missed, page loading | Re-observe, wait, retry |
| Encoding crash | Windows cp1252 vs Unicode | PYTHONIOENCODING=utf-8, errors='replace' |

These aren't bugs. They're the reason the verify→reflect→replan loop exists.

---

## For AI Agents Continuing This Work

You are a system that observes, reasons, acts, and verifies. So is endgame-ai. Build it like you work:
- Small steps, each verified
- Expect failure, handle it structurally
- Don't reason forever — act, observe the result, adjust
- The topology constrains you — that's the feature, not the limitation
- State is a dict, decisions are edge labels, everything is inspectable

The goal is not artificial intelligence. The goal is artificial persistence — a system that maintains any task, for any duration, on a 4B local model, without human intervention, by being structurally unable to get lost.

---

*Branch: `experiment/endgame` | 2550 LOC | Zero pip dependencies | Windows + Python 3.13*
