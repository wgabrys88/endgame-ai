# Endgame-AI — Self-Operating Desktop System

A zero-dependency Windows desktop operator that replaces the human at the keyboard. A local 4B model (nvidia-nemotron-3-nano via LM Studio) drives real mouse and keyboard actions through a closed observe-reason-act loop, and hands off complex reasoning to Grok AI via browser automation.

No API keys. No pip dependencies. No frameworks. Proven working: the system navigated to grok.com, typed a question, and received a complete answer — all autonomously.

Repository: https://github.com/wgabrys88/endgame-ai

## Proven Results

On June 27 2026, the system was given the goal:

> "Open Opera, go to grok.com, and use it as your brain to figure out how to improve yourself."

What happened:
1. Planner decomposed into intent-based steps
2. Actor tried clicking Opera icon → CANNOT (not visible)
3. After 7 retries, escalated to self-modify
4. Replanned: use `launch opera` verb
5. Successfully launched Opera, navigated to grok.com
6. Typed exact question into Grok chat: "How can a local 4B model hand off complex reasoning to you via browser automation?"
7. Grok responded with a complete handover protocol (API key, Python bridge code, routing logic)

Three agents collaborated: **LM Studio** (local brain), **Endgame-AI** (executor), **Grok** (remote brain via browser).

## The ROD Architecture (Reason-Observe-Decide)

The core innovation is a **two-call LLM pattern** for intelligence amplification:

```
┌──────────────────────────────────────────────────────────────────┐
│  CALL 1: System + user prompt. Model reasons freely.             │
│  reasoning_content captured (or content if no reasoning field)   │
├──────────────────────────────────────────────────────────────────┤
│  CALL 2: Same system prompt.                                     │
│  User = original + "\nROD_REASONING_CONTENT:\n" + Call 1 output  │
│  Model sees its OWN reasoning, reconsiders, produces smarter JSON│
└──────────────────────────────────────────────────────────────────┘
```

This is NOT about JSON parsing reliability. It's about **making a 4B model think twice**. Call 2 reasoning tokens: 1249 (vs 67 without ROD). The model catches its own errors.

Cost: 2x LLM calls. Benefit: intelligence amplification from a tiny model.

## Graph Topology

```
Goal Inbox → MoE Route → Planner → Scheduler → Bus Check → Observe → Act → Verify
                                        ↑                                ↓
                                   Scheduler ←── confirmed ──────── Verify
                                        ↓ denied
                                     Reflect → retry | replan Planner | escalate Self-Modify | give_up
Self-Modify → Planner (with patched wiring)
Scheduler plan_complete → Bus Post → Satisfied
```

Every node is a plain Python script (`nodes/*.py`) executed in a sandboxed namespace. The engine reloads scripts and wiring fresh each cycle — edit anything while running.

## Quick Start

```powershell
# Start LM Studio with nvidia-nemotron-3-nano-4b model, reasoning mode ON
# Then:
python engine.py
# Serves http://127.0.0.1:9077/ (workbench + API)

# Send a goal:
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/run `
  -ContentType 'application/json' `
  -Body '{"goal":"open notepad and type hello world"}'

# Watch progress:
# Open http://127.0.0.1:9077/ in browser for visual workbench
# Or poll: curl http://127.0.0.1:9077/state
```

## Brain Transports

Edit `prompts/model.json`:

| Transport | Config | How it works |
|-----------|--------|--------------|
| `openai` | `"host": "http://192.168.16.31:1234"` | LM Studio or any OpenAI-compatible endpoint |
| `file_proxy` | `request_path`, `response_path` | Engine writes request.json, external agent writes response.json |
| `browser_ai` | `"url": "https://grok.com"` | System opens browser, pastes prompt, reads response from screen |

Current proven config (`prompts/model.json`):
```json
{
  "transport": "openai",
  "host": "http://192.168.16.31:1234",
  "model": "nvidia-nemotron-3-nano-4b",
  "temperature": 0.3,
  "temperature_bump": 0.15,
  "repeat_penalty": 1.06,
  "max_tokens": 16384,
  "thinking": {"budget_tokens": 4096},
  "timeout": 900
}
```

## File Structure

