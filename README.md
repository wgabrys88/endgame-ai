# Endgame-AI

**Desktop operator that uses web AI (grok.com) as its brain — no API keys, no local GPU.**

The GUI is the universal API. The browser is the LLM transport.

---

## Architecture (proven June 26, 2026)

```
┌─────────────────────────────────────────────────────────────┐
│  GOAL IN → ROD LOOP → GOAL SATISFIED                        │
│                                                             │
│  ROD LOOP:                                                  │
│    plan → observe → act → verify → (next step or reflect)  │
│                                                             │
│  HANDS (Python, deterministic, never changes):              │
│    desktop.py — UIA hover probes — reads SCREEN             │
│    actions.py — verb executor — moves mouse/types keys      │
│                                                             │
│  BRAIN (LLM, swappable transport):                          │
│    transport=file_proxy  → AI agent reads/writes JSON files │
│    transport=openai      → localhost LM Studio              │
│    transport=browser_ai  → operator navigates to grok.com,  │
│                            types prompt, reads response      │
│                            (THE ENDGAME)                     │
│                                                             │
│  RULES (Python, fast, CONFIRM-ONLY):                        │
│    Auto-confirm steps when outcome is structurally obvious  │
│    NEVER deny. NEVER block. If unsure → call LLM verifier  │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Design Decision: Rules Are Accelerators, Not Guards

### The Problem (discovered in this session)

The rule system grew to 33 rules including 15+ deny/reject rules that:
- Blocked valid writes because goal contained a domain name
- Blocked valid Enter presses because done_when mentioned "response"
- Blocked valid remember actions because Grok's response ended with "?"
- Created unrecoverable deadlocks (advance_hints + deny = infinite loop)

Deny rules have ABSOLUTE PRIORITY over confirm rules in `evaluate_rules()`.
One false-positive deny = system can never complete the goal.

### The Fix

**Rules may only CONFIRM. Never deny. Never reject.**

If no confirm rule matches → the LLM verifier circuit runs.
The LLM verifier can say confirmed:false, which routes to reflect.
Reflect can retry or replan. No deadlocks.

### Rules to keep (confirm-only accelerators):

| Rule | What it does |
|------|-------------|
| `confirm_browser_open_url` | Auto-confirm when open_url verb succeeds |
| `confirm_focus_matches_done_when` | Auto-confirm when focus matches step |
| `confirm_write_to_writable` | Auto-confirm when write succeeds to edit/document |
| `confirm_remember_action` | Auto-confirm when remember verb stores data |
| `confirm_launch_verb` | Auto-confirm when launch succeeds |
| `confirm_save_hotkey` | Auto-confirm ctrl+s |
| `confirm_browser_navigation` | Auto-confirm ctrl+l navigation chain |

### Rules to remove (ALL deny/reject):

Every `deny_*` and `reject_*` rule. The LLM verifier handles edge cases.
Pure Python can confirm obvious successes. Only an LLM can judge ambiguity.

---

## The Endgame: browser_ai Transport

### Vision

```
endgame-ai needs LLM cognition
    │
    ├─ small/fast → Nemotron local (transport=openai, localhost:1234)
    │
    └─ complex/fallback → grok.com via browser GUI (transport=browser_ai)
          │
          ├─ focus Opera tab with grok.com
          ├─ click chat input [ID]
          ├─ write the prompt (system + user message as text)
          ├─ press enter
          ├─ wait for response to appear
          ├─ read response text from SCREEN observation
          └─ return parsed JSON to calling node
```

### Why This Works

1. endgame-ai already has HANDS (desktop.py + actions.py) that can operate any GUI
2. grok.com is free, no API key, no rate limit (reasonable use)
3. The operator uses its OWN observation/action system to talk to the brain
4. Self-referential: the operator operates itself

### Implementation (transport=browser_ai in model.json)

```json
{
  "transport": "browser_ai",
  "browser_ai": {
    "browser": "opera",
    "url": "https://grok.com",
    "input_element_hint": "Ask Grok anything",
    "response_wait_ms": 15000,
    "max_response_length": 4000
  }
}
```

The `llm()` function in server.py, when transport=browser_ai:
1. Calls desktop.py observe to find the grok tab
2. Calls actions.py to focus, click input, write prompt, press enter
3. Waits for response element to appear in SCREEN
4. Reads the response text
5. Returns (content, reasoning, raw) like any other transport

NO new dependencies. NO scripts. Uses existing verb system.

---

## Proven Results

### What works now (file_proxy transport, AI agent as brain):

| Goal | Status |
|------|--------|
| `open notepad and write what you know about the screen` | **satisfied:true** |
| `navigate to google.com in chrome` | **satisfied:true** |
| `open grok.com in opera` | **open_url succeeded, page visible** |
| `click chat input on grok.com` | **clicked at (666,333)** |
| `write "hello from endgame-ai"` | **typed 21 chars** |
| `press Enter to submit` | **Grok responded: "Hello! 👋 Nice to meet you"** |
| `remember response` | **BLOCKED by deny rules** ← the problem |

### What's needed:

1. Remove deny/reject rules → remember will work
2. Implement browser_ai transport → Grok becomes self-sustaining brain
3. Test full loop: goal → browser_ai → grok responds → satisfied

---

## File Inventory

| File | Lines | Role |
|------|-------|------|
| `server.py` | ~3480 | ROD loop, rules engine, LLM transports, state machine |
| `desktop.py` | ~1620 | UIA hover probes, SCREEN rendering |
| `actions.py` | ~290 | Verb executor (click, write, press, hotkey, focus, open_url, scroll, wait, launch, remember) |
| `colony.py` | ~45 | Multi-slot process manager |
| `prompts/wiring.json` | — | Topology, rules, roles, limits |
| `prompts/model.json` | — | Transport config |

---

## How to Run

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
python server.py
# API on :9078, panel on :9077
```

