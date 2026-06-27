# Endgame-AI — Self-Operating Desktop System

A zero-dependency Windows desktop operator that replaces the human at the keyboard. Any AI brain — local model, file-based agent, or browser-hosted AI like grok.com — drives real mouse and keyboard actions through a closed observe-reason-act loop.

No API keys. No pip dependencies. No frameworks. The system can operate its own cognition source by typing prompts into a browser AI and reading responses from the screen.

Repository: https://github.com/wgabrys88/endgame-ai

## The ROD Architecture (Reason-Observe-Decide)

The core innovation is a **two-call LLM pattern** that produces reliable structured output from any model, including small local ones:

```
┌──────────────────────────────────────────────────────────────────┐
│  CALL 1: Same system + user prompt. Model responds freely.       │
│  Response captured as rod_output (thinking, reasoning, anything) │
├──────────────────────────────────────────────────────────────────┤
│  CALL 2: Same system prompt.                                     │
│  User = original prompt + "\nROD_REASONING_CONTENT:\n" + Call 1  │
│  Model sees its OWN previous reasoning as context.               │
│  Naturally produces clean structured JSON output.                │
└──────────────────────────────────────────────────────────────────┘
```

This works because the API is stateless — each call is fresh. By echoing the model's first response back as input, we simulate a "think then commit" flow. The model always produces better structured output on Call 2 because it has already worked through the problem on Call 1.

Cost: 2x LLM calls. Benefit: near-100% valid JSON, zero wasted output tokens on inline reasoning, no retries needed.

## Graph Topology

```
Goal Inbox → MoE Route → Planner → Scheduler → Bus Check → Observe → Act → Verify
                                                                  ↘ failure → Reflect
Reflect → retry Scheduler | replan Planner | escalate Self-Modify | give_up → Bus Post
Self-Modify → Planner (with patched wiring)
Scheduler plan_complete → Bus Post → Satisfied
```

Every node is a plain Python script (`nodes/*.py`) executed in a sandboxed namespace. The engine reloads scripts and wiring fresh each cycle — edit anything while running.

## Quick Start

```powershell
python engine.py
# Serves http://127.0.0.1:9077/ (workbench + API)

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/run `
  -ContentType 'application/json' `
  -Body '{"goal":"open notepad and type hello world"}'
```

## Brain Transports

Edit `prompts/model.json`:

| Transport | Config | How it works |
|-----------|--------|--------------|
| `openai` | `"host": "http://localhost:1234"` | LM Studio or any OpenAI-compatible endpoint |
| `file_proxy` | `request_path`, `response_path` | Engine writes request.json, external agent writes response.json |
| `browser_ai` | `"url": "https://grok.com"` | System opens browser, pastes prompt, reads response from screen |

All three transports return `(content, reasoning_content)` tuples. The ROD pattern works identically regardless of which brain is active.

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

| Role | record_type | Output |
|------|-------------|--------|
| Planner | `task` | `{"steps":[{"description":"...","done_when":"..."}]}` |
| Actor | `action` | `{"conclusion":"EXECUTE","actions":[{"verb":"...","target":"...","value":"..."}]}` |
| Verifier | `verdict` | `{"confirmed":true,"evidence":"...","reason":"..."}` |
| Reflector | `diagnosis` | `{"diagnosis":"...","suggestion":"...","should_replan":false}` |
| Self-Modify | `wiring_patch` | `{"op":"add_edge","payload":{...}}` |

## Allowed Verbs

| Verb | Target | Value | Meaning |
|------|--------|-------|---------|
| `click` | element id/name | empty | Click UI element |
| `write` | element or empty | text | Select all + type text |
| `press` | empty | key name | Single key press |
| `hotkey` | empty | chord (ctrl+s) | Key combination |
| `focus` | window token/title | empty | Bring window forward |
| `open_url` | browser name | URL | Open web location |
| `scroll` | element | signed int | Scroll element |
| `wait` | empty | milliseconds | Pause 100-30000ms |
| `launch` | app name | empty | Win+R → type → Enter |
| `remember` | memory key | value | Store in state.memory |
| `copy_codebase` | empty | empty | Snapshot repo to clipboard |
| `browser_ai_handoff` | label | request text | Submit to browser AI, store response |

## Confirm Rules (Accelerators)

Rules auto-confirm mechanical successes without calling the LLM verifier:

- `confirm_remember_action` — remember verb stored data
- `confirm_copy_codebase` — codebase snapshot written
- `confirm_llm_request_written` — external AI request file written
- `confirm_browser_ai_handoff` — browser AI returned response

Rules only confirm. They never deny or block.

## Self-Modification

When failures exhaust retries (max_attempts=7) and replans (max_replans=3), the system escalates to self_modify. It can patch its own wiring with 15 operations including add/remove nodes and edges, modify prompts, add rules, and change limits. Patches are validated before saving. Backups are created automatically.

## HTTP API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Workbench UI |
| `/health` | GET | Status |
| `/wiring` | GET/POST | Load or replace wiring |
| `/state` | GET/POST | Runtime state |
| `/run` | POST | Start goal loop |
| `/step` | POST | Single node execution |
| `/pause` `/resume` `/stop` | POST | Control active run |
| `/node/types` | GET | Available node scripts |
| `/node/<type>` | GET/POST | Read or write node code |
| `/codebase?format=text` | GET | Full repo snapshot |
| `/events` | GET | SSE stream |

## Design Principles

1. **Zero dependencies** — stdlib Python only. Runs on any Windows 10/11 Python 3.10+.
2. **Hot-reload everything** — wiring, nodes, model config read fresh each cycle.
3. **Actor cannot say DONE** — verifier owns completion judgment.
4. **Verb contract enforcement** — unknown verbs rejected before execution.
5. **ROD two-call** — model reasons on Call 1, commits on Call 2. Clean separation.
6. **Rules accelerate, never block** — confirm-only rules bypass LLM for obvious truths.

## Handover Prompt (For Any AI Agent)

```
CONTEXT: endgame-ai project
REPO: https://github.com/wgabrys88/endgame-ai
PYTHON: engine.py + runtime.py + desktop.py + actions.py + nodes/*.py
CONFIG: prompts/wiring.json (topology + rules), prompts/model.json (transport)

ARCHITECTURE: ROD (Reason-Observe-Decide)
- call_node() does TWO LLM calls per node execution
- Call 1: model reasons freely with full context
- Call 2: model's own Call 1 output echoed back as ROD_REASONING_CONTENT
- Model sees its prior thinking and produces clean JSON on Call 2
- This pattern works with any model size, any transport

GRAPH: goal_inbox → moe_route → planner → scheduler → bus_check → observe → act → verify
       verify confirmed → scheduler (advance step)
       verify denied → reflect → retry|replan|escalate|give_up

TRANSPORTS: openai (LM Studio), file_proxy (any agent), browser_ai (grok.com via GUI)
All return (content, reasoning_content) tuples.

VERBS: click, write, press, hotkey, focus, open_url, scroll, wait, launch,
       remember, copy_codebase, browser_ai_handoff

RULES: 4 confirm-only accelerators. No deny rules (they caused deadlocks).

LIMITS: max_attempts=7, max_replans=3, max_self_modify=3, max_cycles=300

HOW TO RUN:
  python engine.py  (serves port 9077)
  POST /run {"goal":"..."} to start
  GET /state to check progress
  Edit prompts/model.json to switch brain transport

CRITICAL RULES:
- NO pip dependencies (stdlib only)
- NO test frameworks
- .gitattributes enforces CRLF
- System requires native Windows Python (UIA via ctypes)
```

## License

MIT
