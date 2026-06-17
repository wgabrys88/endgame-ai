# endgame-ai

Wiring-driven, self-evolving agentic runtime for Windows 11.
Single process, model-agnostic, ~1500 LOC Python.

## Status: Active Development

**Branch:** `codex-unify-bus`  
**Model:** `nvidia-nemotron-3-nano-4b@q6_k_xl` (4B params, 32k context)  
**Host:** LM Studio at `192.168.16.31:1234`

---

## Progress Ledger

### 2026-06-17 — Session 2: Reasoning-as-Memory Proven

**Key Discovery:** The model's `reasoning_content` field IS the reflection/mutation layer.
We don't need separate LLM calls for reflection — feed reasoning back as context and the
model self-corrects across iterations FOR FREE.

**Proven behaviors (real desktop runs):**
- Model uses `inspect` verb spontaneously when screen lacks detail
- Model self-corrects from failed approaches using prior reasoning
- Verifier catches premature DONE claims (actor says "done" but screen contradicts)
- Planner replans after max_attempts with history of what failed
- Full plan→act→verify→replan cycle completes end-to-end

**Architectural changes this session:**
1. All prompts rewritten: self-aware, dynamic ID warnings, inspect verb
2. `inspect` verb added — triggers `desktop.observe()` re-scan
3. Truncation limits raised massively (screen 8k, reasoning 2k, evidence 1k)
4. `max_tokens=4096` in model.json (was 2536)
5. Reflector/mutator unwired (reasoning IS reflection — under evaluation)
6. `_test_run.py` now executes actions + feeds reasoning back (IS the full runtime)
7. `max_attempts` uses wiring transitions (was hardcoded to reflector)

**Open questions:**
- Reflector: is reasoning_content truly sufficient, or do we need explicit diagnosis?
- Screen observation: "Program Manager" appears when no app focused (WSL2 artifact)
- Model repeats actions when reasoning feedback says "OK" (needs "already done" awareness)

### 2026-06-17 — Session 1: Architecture Built

**Built from scratch:**
- Generic Circuit class + Slot state machine
- All topology in `prompts/wiring.json` (transitions, context injection, verbs)
- Schema in prompts not API (strict schema kills reasoning on nemotron)
- LLM fallback: reasoning_content → content when content empty
- Goal complete lifecycle: planner returns empty → idle
- TUI: threaded, responsive, full req/resp display, PgUp/PgDn
- Level 0 mode: single implementor, no CommsOperator

**5-call curl proof:**
Nemotron self-corrected from "use notepad" → "use chrome" → "use screenshot" → "use Word
with exec:" across 5 reasoning iterations. Reasoning-as-memory works.

---

## Architecture

```
prompts/wiring.json ─── ALL behavior defined here
  ├── circuits: planner, actor, verifier (reflector unwired)
  ├── transitions: event → next_phase
  ├── verbs: click, write, press, hotkey, scroll, focus, inspect
  └── limits: max_attempts=5, reasoning_depth=5, max_tokens=4096

State machine (current):
  planner → actor → verifier → planner (loop)
                ↑         |
                └─────────┘ (verify_not_done → planner)
                            (max_attempts → planner)

Context injection per circuit:
  planner:  [goal, screen, history, bus_context, last_reasoning]
  actor:    [goal, task, contract, last_error, last_reasoning, screen]
  verifier: [task, contract, screen, evidence, last_reasoning]
```

## Files

| File | LOC | Purpose |
|------|-----|---------|
| `_test_run.py` | ~70 | Headless runtime (executes actions, feeds reasoning) |
| `tui.py` | 219 | Interactive TUI (threaded, PgUp/PgDn) |
| `colony.py` | 182 | Level 0 bypass, slot activation, CommsOperator |
| `slot.py` | 351 | Circuit + Slot state machine |
| `desktop.py` | 428 | Win32 screen observation + GUI actions |
| `llm.py` | ~100 | LM Studio client, reasoning extraction, logging |
| `actions.py` | 95 | Verb dispatch (click, write, press, hotkey, inspect...) |
| `bus.py` | 74 | Shared blackboard |

## Running

```bash
# Headless (logs to logs/)
python _test_run.py open opera and go to grok.com

# Interactive TUI
python tui.py
```

## Logs

All runs preserved in `logs/YYYYMMDD_HHMMSS.txt` — full LLM request/response, no truncation.
Never delete log data during active development.