| File | Purpose |
|------|---------|
| `engine.py` | HTTP server, graph walker, node execution sandbox |
| `runtime.py` | LLM transports, ROD call_node, prompt assembly, rule evaluation, wiring patches |
| `desktop.py` | Windows UIA hover probes, element classification, input simulation |
| `actions.py` | Verb executor (click, write, press, hotkey, focus, open_url, scroll, wait, launch) |
| `nodes/*.py` | 14 exec-node scripts (entry, planner, act, verify, reflect, self_modify, etc) |
| `prompts/wiring.json` | Topology, role prompts, verb contracts, rules, limits |
| `prompts/model.json` | Active transport and model parameters |
| `wiring-editor.html` | Browser-based visual graph editor served by engine |

## LLM Role Contracts

Every role produces exactly one JSON record type:

| Role | record_type | Key design decision |
|------|-------------|---------------------|
| Planner | `task` | done_when is INTENT-based ("grok page visible") not literal ("title == Grok.com") |
| Actor | `action` | Uses verbs from SCREEN elements. CANNOT when target not visible. |
| Verifier | `verdict` | Judges SPIRIT of done_when, not literal string match |
| Reflector | `diagnosis` | should_replan=true after 3+ repeated CANNOT |
| Self-Modify | `wiring_patch` | Patches wiring/prompts when all retries exhausted |

## Allowed Verbs

| Verb | Target | Value | Meaning |
|------|--------|-------|---------|
| `click` | element id/name | empty | Click UI element |
| `write` | element or empty | text | Select all + type text |
| `press` | empty | key name | Single key press |
| `hotkey` | empty | chord (ctrl+s) | Key combination |
| `focus` | window token/title | empty | Bring window forward |
| `open_url` | browser name | URL | Open web location (target=browser!) |
| `scroll` | element | signed int | Scroll element |
| `wait` | empty | milliseconds | Pause 100-30000ms |
| `launch` | app name | empty | Win+R → type → Enter |
| `remember` | memory key | value | Store in state.memory |
| `copy_codebase` | empty | empty | Snapshot repo to clipboard |
| `browser_ai_handoff` | label | request text | Submit to browser AI, store response |

## Design Principles

1. **Zero dependencies** — stdlib Python only. Runs on any Windows 10/11 Python 3.10+.
2. **Hot-reload everything** — wiring, nodes, model config read fresh each cycle.
3. **Actor cannot say DONE** — verifier owns completion judgment.
4. **Intent-based verification** — "Opera window visible" matches "Grok - Opera" title.
5. **ROD two-call always** — model reasons on Call 1, commits on Call 2. Never skipped.
6. **Rules accelerate, never block** — confirm-only rules bypass LLM for obvious truths.
7. **Escalation ladder** — retry → replan → self-modify → give_up. Never stuck forever.

## Handover Prompt (For Any AI Agent)

```
CONTEXT: endgame-ai project — self-operating Windows desktop system
REPO: https://github.com/wgabrys88/endgame-ai
PYTHON: engine.py + runtime.py + desktop.py + actions.py + nodes/*.py
CONFIG: prompts/wiring.json (topology + prompts + rules), prompts/model.json (transport)

ARCHITECTURE: ROD (Reason-Observe-Decide) — ALWAYS two LLM calls per decision
- call_node() does TWO calls. Call 1: model reasons freely. Call 2: echoes reasoning back.
- thinking.budget_tokens=4096, max_tokens=16384 — give model room to think
- All 5 circuits (planner, actor, verifier, reflector, self_modify) use ROD uniformly

GRAPH: goal_inbox → moe_route → planner → scheduler → observe → act → verify
       verify confirmed → advance step. verify denied → reflect → retry|replan|self_modify

KEY LESSONS (from live calibration):
- Planner done_when must be INTENT-based, never predict exact window titles or URLs
- Verifier judges SPIRIT not literal equality
- Reflector must say should_replan=true after 3+ repeated CANNOT
- Actor must specify target browser in open_url (empty = system default = wrong browser)
- remember verb stores visible Text elements in memory
- copy_codebase verb needed before pasting codebase content
- max_attempts=7 then escalate to self_modify

HOW TO RUN:
  1. Start LM Studio with nvidia-nemotron-3-nano-4b, reasoning mode ON
  2. python engine.py (serves port 9077)
  3. POST /run {"goal":"..."} to start
  4. Watch at http://127.0.0.1:9077/ or GET /state

TRANSPORT: LM Studio at 192.168.16.31:1234 (openai-compatible)
VERBS: click, write, press, hotkey, focus, open_url, scroll, wait, launch,
       remember, copy_codebase, browser_ai_handoff
```

## License

MIT
