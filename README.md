# endgame-ai

A desktop automation tool for Windows 11. Observes the screen, plans actions, executes them, verifies results, and learns from mistakes. Zero dependencies. Pure Python 3.13 + ctypes.

Repository: github.com/wgabrys88/endgame-ai

## Quick StartTry it with one command (using LM Studio as backend):```bashpython main.py "Open Notepad and type 'Endgame-AI is working!'" --backend lmstudio```------

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCHEDULER (chaos-governed)                    │
│  chaos < 0.5:  observe → plan → act → verify                   │
│  chaos >= 0.5: reflect (analyze what went wrong, try to fix)    │
│  chaos >= 0.7: emergency (reflect + reset + spawn analysis)     │
│  chaos >= 0.95 sustained 5 iterations: halt + spawn successor   │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   OBSERVER   │ │   PLANNER    │ │    ACTOR     │ │  REFLECTOR   │
│ Screen scan  │ │ Decides what │ │ Executes it  │ │ Learns from  │
│ via UIA COM  │ │ to do next   │ │ via verbs    │ │ mistakes     │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

Available verbs: click, write, press, hotkey, scroll, wait, focus, read_file, write_file, spawn_agent, cmd, done.

Multi-agent: spawn_agent starts another instance. Screen access serialized via lock file. Agents take turns like cooperative multitasking.

---

## How to Run

```
python main.py "goal" --backend acp
python main.py "goal" --backend lmstudio
python main.py --resume --backend acp
```

Run as Administrator. Backends: `acp` (Claude via kiro-cli in WSL2), `lmstudio` (local LLM at localhost:1234).

---

## Files

```
main.py              Entry point, CLI
orchestrator.py      Event-driven scheduler
state.py             Blackboard state, Lorenz chaos system
observer.py          Windows UIA screen observation
actions.py           12 verb handlers
dispatch.py          LLM call + JSON extraction
llm.py               Backend switching (LM Studio / ACP)
config.py            All constants
journal.py           Execution journal
lessons.py           Cross-run learning
persistence.py       State snapshots, evolution ledger
event_schema.py      Inter-agent event protocol
blackboard_controller.py  Blackboard CLI management
acp_client.py        ACP backend (WSL2 → kiro-cli)
win32.py             Raw ctypes: UIA COM, SendInput
```

---

## Goal Template

```
python main.py "Hey, you're endgame-ai at %USERPROFILE%\Downloads\endgame-ai. You're a desktop automation tool on Windows 11 — you can see the screen, use apps, run commands, and read/write files. Your code lives on github.com/wgabrys88/endgame-ai and you can use GitHub Desktop to push changes. [ENVIRONMENT: which apps and logins are available]. First take a moment to explore your environment — check what's on screen and what you're working with. Then: [TASK]. Done when: [OBSERVABLE CHECKPOINTS — verify each before claiming done]. Work step by step. If something fails twice, try a different way. For big tasks, start another instance to handle parts in parallel — pass it full context of what you know. Take your time." --backend acp
```

---

## Examples

### Example 1 — Self-Analysis (file operations, no GUI)

```
python main.py "Hey, you're endgame-ai at %USERPROFILE%\Downloads\endgame-ai. You're a desktop automation tool on Windows 11. Read your own source files: orchestrator.py, state.py, and config.py. Write a JSON summary to self_check.json with keys: total_lines, scheduler_modes (list them), chaos_thresholds (list the numeric values from code). Done when: self_check.json exists with correct data — verify with read_file. Take your time." --backend acp
```

### Example 2 — Multi-App Real Work (Chrome + GitHub Desktop + Opera)

```
python main.py "Hey, you're endgame-ai at %USERPROFILE%\Downloads\endgame-ai. You're a desktop automation tool on Windows 11. Chrome is installed and logged into GitHub. GitHub Desktop is installed and connected to wgabrys88/endgame-ai. Opera is installed and logged into X and LinkedIn. First check what's on screen and which apps are running. Then: go to your GitHub repo in Chrome and create an issue describing something you think could be improved in your architecture. Use GitHub Desktop to create a branch, commit a small fix to that issue, and push. Then use Opera to post on X about what you improved. Done when: issue exists, branch is pushed, post is live — verify each visually. Work step by step. If something fails twice, try a different way. Take your time." --backend acp
```

### Example 3 — Cross-Instance Coordination (spawns child)

```
python main.py "Hey, you're endgame-ai at %USERPROFILE%\Downloads\endgame-ai. You're a desktop automation tool on Windows 11. Chrome is installed and logged into GitHub. Download your own code from github.com/wgabrys88/endgame-ai as a ZIP from Chrome, unpack it to %USERPROFILE%\Downloads\endgame-ai-verify using cmd, and start that copy with a goal to read its own config.py and write a confirmation to verified.txt. After it finishes, read verified.txt to confirm. Done when: verified.txt exists with correct content. When starting the other instance, tell it exactly where it runs from, that it only needs read_file and write_file, and what to produce. Take your time." --backend acp
```

### Example 4 — Read GitHub + Find Bug + Fix (development workflow)

```
python main.py "Hey, you're endgame-ai at %USERPROFILE%\Downloads\endgame-ai. You're a desktop automation tool on Windows 11. Chrome is installed and logged into GitHub. GitHub Desktop is installed and connected to wgabrys88/endgame-ai. First explore what's on screen. Then open Chrome, go to github.com/wgabrys88/endgame-ai, and read through the README and a few source files on the web to understand the current state of the project. Look for something that could be more reliable, more concise, or use fewer tokens. Once you find something specific, use GitHub Desktop to create a branch with a descriptive name, make the improvement locally using read_file and write_file, commit via GitHub Desktop, and push. Done when: the new branch is visible on GitHub with your improvement committed. Work step by step. Take your time." --backend acp
```

### Example 5 — Continuous Improvement (self-directed)

```
python main.py "Hey, you're endgame-ai at %USERPROFILE%\Downloads\endgame-ai. You're a desktop automation tool on Windows 11. Chrome is installed and logged into GitHub. GitHub Desktop is installed and connected to wgabrys88/endgame-ai. Your job today: make yourself better. Start by reading your own orchestrator.py and state.py to understand how you work. Then identify one thing that could be simpler, faster, or more robust — maybe a function that's too long, a threshold that could be smarter, or a context builder that wastes tokens. Make the improvement. Test it by reading the result back and checking it makes sense. Then use GitHub Desktop to create a branch, commit your change with a clear message explaining what you improved and why, and push it. Done when: the branch with your improvement is pushed to GitHub. Take your time and think carefully about what actually matters." --backend acp
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
