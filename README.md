# endgame-ai

A self-regulating Windows desktop automation organism. Pure Python 3.13, zero dependencies, raw ctypes.

Three mathematical pipelines (Lorenz, PID, Jacobian) govern behavior. LLMs provide intelligence. Mathematics provides controlled chaos — not stabilization.

---

## Current State (math-pulse branch)

Working system. Proven on both cloud (ACP/Claude) and local (LM Studio/gemma-4-e2b-it, 2B params).

### Proven Results (this session)

| Test | LM Studio (2B) | ACP (Claude) |
|------|-----------------|--------------|
| write file | 10 events, COMPLETE | 9 events, COMPLETE |
| open notepad + type hello world | 26 events, COMPLETE | 26 events, COMPLETE |
| read README + write summary | 17 events, 1108b content | 11 events, 202b content |
| describe screen to file | 15 events, COMPLETE | 9 events, 821b description |

### Key Breakthrough

The 2B local model now completes multi-step tasks. The fix: **plan-based execution**. Planner generates a plan ONCE. Python feeds steps to the actor sequentially without re-calling the planner LLM. The orchestrator IS the working memory that small models lack.

```
BEFORE: planner called every cycle → 2B repeats first step → stuck loop → halt
AFTER:  planner called once → plan=[A,B,C,D] → Python feeds A,B,C,D → done
```

### Self-Evolution (active)

- Tier 1: Lessons persist to lessons.txt across runs
- Tier 2: Reflector mutates prompts at runtime (min 200 chars enforced)
- Tier 3: Code modification — future
- Tier 4: Resurrection — future

---

## Architecture

```
observe(screen) → math.decide_next_role() → dispatch(role) → loop
                         │
         ┌───────────────┼───────────────────┐
         │               │                   │
    Lorenz fork     PID pressure      Jacobian sensitivity
    (chaos replan)  (reflector gate)  (verb effectiveness)
```

The **blackboard** (`Board`) holds all truth. `CONTEXT_POLICY` controls what each role sees.

Math decides WHO acts. LLMs decide WHAT to do. Each LLM has a `recipient` field to request who goes next. Math can override via Lorenz fork or PID-triggered reflection.

### Roles

| Role | Purpose | LLM calls |
|------|---------|-----------|
| Planner | Generates multi-step plan | Once per plan (not per step) |
| Actor | Executes one action per step | Once per step |
| Verifier | Confirms goal complete | Once when plan exhausted |
| Reflector | Diagnoses loops, writes lessons, mutates prompts | When PID > 0.5 |

---

## Next Session: Tree-Based Screen Representation

### Problem

The current screen data injected into LLM requests is a mess. Shortened items with cryptic tags and numbers — confusing even for humans. The actor sees:

```
[1] W Btn 'Close' x=2050 y=10 w=50 h=40
[2] W Edt 'File name:' x=1200 y=770 w=300 h=25
[3] I Img '' x=100 y=50 w=32 h=32
```

This format requires cognitive parsing that wastes model capacity.

### Hypothesis

If the screen description uses a **tree** format — like the Linux `tree` command for directories — LLMs will understand it natively because that's a representation they were trained on extensively.

### Proposed Changes

**1. Tree-formatted screen output**

```
Desktop
├── Notepad — *Untitled
│   ├── [1] Edit "File name:" (editable)
│   ├── [2] Button "Save"
│   └── [3] Button "Cancel"
├── Task Manager
│   ├── [4] Tab "Performance"
│   └── [5] Tab "Processes"
└── Taskbar
    ├── [6] Button "Start"
    └── [7] Button "Task View"
```

- Windows are top-level nodes (like directories)
- Elements inside windows are leaves (like files)
- Only interactive elements shown (non-interactive filtered out in Python)
- Element IDs in brackets for actor targeting
- Role labels only where needed (editable, disabled)

**2. Desktop as a window**

Currently the probe scans only the focused window. The fix: treat the entire desktop as a scannable surface. Taskbar becomes a subtree. All visible windows appear in the tree. The planner sees the full picture; the actor sees the focused window's subtree.

This unifies the scanning code (one tree-walk pattern for everything) and reduces edge cases.

**3. Plan as a tree**

Reuse the same tree representation for plans:

