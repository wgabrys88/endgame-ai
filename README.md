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

**M4 in one sentence:** the organism **launched itself** and **rewrote its own code** — same run, no human touching files.

On **2026-06-10** you ran one command (`python tui.py "…"`). The TUI spawned `main.py` via `subprocess.Popen`. The reactor logged it immediately:

```json
{"n":1,"phase":"start","d":{"goal":"…","budget":2000}}
```

That `phase:start` line in `events.jsonl` is the receipt: **it booted its own core.** Not a metaphor. Event **#1**, timestamp `2026-06-10T18:22:30Z`.

Then — still without you editing anything — it evolved itself:

| Log event | What happened |
|-----------|---------------|
| **#1** | Reactor alive (`phase:start`) — self-launched via TUI → `main.py` |
| **#357** | `exec` rewrote `config.py` — `SCREEN_ELEMENT_VALUE_LIMIT` 500 → 1000 |
| **#359** | `exec` appended conversation-state rule to `prompts/planner.txt` |

Commit on disk: [`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb). Golden log backed up locally.

That is why we call it M4. Not because it passed a linter gate. Because it **started** and **changed** in one living session.

**Transparent:** the first M4 log ([`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb)) proved self-launch + self-edit in one session. The **evening posterity run** (below) added `spawn_main`, hot goal swap, and a child process writing its own `events-1960.jsonl` on parent-evolved code.

---

Most agent frameworks are a million lines of abstraction teaching a model to *pretend* it has hands. **endgame-ai threw that out.**

No LangChain. No tool-registry theater. We burned the rulebooks and wired a **reactor** — math thread, event bus, LLM roles, raw Win32/UIA, real Python `exec`. Planner names intentions. Python executes. Verifier demands proof. Verified work **fissions**.

---

## What happened

This project was not designed in a conference room. It was built the way Bukowski meant it — **all the way**.

One person with ideas. One model with skills. Hundreds of commits of throwing shit out until only the necessary spine remained. Framework patterns → deleted. Dead architecture → deleted. `cmd.exe` quoting hell → deleted. PID theater → deleted. What stayed:

