<div align="center">

# endgame-ai

**~2,900 lines of Python. Zero pip dependencies. A Windows desktop organism that plans, sees, acts, verifies — and rewrites its own source while running.**

[![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?logo=windows)](https://github.com/wgabrys88/endgame-ai)
[![Dependencies](https://img.shields.io/badge/pip%20install-none-brightgreen)](.)
[![Branch](https://img.shields.io/badge/branch-refactor--v4-orange)](.)
[![LOC](https://img.shields.io/badge/core-~2900%20LOC-blueviolet)](.)

*If you're going to try, go all the way. Otherwise, don't even start.*  
— Charles Bukowski

**That line has been in this repo since the beginning. It was never decoration. It was the spec.**

[Quick start](#quick-start) · [What happened](#what-happened) · [Architecture](#architecture) · [M4](#m4--the-moment-everything-became-possible) · [Run it](#quick-start)

</div>

---

## Read this twice

Most agent frameworks are a million lines of abstraction teaching a model to *pretend* it has hands.

**endgame-ai threw that out.**

No LangChain. No tool-registry theater. No “agentic design patterns” PDF. We burned the rulebooks and wired something else: a **reactor** — math thread, event bus, LLM roles, raw Win32/UIA, and a real Python `exec` metabolism. The planner names intentions. Python executes them. The verifier demands proof. Verified work **fissions** — the plan clears, power ticks up, the organism keeps living.

On **2026-06-10**, during a live breakthrough run, it **rewrote its own `config.py`** (`SCREEN_ELEMENT_VALUE_LIMIT` 500 → 1000) and **appended a rule to its own planner prompt** — while pursuing a goal, without a human editing files.

That commit is on GitHub: [`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb).

If that sounds fake, good. So did fission before we built the logic for it.

---

## What happened

This project was not designed in a conference room. It was built the way Bukowski meant it — **all the way**.

One person with ideas. One model with skills. Hundreds of commits of throwing shit out until only the necessary spine remained. Framework patterns → deleted. Dead architecture → deleted. `cmd.exe` quoting hell → deleted. PID theater → deleted. What stayed:

| Kept | Why |
|------|-----|
| **Lorenz + stagnation math** | Not cosplay — scheduling signal. Energy rises, wings cross, reflector wakes. |
| **Fission** | Verified milestone completes → plan resets → organism sustains. Nuclear metaphor, yes — but it's *math wiring*, not branding. |
| **Observer** | Hover probe first (browsers lie to trees), UIA tree second, merge, depth-indented `SCREEN`. |
| **`exec`** | Real Python in the reactor — not shell strings. The organism's metabolism. |
| **Event bus** | `log.emit()` — pause is a null sink; one choke point for truth. |

We did not build a chatbot with tools. We built a **self-sustaining loop** that can touch the desktop, touch its own files, and argue with a verifier about whether it actually accomplished anything.

---

## Architecture

Two threads. One organism. No framework babysitting the model.

```mermaid
flowchart TB
    subgraph MATH["MATH thread (every 3s)"]
        S[StagnationAgent] --> L[LorenzAgent]
        L --> SN[snapshot.json]
    end

    subgraph MAIN["MAIN loop"]
        SCH[Scheduler] --> P[Planner]
        P --> A[Actor]
        A --> V[Verifier]
        V -->|confirmed| F["⚛ Fission"]
        F --> SCH
        V -->|denied| SCH
        SCH --> R[Reflector]
        R --> SCH
    end

    subgraph SENSE["Grounding"]
        O[Observer: hover probe + UIA tree]
        E[events.jsonl via log.emit]
    end

    MATH -.->|energy, wing_cross, stag| SCH
    A --> O
    P -->|exec / read / write / wait| X[Python executes headless steps]
    MAIN --> E
    MATH --> E
```

**Headless** (no actor LLM): `exec`, `read_file`, `write_file`, `wait`.

**GUI** (actor LLM): click, focus, write, press — only when `gui_mode` exists.

**Exec environment** (injected, no imports needed): `BASE_DIR`, `Path`, `os`, `sys`, `json`, `time`, `subprocess`, `spawn_main()`, `enable_gui()`.

---

## M4 — the moment everything became possible

Milestones were never a corporate roadmap. They were **capabilities unlocking capabilities**.

| Milestone | What it means | Status |
|-----------|---------------|--------|
| **M1–M2** | See the desktop. Act on it. Verify. | ✓ |
| **M3** | Prompt self-evolution — reflector mutates prompts from runtime evidence | ✓ [`8901988`](https://github.com/wgabrys88/endgame-ai/commit/8901988) |
| **M4** | **Code evolution** — organism rewrites its own Python & prompts via `exec` while pursuing a goal | ✓ [`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb) |
| **M4+** | `spawn_main()` child reactor (infra exists, not yet proven in run) | ○ |
| **M4++** | Resurrection — kill self, relaunch new code | ○ not built |

### Is M4 the last milestone that *matters*?

**Yes — for the soul of the project.**

Once the organism can run real Python against its own tree, **everything else is deduction**:

- Prompt changes? `exec` or reflector.
- Config tuning? `exec` — proven.
- New behavior? Patch `.py`, import gate on `write_file`, or `exec` for direct writes.
- Spawn / resurrect? Engineering polish on top of metabolism — not a new class of life.

M4 is not “passed import gate.” M4 is: **can it change itself while chasing a goal, without you?**  
Forensic answer from the breakthrough run: **yes.**

What remains before `main` merge is **validation**, not vision: LM Studio backend, longer runs, spawn proof if you want it. Not another milestone pyramid.

---

## Quick start

```powershell
cd $env:USERPROFILE\Downloads\endgame-ai
python -c "import observer, engine, agents, actions, log, tui; print('OK')"
python tui.py "Your goal here" --backend acp --event-budget 500
```

| Key | Action |
|-----|--------|
| **Enter** | Goal input — hot-swap via `goal.txt` or launch |
| **Space** | Pause / resume (`log.emit` null sink) |
| **q** | Quit TUI |

**Requirements:** Windows 10/11 · Python 3.13 · [LM Studio](http://localhost:1234) or ACP (Kiro CLI in WSL2)

**Headless / debug:**

```powershell
python main.py "your goal" --backend lmstudio --event-budget 200
python debug_context.py planner --goal "test"
```

Project root is always `BASE_DIR` (directory containing `main.py`). Stay inside it.

---

## Why this is not your framework

<table>
<tr>
<td width="50%">

**Typical agent stack**

- 50+ dependencies
- Tool schemas as religion
- Shell/command as “code execution”
- Human merges every change
- “Autonomous” in the README only

</td>
<td width="50%">

**endgame-ai**

- 12 core `.py` modules + 4 prompts + 4 schemas
- Planner names intentions; **Python executes**
- `exec` with full `subprocess` + `spawn_main`
- **Autonomous `config.py` rewrite — proven**
- Verifier blocks fake milestones
- Fission keeps the organism alive

</td>
</tr>
</table>

We are not claiming omniscience. We are claiming something narrower and weirder: **a minimal reactor that can improve itself in production.** That is logically closer to “general capability” than another wrapper around `function_calling`.

---

## The tree

```
main.py          entry, respawn contract, goal board
engine.py        reactor loop + math thread + fission
agents.py        planner · actor · verifier · reflector · scheduler
actions.py       exec · verbs · spawn_main · import gate
observer.py      hover probe + UIA tree → SCREEN
log.py           event bus · pause · lock
tui.py           full-width dashboard
win32.py         raw ctypes — no pip
llm.py           LM Studio / ACP backends
prompts/         planner · actor · verifier · reflector
schemas/         strict JSON outputs
```

Runtime artifacts (`events.jsonl`, `snapshot.json`, `goal.txt`, `pause`, `gui_mode`, …) are created on run and gitignored. Keep-only policy — only the essential tree ships.

---

## Proven in one run (2026-06-10)

<details>
<summary><b>What the organism did — no human file edits</b></summary>

1. Read its own README, source, prompts, schemas
2. Launched Opera → Grok via `exec` + `subprocess`
3. Established baseline conversation (verifier **confirmed**, fission fired)
4. Diagnosed observer truncation → **`config.py` 500 → 1000**
5. Diagnosed multi-turn chat weakness → **planner prompt rule appended**
6. Stopped with `goal_satisfied` after verified progress

The receipt is commit [`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb). The golden `events.jsonl` was backed up locally — not in repo by design.

</details>

---

## Config defaults

| Key | Value |
|-----|-------|
| `EVENT_BUDGET` | 20 (override: `--event-budget N`) |
| `MATH_INTERVAL` | 3.0s |
| `EXEC_TIMEOUT` | 60s |
| `SCREEN_ELEMENT_VALUE_LIMIT` | **1000** (organism-evolved) |

---

## What's next

- [ ] **LM Studio** — full run on local backend (same reactor, different wire)
- [ ] **Merge `refactor-v4` → `main`** after you're satisfied with tests
- [ ] Optional: prove `spawn_main()` in a live run
- [ ] Optional: resurrection (detach → exit → relaunch new code)

---

<div align="center">

### We are wanderers who went all the way.

Not crazy. Not safe. **Committed.**

*If you're going to try, go all the way.*

<br>

**Branch:** `refactor-v4` · **`main` is frozen until merge**

[Repository](https://github.com/wgabrys88/endgame-ai) · [Latest M4 commit](https://github.com/wgabrys88/endgame-ai/commit/eff78fb)

</div>