```
Goal: open notepad and type hello
├── 1. hotkey win+r
├── 2. write "notepad"
├── 3. hotkey return
├── 4. wait 2
└── 5. write "hello world"
```

Same format, same parsing, same cognitive model for the LLM.

**4. TUI rewrite — independent viewer**

The TUI must be:
- **Independent process** — stays open even when endgame-ai isn't running
- **File-watching** — monitors events.jsonl in real-time, updates when new events appear
- **Interactive** — keyboard controls:
  - `Space` = pause/unpause display
  - `Enter` = step forward one event
  - `←/→` = scrub through event history
  - `q` = quit
  - `e` = expand selected element (show full LLM request/response)
  - `s` = toggle screen view (full tree or collapsed)
- **Expandable panels** — click/select on:
  - Screen description → shows full tree the model received
  - LLM response → shows full JSON the model returned
  - Math state → shows Lorenz xyz, PID, stagnation, Jacobian
- **Playback controls** — like a media player:
  ```
  [|◄] [◄◄] [▶/❚❚] [►►] [►|]   Event 14/38   [=====>------] 37%
  ```

This gives human operators full debuggability: see exactly what the model sees, what it responds, and what Python does with the response.

---

## Usage

```
python main.py "goal" --backend acp --event-budget 50
python main.py "goal" --backend lmstudio --event-budget 100
python analyze_run.py events.jsonl
python tui.py events.jsonl
```

`acp`: Claude via kiro-cli (fast, reliable).
`lmstudio`: Local LLM at localhost:1234 (slower, requires simpler prompts).

---

## Files

```
main.py           Entry point, CLI
orchestrator.py   Math-driven loop, plan-based execution, role dispatch
state.py          Blackboard (Board), 3 math pipelines, context rendering
config.py         All constants, CONTEXT_POLICY
observer.py       UIA tree walk + cursor probe, element classification
actions.py        10 verb handlers (click, write, hotkey, press, scroll, wait, focus, read_file, write_file, cmd)
dispatch.py       LLM call wrapper + JSON extraction
llm.py            Backend transport (LM Studio HTTP / ACP JSON-RPC)
acp_client.py     ACP protocol client
win32.py          Raw ctypes: UIA COM, SendInput, window management
log.py            JSONL event emitter + budget counter
tui.py            Event viewer (to be rewritten as independent interactive TUI)
analyze_run.py    Post-execution statistics
prompts/          System prompts (mutable at runtime by reflector)
schemas/          JSON schemas with recipient field
```

---

## Design Rules

1. One loop. Mathematics controls scheduling.
2. No comments. No docstrings. This README is the documentation.
3. No magic numbers outside config.py.
4. No fallback modes. Dead code is wrong code.
5. The three mathematical laws are non-negotiable.
6. Prompts are mutable by the organism at runtime.
7. The blackboard is the single source of truth.
8. Fewer moving parts beats theatrical autonomy.
9. Tree format everywhere: screen, plans, history.
10. Events measure behavior — every `log.emit()` = 1 event toward budget.

---

## Mathematical Pipelines

### Lorenz Attractor (controlled chaos)

Stagnation feeds Lorenz ODE. When trajectory crosses wings (x sign change) AND stagnation > 0.4: force completely different approach. Prevents loops.

```
rho_eff = 28 + stagnation * 1.5 * 28
wing_cross + stag > 0.4 → clear plan, DIVERGE
attractor_energy → scales LLM temperature
```

### PID Controller (reflection gate)

Accumulates stagnation error. Promotes reflector when output > 0.5. Integral resets on step advance.

### Jacobian (sensitivity analysis)

Tracks `∂(screen_change)/∂(verb)`. Exposed to reflector for diagnosis.

---

## Difference from main branch

The `main` branch contains an older architecture (pre-math-pulse). This branch (`math-pulse`) is a complete rewrite:

- main: mode-based state machine, fixed role ordering, no math
- math-pulse: math-driven scheduling, plan-based execution, self-evolution, dual backend support

The branches will be merged when the tree-based screen representation is proven and the TUI rewrite is complete.

---

## Development Protocol

```
pyright (strict, 0/0/0)  →  run with simple goal  →  analyze_run.py  →  commit
```

Scientist Mode: test before claiming. Treat counter-intuitive ideas as hypotheses. Update plainly when results contradict expectations.

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