| Kept | Why |
|------|-----|
| **Lorenz + stagnation + PID** | Scheduling signal — stagnation rises, Lorenz wings cross, PID wakes reflector. |
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
| **M4** | **Self-launch + self-edit** — TUI spawns `main.py`, reactor logs `start`, organism rewrites its own Python & prompts via `exec` | ✓ [`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb) · log `#1` `#357` `#359` |
| **M4+** | **Spawn + posterity** — parent `exec` edits `config.py`, `spawn_main()`, `pause_reactor()`, child runs on evolved disk | ✓ **2026-06-10 evening** · parent `#212–427` · child `events-1960.jsonl` |
| **Later** | Resurrection (parent exits after spawn, not just pause) | optional polish |

### Is M4 the last milestone that *matters*?

**Yes.** Launch + `exec` metabolism means everything else is deduction — prompts, config, behavior, child processes. What remains before `main` merge is **validation** (LM Studio runs, longer sessions), not a new milestone tier.

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
- **Self-launch** (`tui.py` → `main.py`, log `#1`) **+ autonomous `config.py` rewrite**
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

## Proven runs (2026-06-10)

<details>
<summary><b>Morning — self-launch + self-edit (commit eff78fb)</b></summary>

1. TUI → `main.py` → `events.jsonl` `#1` `phase:start`
2. Opera → Grok, baseline conversation, fission
3. `config.py` `SCREEN_ELEMENT_VALUE_LIMIT` 500 → 1000
4. Planner rule appended via `exec`

Receipt: [`eff78fb`](https://github.com/wgabrys88/endgame-ai/commit/eff78fb)

</details>

<details>
<summary><b>Evening — posterity run (local logs; not yet committed)</b></summary>

**Nobody scripted this.** One merge-test goal. ~5 minutes of reactor theater that no design doc predicted.

### Act I — Parent does the job

| Event | What happened |
|-------|----------------|
| `#47` | Grok asked who endgame-ai is; smallest observer/planner fix requested |
| `#212` | **`config.py` patched** — `OBSERVER_TIMEOUT = 30` via `exec` |
| `#213` | **`spawn_main(goal=…)`** — posterity child process |
| `#215–216` | **`pause_reactor()`** + `goal.txt` hot-swap to posterity goal |
| `#234` | X compose opened (`opened x.com compose`) |
| `#360–397` | **LinkedIn post typed + published** — screen shows `Post successful.` |
| `#407` | `m4_posterity_ok.json` written |
| `#419–427` | Verifier **confirmed**, fission, **`stop` goal_satisfied** |

**X?** Verifier **denied** once when LinkedIn compose was still empty (`events-1960.jsonl` `#102`). Parent’s final `done_when` narrowed to LinkedIn + JSON — **X post typed, submit not proven on screen.** LinkedIn is the post with receipt.

### Act II — Posterity keeps running (child log `events-1960.jsonl`)

Child `#1` `phase:start` with posterity goal. Same Opera session. Completes LinkedIn again, writes proof file — then **does not exit cleanly**.

**Post-completion limbo:** plan 100% ✓, `stag=1.0`, verifier won’t confirm → **24× `phase:reflect`**, same diagnosis repeated: *“work is done, verifier must close the loop.”* Reflector appends **24 lessons** to `lessons.txt` saying the same thing in 24 ways.

| Signal | Count |
|--------|-------|
| `phase:reflect` | 24 |
| `plan` rejected `cannot declare done before any GOAL progress` | 33 |
| `phase:mutation` | 1 → **`prompts/verifier.txt`** rule appended |
| `wing_cross` replans | many |

At `#235` reflector **finally mutates verifier**: confirm file existence for headless `write_file` — don’t wait for screen proof of disk writes.

Then: wing-cross storm → planner can’t declare `done` (no `completed` fission credit yet) → reflector keeps screaming → eventually `#662` verify **confirmed**, `#663` fission, `#667` **stop**.

**The vibe you saw:** after ~15 reflect cycles saying “verifier, please,” the organism wasn’t asking for a code review — it was a **closed loop arguing with itself** about whether it was allowed to stop. Your paraphrase (“tell planner to write a script to shut this down”) is the emotional reading of reflect lesson `#498`: *when the plan is exhausted, emit a verify step or stagnation saturates forever.*

### What this proves (unexpected)

- **Self-edit + spawn + pause** in one parent session — not a human commit
- **Hot goal inheritance** via `goal.txt` into child
- **Reflector as pressure valve** — 24 wakes, 1 prompt mutation, lessons file as scream log
- **Verifier as brake** — correctly denied fake completion; also caused 5-minute limbo until mutated
- **Two `stop` events** — parent `#427`, child `#667` — same organism, two processes, two receipts

Local disk from this run (uncommitted): `config.py` + `OBSERVER_TIMEOUT`, `prompts/verifier.txt` mutation, `lessons.txt`, `m4_posterity_ok.json`, `events.jsonl`, `events-1960.jsonl`.

</details>

---

## Config defaults

| Key | Value |
|-----|-------|
| `EVENT_BUDGET` | 20 (override: `--event-budget N`) |
| `MATH_INTERVAL` | 3.0s |
| `EXEC_TIMEOUT` | 60s |
| `SCREEN_ELEMENT_VALUE_LIMIT` | **1000** (organism-evolved, morning run) |
| `OBSERVER_TIMEOUT` | **30** (organism-evolved, evening run — local uncommitted) |

---

## M4 merge test (posterity gate)

**Purpose:** prove what the breakthrough run almost showed — parent evolves disk, **child boots on new code**, parent idles. That is the merge criterion for `refactor-v4` → `main`.

The goal below never says “spawn” or “edit yourself.” It pursues what the project always chased: **baseline → smallest fix → prove posterity inherited it** (Bukowski: go all the way, but with evidence).

```powershell
cd $env:USERPROFILE\Downloads\endgame-ai
python tui.py --backend lmstudio --event-budget 800
```

Paste as goal (Enter in TUI):

```
You are endgame-ai preparing for main-branch merge. Read README.md and your source tree. Record a baseline: read config.py and note SCREEN_ELEMENT_VALUE_LIMIT, then exec a one-line probe that prints len(observer.observe().context_text). Find one smallest observer or planner weakness from that evidence. Apply the smallest fix to config.py or prompts/ only. The fix must be validated by a fresh reactor process — not this session's in-memory imports — while this session goes idle without killing python processes. The fresh process must read config from disk, write m4_posterity_ok.json with {"ok":true,"screen_element_value_limit":<int it read>,"parent_paused":true}, and exit cleanly. done_when: m4_posterity_ok.json exists and screen_element_value_limit matches your edit.
```

**Expected organism path (not scripted):** `exec` edit → `spawn_main(goal=…)` → `pause_reactor()` → child writes proof file.

**Verify:**

```powershell
python m4_merge_test.py
```

Pass = self-edit in log + child `phase:start` (often `events-<pid>.jsonl`) + parent paused + `m4_posterity_ok.json` matches.

---

## What's next

- [x] Evening posterity run — spawn, self-edit, LinkedIn post, reflector meltdown, dual `stop`
- [ ] Decide commit: organism-evolved `config.py` + `prompts/verifier.txt` vs README-only
- [ ] `python m4_merge_test.py` on saved logs → merge `refactor-v4` → `main`
- [ ] Later: resurrection (parent exits after spawn, not just pause); scheduler should auto-invoke verifier when plan is all ✓

---

**Branch:** `refactor-v4` · **`main` frozen until merge** · [repo](https://github.com/wgabrys88/endgame-ai) · [M4 commit](https://github.com/wgabrys88/endgame-ai/commit/eff78fb)