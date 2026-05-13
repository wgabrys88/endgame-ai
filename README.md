# Endgame-AI v7
(ready for self development runs, human (should) only monitor the process, or not - YOLO)

## Status

Fully Operational in local (LMStudio) and remote (ACP kiro-cli) modes.

Tested on browser automation tasks. Self-improvement loop verified - prompts evolve across runs without human intervention. Does not accumulate contexts/tokens - each turn uses the same amount of tokens +/- 20%

Tested with gemma-4-E4B via LMStudio - its operational now, yesterday it was complete mess. Did not worked with Local LLMs.

ACP Mode - works even more reliable than yesterday.

---

**It wasted 9 cycles failing. Then it rewrote its own brain. Next run: 4 cycles, zero failures.**

That's not a tagline - it's what happened. The system ran a task, failed repeatedly, analyzed its own mistakes, compressed the lessons into its prompts, and performed the same task 56% faster on the next attempt. No human edited the prompts. The machine did.

---


## What It Does Now

General-purpose desktop automation that improves with every task. No scripts. No recordings. No task-specific programming. Give it a goal in plain English, it figures out how to do it, and next time it's faster.

The prompts are under evolutionary pressure - they can never grow, only get denser. Low-value advice gets replaced by proven patterns. Natural selection on instructions.

## Technical Stack

- Python 3.13, Windows 11
- Zero external packages - pure stdlib + ctypes COM
- UI Automation via IUIAutomation COM interface
- Win32 input simulation (SendInput, keybd_event, mouse_event)
- LLM backends: local (LM Studio) or cloud (Claude via ACP)

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ PLANNER  │────▶│  ACTOR   │────▶│ REFLECTOR│
│ (what)   │     │  (how)   │     │ (learn)  │
└──────────┘     └──────────┘     └──────────┘
     │                │                 │
     │           Win32 APIs             │
     │          ┌─────────┐             │
     └─────────▶│ Windows │◀────────────┘
                └─────────┘
                  Desktop
```

