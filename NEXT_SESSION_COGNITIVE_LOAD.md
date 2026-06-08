# NEXT SESSION: JSON Schema Cognitive Load Reduction

## Problem Statement

The planner JSON schema requires 8 fields per response. Local models (gemma-4-e2b-it) produce valid JSON structure but fill fields incorrectly because they allocate attention across too many fields instead of getting the critical ones right.

## Evidence (collected this session)

Identical input (2029 char system prompt + ~600 char user context), same goal "Open Notepad via Win+R and type hello world":

### LM Studio (gemma-4-e2b-it) — 344 chars, 83 tokens
```json
{
  "mode": "direct",
  "because": "The goal is to open Notepad and type 'hello world', which can be done in a single sequence of actions.",
  "next_action": "Press Win+R and type notepad, then press Enter.",
  "expect": "Notepad application should open.",
  "step_advance": true,
  "notes": [],
  "sequence": ["Press Win+R and type notepad", "Press Enter"],
  "decompose": []
}
```

### ACP (Claude) — 663 chars
```json
{
  "mode": "direct",
  "because": "The goal is to open Notepad via Win+R and type hello world. Currently Task Manager is focused. I need to first open the Run dialog using Win+R hotkey.",
  "next_action": "Press hotkey Win+R to open the Run dialog.",
  "expect": "The Run dialog appears with a text field labeled 'Open' ready for input.",
  "step_advance": false,
  "notes": ["Goal: Open Notepad via Win+R and type hello world"],
  "sequence": ["Press Win+R to open the Run dialog", "Type 'notepad' in the Run dialog and press Enter to launch Notepad", "Wait for Notepad window to appear and become focused", "Click in the Notepad text area and type 'hello world'"],
  "decompose": []
}
```

## Observed Failures (LM Studio)

| Field | Error | Why |
|-------|-------|-----|
| `step_advance` | `true` on first call (nothing done) | Model doesn't reason about preconditions — just fills a boolean |
| `next_action` | 3 steps crammed into one string | Model avoids breaking work into atomic pieces |
| `sequence` | Too coarse (2 items vs 4) | Model doesn't invest tokens in planning granularity |
| `notes` | Empty | Model sees it as optional filler |
| `decompose` | Empty (correct) | Always empty for direct mode — wasted field |
| `because` | Generic, no screen citation | Model skips grounding to save effort |

## Key Insight

**`decompose` is ALWAYS empty unless mode=parallel.** Both models return `"decompose":[]` 99% of the time. Same for `notes` — LM Studio never fills it. These are wasted cognitive slots forcing the model to emit tokens (`[]`) that contribute nothing.

## Hypotheses for Next Session

### H1: Remove fields that are conditionally empty
- `decompose` should only exist when mode=parallel (never in the schema otherwise)
- `notes` could be optional or merged into a simpler field
- `sequence` could be a separate "first call only" schema

### H2: Split into two schemas — "plan" vs "advance"
- First call: mode + because + next_action + expect + sequence (creates the plan)
- Subsequent calls: mode + because + next_action + expect + step_advance (advances the plan)
- No decompose/notes/sequence clutter on every call

### H3: Reduce required fields to absolute minimum
- What does the system ACTUALLY consume from the planner?
  - `mode` — yes, drives control flow
  - `next_action` — yes, passed to actor
  - `sequence` — yes, but only once (first iteration)
  - `because` — only for logging
  - `expect` — only for logging
  - `step_advance` — yes, drives checklist
  - `notes` — rarely used
  - `decompose` — only for parallel mode

### H4: Provide in-context example in the prompt
- The "Required JSON" line shows the template but local models may benefit from a concrete filled example

## Methodology for Next Session

1. Put exit-after-first-call debug hook back in `dispatch.py` (code removed, pattern documented here)
2. Reduce planner schema fields and re-run LM Studio comparison
3. Measure: does the local model produce correct `step_advance=false` and atomic `next_action` with fewer fields?
4. If yes, apply to actor/verifier/reflector schemas similarly

## Debug Hook Pattern (for dispatch.py call_role)
```python
# Add after raw = call_llm(...):
if _call_count == TARGET:
    dump = f"=== ROLE: {spec.name} ===\n=== SYSTEM ({len(system)}) ===\n{system}\n\n=== CONTEXT ({len(context)}) ===\n{context}\n\n=== RESPONSE ({len(raw)}) ===\n{raw}\n"
    (BASE_DIR / "FIRST_LLM_CALL_DUMP.txt").write_text(dump, encoding="utf-8")
    sys.exit(42)
```

## Files to Modify
- `schemas/planner.json` — reduce required fields
- `prompts/planner.txt` — simplify field rules section
- `orchestrator.py` — handle missing optional fields gracefully
- Possibly: `schemas/actor.json`, `prompts/actor.txt` (same pattern)

## Current State
- Branch: `codex/wiring-hardening`
- All code operational, Pyright 0 errors
- Debug hook removed, dispatch.py is clean
- Dump files: `FIRST_LLM_CALL_LMSTUDIO.txt`, `FIRST_LLM_CALL_ACP.txt` (gitignored)
