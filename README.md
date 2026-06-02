# Endgame-AI

A persistent, self-regulating, self-improving autonomous desktop agent. Event-driven architecture. Chaos-governed scheduling. Self-verifying execution.

No dependencies. No pip install. No frameworks. Pure Python 3.13 + Windows 11.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BLACKBOARD                                │
│                                                                  │
│  screen: str           screen_valid: bool     errors: list       │
│  console_log: list     chaos_level: float     iteration: int     │
│  history: list         goal: str              mode: str          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   OBSERVER   │ │   PLANNER    │ │    ACTOR     │ │  REFLECTOR   │
│ UIA tree +   │ │ Semantic     │ │ Resolves to  │ │ Rewrites     │
│ probe scan   │ │ decisions    │ │ element IDs  │ │ own prompts  │
│ → screen     │ │ → mode/action│ │ → verbs      │ │ → lessons    │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## Scheduler (Chaos as Arbiter)

```
chaos < 0.25 AND screen_valid:   observe → plan → act (full pipeline)
chaos >= 0.25 AND !screen_valid: plan_blind (no click/scroll)
chaos >= 0.5:                    reflect_only (reflector analyzes)
chaos >= 0.7:                    emergency (reflect + reset + distill)
chaos >= 0.95 sustained 5 iter:  halt → spawn successor → exit 1
```

Periodic: reflect every 5 iterations, distill every 10.

## Termination

1. Done — goal verified by verifier LLM with evidence → exit 0
2. Chaos halt — spawn successor agent, then exit 1
3. Interrupt — Ctrl+C → exit 1

## How to Run

```
python main.py "your goal here" --backend acp
python main.py "your goal here" --backend lmstudio
python main.py --resume --backend acp
```

Run as Administrator. Backends: `lmstudio` (local LLM at localhost:1234), `acp` (Claude via kiro-cli in WSL2).

## 12 Verbs

click, write, press, hotkey, scroll, wait, focus, read_file, write_file, spawn_agent, cmd, done.

Blind-mode verbs (no screen required): cmd, read_file, write_file, spawn_agent, wait, press, hotkey, done.

## Files

```
main.py              Entry point, CLI, signal handling
orchestrator.py      Event-driven scheduler, phase functions
state.py             Blackboard dataclass, chaos/Lorenz system
observer.py          UIA tree walk + sinusoidal probe scan
actions.py           12 verb handlers
dispatch.py          LLM call + JSON extraction with salvage
llm.py               LM Studio / ACP backend
config.py            All constants
journal.py           Execution journal
lessons.py           Cross-run learning
persistence.py       Blackboard snapshots, evolution ledger, IPC events
event_schema.py      Inter-agent event protocol
blackboard_controller.py  CLI for blackboard management
acp_client.py        ACP backend via kiro-cli in WSL2
win32.py             Raw ctypes: UIA COM, SendInput, VK_MAP
```

## Design Philosophy

The wiring is the intelligence. The LLM is the brain. Everything else is dumb, honest plumbing that gives it the best possible current picture of reality every iteration.

No RAG. No skills database. No MCP. No API wrappers. No frameworks.

---

## Self-Validation Protocol

The tests below are ordered by signal value. Each test is a self-contained goal string. Run them in sequence. Each must exit 0 before proceeding to the next.

### Test 1 — File Read + Write (Blind Mode Proof)

```
python main.py "Read 3 of your own source files: config.py, lessons.py, event_schema.py. After reading all 3, write a one-line JSON summary to validation_result.jsonl containing keys: files_read (count), status (pass or fail). Then emit done with the file path as evidence." --backend acp
```

Proves: read_file verb works, write_file verb works, planner sequences multi-step goals, done detection with evidence.

Success criteria: validation_result.jsonl exists with files_read=3 and status=pass.

### Test 2 — Self-Architecture Analysis

```
python main.py "Read orchestrator.py and state.py using read_file verb. Write a JSON analysis to self_analysis.json containing: scheduler_modes (list the 4 modes from _schedule function), blackboard_fields (list 5 key fields), chaos_thresholds (list the 4 threshold values). Then emit done with evidence." --backend acp
```

Proves: the system can read its own architecture and extract structured facts.

Success criteria: self_analysis.json exists with correct scheduler modes, field names, and threshold values matching code.

### Test 3 — Parallel Decomposition

```
python main.py "Decompose into 2 parallel children: Child 1 (agent_id=reader_1) reads config.py and writes its line count to child_1_result.txt. Child 2 (agent_id=reader_2) reads dispatch.py and writes its line count to child_2_result.txt. After both children complete, write combined_results.json with both line counts. Then emit done." --backend acp
```

Proves: parallel decomposition works, children complete independently, parent integrates results.

Success criteria: child_1_result.txt, child_2_result.txt, and combined_results.json all exist with correct line counts.

### Test 4 — Error Recovery (Blind Mode)

```
python main.py "Attempt to read a file that does not exist: nonexistent_file_xyz.py. When this fails, recover by reading config.py instead. Write recovery_proof.json with keys: failed_file, recovered_file, recovered_content_length. Then emit done." --backend acp
```

Proves: system handles errors without chaos spiral, planner adapts after failure, error shows in context.

Success criteria: recovery_proof.json exists with correct failed_file and positive recovered_content_length.

### Test 5 — Reflector Fires Under Pressure

```
python main.py "Attempt to read_file INVALID_PATH_1, then INVALID_PATH_2, then INVALID_PATH_3 (all will fail). After these failures trigger reflection, read config.py successfully and write reflection_proof.json with keys: total_failures_before_success (should be 3), final_chaos_level (numeric). Then emit done." --backend acp
```

Proves: consecutive failures raise chaos, reflector fires at iteration 5, system recovers and completes goal after reflection.

Success criteria: reflection_proof.json exists with total_failures_before_success=3 and chaos > 0.

### Test 6 — Self-Validation Meta-Test

```
python main.py "Read README.md using read_file verb. Find the Self-Validation Protocol section. Execute Test 1 by spawning yourself with the exact goal string from Test 1. After the spawned agent completes, verify validation_result.jsonl exists using read_file. Write meta_test_result.json with keys: test_executed (1), spawn_succeeded (true/false), validation_file_found (true/false). Then emit done." --backend acp
```

Proves: the system can read its own documentation, extract a goal, spawn itself with that goal, and verify the result. This is the recursive self-test.

Success criteria: meta_test_result.json exists with test_executed=1, spawn_succeeded=true, validation_file_found=true.

---

## The Bootstrap Goal

To run the full self-validation sequence as a single command:

```
python main.py "Read README.md using read_file verb. In the Self-Validation Protocol section you will find 6 tests numbered Test 1 through Test 6. Execute them in order. For each test: spawn yourself using spawn_agent with the exact goal string shown in the code block. After each spawn completes, verify the expected output file exists. If a test fails, record it and continue to the next. After all 6 tests, write bootstrap_report.json with keys: tests_attempted (number), tests_passed (number), tests_failed (list of failed test numbers). Then emit done with the report path as evidence." --backend acp
```

---

*"If you're going to try, go all the way. Otherwise, don't even start."*
