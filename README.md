# Endgame-AI

Closed-loop autonomous Windows 11 desktop agent. Local LLM or remote backend observes the screen via UI Automation, plans semantically, resolves targets from fresh observation, executes via SendInput, verifies, reflects, and rewrites its own prompts during execution.

No dependencies. No pip install. Pure Python 3.13 + Windows.

---

## How to Run

```
python main.py "your goal here" --backend lmstudio
python main.py "your goal here" --backend acp
python main.py --resume --backend lmstudio
python main.py "your goal here" --backend acp --agent-id worker_1
```

Run as Administrator. The system needs UI Automation access.

**Backends:**
- `lmstudio` — local LLM via LM Studio HTTP API (default: `localhost:1234`)
- `acp` — remote via kiro-cli ACP protocol in WSL2

---

## Architecture

```
observer → planner → actor → execute → verify → reflect → loop
```

- **Observer** — walks the UI Automation tree + probes screen with cursor movement to discover elements. Produces numbered element list.
- **Planner** — decides WHAT to do next (semantic, no IDs). Modes: direct, parallel, done.
- **Actor** — resolves planner instruction to specific element IDs from fresh screen list. Outputs verb + target + value.
- **Execute** — runs the action (click, write, press, hotkey, scroll, wait, focus, read_file, write_file, spawn_agent, cmd, done).
- **Verifier** — confirms goal completion with evidence.
- **Reflector** — analyzes execution history, rewrites prompts, adds lessons, rewrites goals.

---

## Termination

No cycle caps. The system runs `while True` and terminates on:

1. **Done** — goal achieved, verified → exit 0
2. **Chaos halt** — chaos ≥ 0.95 sustained 5 iterations → exit 1
3. **Interrupt** — Ctrl+C → exit 1
4. **Inbox kill** — external kill command → exit 0

---

## Files

| File | Purpose |
|------|---------|
| main.py | Entry point, CLI |
| orchestrator.py | Core loop |
| state.py | Blackboard, EventBus, Lorenz chaos |
| observer.py | UI Automation tree walk + probe scan |
| actions.py | 12 verb handlers |
| dispatch.py | LLM call + JSON extraction |
| llm.py | LM Studio / ACP backend |
| config.py | All constants |
| journal.py | Execution journal |
| lessons.py | Learned insights CRUD |
| persistence.py | Blackboard state, evolution ledger |
| win32.py | Raw ctypes: UIA COM, SendInput |
| acp_client.py | ACP backend via kiro-cli |
| prompts/ | System prompts (rewritten by reflector during execution) |
| schemas/ | JSON schemas enforced on LLM output |
| blackboard/ | Inter-agent communication |

---

## Self-Improvement

The reflector rewrites `prompts/planner.txt`, `prompts/actor.txt`, and `prompts/verifier.txt` during execution based on concrete lessons from action history. The system also accumulates insights in `lessons.json` and maintains an evolution ledger across runs.

Prompts that ship in this repo are the starting genome. After execution, your copy diverges.

---

## Multi-Agent

The planner can decompose goals into parallel sub-goals. Each child runs the same architecture. Coordination happens via the blackboard (`blackboard/blackboard_state.json`). Screen access is serialized via file-based locking.

---

## Chaos System

Lorenz attractor drives self-regulation. Inputs: action diversity, progress, stagnation, repetition. Outputs: chaos level that gates behavior — blocks repeated actions, forces parallel decomposition, rejects premature done claims, and ultimately halts the system if it cannot self-correct.
