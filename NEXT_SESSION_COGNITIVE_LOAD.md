# JSON Schema Cognitive Load — Reduction Results

## Experiment: Reduce planner from 8 fields to 3, actor from 5 to 2

### Before (8 fields: mode, because, next_action, expect, step_advance, notes, sequence, decompose)

**LM Studio** — 83 tokens out:
```json
{"mode":"direct","because":"...vague...","next_action":"Press Win+R and type notepad, then press Enter.","expect":"...","step_advance":true,"notes":[],"sequence":["Press Win+R and type notepad","Press Enter"],"decompose":[]}
```
Problems: step_advance=true (wrong), next_action combines 3 steps, vague because, hallucinated "save as"

**ACP** — correct on all 8 fields, 4-step sequence, atomic next_action

### After (3 fields: mode, next_action, sequence)

**LM Studio** — 29 tokens out:
```json
{"mode":"direct","next_action":"win+r","sequence":["open notepad","type hello world","save as document.txt"]}
```

**ACP** — 254 chars:
```json
{"mode":"direct","next_action":"Press hotkey Win+R to open the Run dialog","sequence":["Press hotkey Win+R to open the Run dialog","Type 'notepad' in the Run dialog","Press Enter to launch Notepad","Type 'hello world' in the Notepad window"]}
```

### Key finding

| Metric | Before (LM Studio) | After (LM Studio) | Fixed? |
|--------|--------------------|--------------------|--------|
| next_action atomic | NO (3 steps crammed) | YES ("win+r") | ✅ |
| step_advance wrong | YES (true on iter 1) | N/A (field removed) | ✅ |
| decompose waste | Always [] | N/A (field removed) | ✅ |
| notes waste | Always [] | N/A (field removed) | ✅ |
| sequence hallucination | Partial | Still hallucinates "save as" | ⚠️ |
| System prompt size | 2029 chars | 772 chars (-62%) | ✅ |
| Response tokens | 83 | 29 (-65%) | ✅ |

### Remaining issues
1. LM Studio sequence has vague steps ("open notepad" vs "Type 'notepad' in the Run dialog")
2. LM Studio hallucinated "save as document.txt" (not in goal)
3. Actor schema also reduced (5→2 fields) — untested in full run yet

### Actor schema reduction
Before: observe, reason, actions, expect, conclusion (5 fields)
After: actions, conclusion (2 fields)

### Next: full end-to-end run with both backends on reduced schemas
