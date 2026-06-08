# JSON Schema Cognitive Load — Test Results

## Test Protocol
- Time limit: 3 minutes (kill via PowerShell)
- Both backends run sequentially on same machine
- Clean runtime between each test
- All schemas reduced: planner 8→3, actor 5→2, verifier 5→2, reflector 4→2

## Schema Summary (bare metal)

| Role | Fields | Schema |
|------|--------|--------|
| Planner | 3 | mode, next_action, sequence |
| Actor | 2 | actions, conclusion |
| Verifier | 2 | verdict, evidence |
| Reflector | 2 | diagnosis, lesson |

## Test 1: "Open Notepad via Win+R and type hello world"

| Metric | ACP (Claude) | LM Studio (gemma-4-e2b-it) |
|--------|-------------|---------------------------|
| Outcome | SUCCESS ✅ | HALTED (stagnation) ❌ |
| Wall time | 60.5s | 164.8s |
| Iterations | 10 | 10 |
| LLM calls | 18 | 17 |
| Actions executed | 10 (all correct) | 4 (wrong targets) |
| Efficiency | 0.56 | 0.24 |
| Checklist advances | 3 | 0 |
| Verifier called | 2 (1 denied) | 0 |
| Reflector called | 0 | 2 |
| Root cause | — | Actor writes to wrong elements, never opens Win+R first |

## Test 2: "Open Notepad and write everything you know about the current environment"

| Metric | ACP (Claude) | LM Studio (gemma-4-e2b-it) |
|--------|-------------|---------------------------|
| Outcome | HALTED ❌ | Backend unavailable ❌ |
| Wall time | 103.9s | 139.9s |
| Iterations | 16 | 8 |
| LLM calls | 28 | 15 |
| Actions executed | 13 | 4 |
| Efficiency | 0.46 | 0.27 |
| Root cause | Actor clicks text area 9x but never types (no observe field = can't reason about content) | Typed "hello world" 4x (hallucinated from previous context window) |

## Key Findings

### 1. Planner schema reduction WORKS
Both models produce correct atomic `next_action` with 3 fields. The planner bottleneck is resolved.

### 2. Actor schema too aggressive
Removing `observe` from actor broke content generation for BOTH models:
- Without seeing screen state in its own reasoning, the actor can't decide WHAT to write
- Claude got stuck clicking the text area repeatedly
- The local model hallucinated old content

### 3. `observe` is load-bearing for the actor
The actor needs to describe what it sees to generate appropriate text content. This is especially critical for creative/open-ended goals.

### 4. Verifier/reflector reduction is fine
2 fields each is sufficient. The verifier correctly denied once for ACP on test 1, then confirmed.

## Recommended Schema (next iteration)

| Role | Fields | Rationale |
|------|--------|-----------|
| Planner | 3 | mode, next_action, sequence — KEEP |
| Actor | 3 | observe, actions, conclusion — add back observe |
| Verifier | 2 | verdict, evidence — KEEP |
| Reflector | 2 | diagnosis, lesson — KEEP |

Total fields: 10 (was 22 before, reduced by 55%)

## Remaining Issues
1. LM Studio actor still targets wrong elements (writes to random editboxes)
2. LM Studio backend crashes under sustained load (memory pressure)
3. Checklist never advances for LM Studio (planner doesn't understand step progression without step_advance)
4. Both models failed the creative goal — system needs a way to generate content, not just click