### Post a goal:
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/run `
  -ContentType 'application/json' `
  -Body '{"goal":"open notepad and type hello"}'
```

### Check state:
```powershell
Invoke-RestMethod http://127.0.0.1:9078/state
```

---

## AI Agent as Brain (file_proxy)

When `transport=file_proxy` in model.json, the server writes requests to
`comms/slot1_cognition/request.json` and polls for `response.json`.

Any AI agent acts as the brain by reading requests and writing responses.

### Request format:
```json
{"id":"llm-...", "status":"pending", "messages":[
  {"role":"system","content":"...ROLE: Planner/Act/Verifier/Reflector..."},
  {"role":"user","content":"SUBTASK: ...\nSCREEN: ...\n[1] Edit \"input\" @focused\n..."}
]}
```

### Response format:
```json
{"id":"<same>", "status":"complete", "choices":[{"message":{
  "content": "<JSON for the role>",
  "reasoning_content": ""
}}]}
```

### Role outputs:

| Role | JSON |
|------|------|
| Planner | `{"record_type":"task","data":{"steps":[{"description":"...","done_when":"..."}]}}` |
| Act | `{"record_type":"action","data":{"conclusion":"EXECUTE","actions":[{"verb":"...","target":"...","value":"..."}]}}` |
| Verifier | `{"record_type":"verdict","data":{"confirmed":true/false,"evidence":"...","reason":"..."}}` |
| Reflector | `{"record_type":"diagnosis","data":{"diagnosis":"...","suggestion":"...","should_replan":false}}` |

### Two-pass protocol:
- Pass A (no DECIDE NOW): respond with prose reasoning
- Pass B (has DECIDE NOW): respond with ONLY the JSON object

### Critical rules for Act:
- Use [ID] numbers from SCREEN for click/write/scroll targets
- @background elements have NO [ID] — cannot be targeted
- `launch` verb for deterministic app opening (Win+R sequence)
- `open_url` verb for browser navigation

---

## Execution Plan

### Phase 1: Surgery (next commit)
- Remove ALL deny_* and reject_* rules from wiring.json
- Remove advance_hints deadlock logic from server.py
- Keep only confirm_* rules
- Result: system can never deadlock on valid actions

### Phase 2: Prove (same session)
- Restart server with clean rules
- Post grok.com goal
- Act as file_proxy brain (Kiro)
- Demonstrate: satisfied:true with response in MEMORY

### Phase 3: browser_ai Transport (next session)
- Add browser_ai transport handler to server.py llm() function
- Uses existing desktop.py observe + actions.py verbs
- Grok.com becomes reachable as LLM backend
- Test: planner calls grok via browser, gets valid plan back

### Phase 4: Handover (endgame)
- model.json: transport=browser_ai
- Post goal → server calls grok.com for planning/acting/verifying
- Operator uses its own hands to talk to its own brain
- Self-sustaining. No external agent needed.

---

## Truth Order

1. Live `server.py` + `desktop.py` + `actions.py` (what runs)
2. Live `prompts/wiring.json` (active rules and topology)
3. Live `prompts/model.json` (active transport)
4. Raw log `logs/endgame_raw.jsonl` (execution evidence)
5. This README (intent and plan — may lead code)

---

## Methodology Critique (honest)

| What I (AI agent) did wrong | Lesson |
|---|---|
| Tried to fix deny rules one-by-one | Should have recognized systemic failure after 2nd false positive |
| Created polling scripts | Should have just read/written files directly as the model |
| Fought timing issues | The file_proxy mechanism is simple: wait for request, write response |
| Didn't question rule architecture | 15 deny rules with absolute priority = fragile by design |

| What works well | Keep |
|---|---|
| UIA hover observation | Real SCREEN with [ID] targets |
| Verb executor | Deterministic actions on real desktop |
| Two-pass DECIDE NOW | Separates reasoning from decision |
| Confirm-only rules | Fast-path for obvious successes |
| Raw JSONL logging | Full audit trail |

---

## Handover Prompt (for continuation after compact)

```
CONTEXT: endgame-ai project at /mnt/c/Users/ewojgab/Downloads/endgame-ai/
BRANCH: runtime-optimization
STATE: server.py has patches (parse reasoning_content, target validation, launch verb, raw log)
PROBLEM: deny/reject rules in wiring.json block valid actions and create deadlocks
NEXT STEP: Phase 1 — remove all deny_*/reject_* rules, keep only confirm_* rules
THEN: Phase 2 — restart server, post grok.com goal, act as file_proxy brain, prove satisfied:true
THEN: Phase 3 — implement browser_ai transport in server.py llm() function
METHOD: I (AI agent) AM the LLM brain via file_proxy. I read request.json, I write response.json.
         No scripts. No workarounds. I respond as Planner/Act/Verifier/Reflector based on ROLE:.
PROVEN: Grok.com is reachable (Opera opened it, chat input visible, message typed, Grok responded)
BLOCKED BY: deny rules that prevented remembering Grok's response
FILES: server.py(3480), desktop.py(1620), actions.py(290), wiring.json(33 rules → trim to ~10)
```
