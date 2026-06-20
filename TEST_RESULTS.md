# Test Results — honest matrix

**Branch:** `experiment/endgame` · **Updated:** 2026-06-20

---

## Infrastructure

| Test | Result | Evidence |
|------|--------|----------|
| `validate_stack.py` | ✓ | wiring structure, task-agnostic prompts, `/health` + `/node/entry` |
| `probe_circuits.py --dry all` | ✓ | All 5 circuits assemble prompts from wiring |
| Port slot=1 | ✓ serves :9078 | `runtime.http_port_base` 9077 + slot 1 |
| `run_single_rod_test.py` port | ✓ fixed | reads `runtime` from wiring |

---

## LLM circuits (isolated probe)

Fixture: `probe_fixtures/shakira_poisoned.json` (stale reasoning chain)

| Circuit | Expected | After WIRING-SEPARATION fixes |
|---------|----------|-------------------------------|
| planner | task | ✓ |
| unified | action | ✓ (was verdict before fixes) |
| verifier | verdict | ✓ |
| reflector | diagnosis | ✓ (was verdict before fixes) |
| self_modify | wiring_patch | ✓ |

Fixture: `probe_fixtures/shakira_clean.json`

| Circuit | Result |
|---------|--------|
| unified | ✓ `write Edit chrome` |

---

## End-to-end goals

| Goal | Mode | Duration | Result | Failure point |
|------|------|----------|--------|---------------|
| open notepad and write hello | single rod | ~5 min | **✓ PASS** | — |
| open chrome + shakira waka waka youtube | single rod 8min | 480s | **✗ FAIL** | step 0–2: Google not YouTube; reasoning poison spiral (pre-fix) |
| open chrome + shakira | colony 2min | 120s | **✗ FAIL** | step 2: YouTube homepage, no search UIA |
| open chrome + shakira | single rod 8min post-reasoning | 480s | **✗ FAIL** | act_failed loop on step 0 Run dialog |

---

## Proven capabilities

1. Planner decomposes goals into steps with `done_when`
2. Act executes real UIA verbs (hotkey, write, click, press)
3. Verify denies without SCREEN evidence; confirms when present
4. Reflect + retry loop runs
5. Reasoning_content stored and fed per wiring blocks
6. `expected_record_type` prevents verdict JSON in act parse
7. Guards block repeat actions
8. state.json persists full SCREEN field (no truncation)
9. wiring-editor connects and steps nodes

---

## Not proven

1. Arbitrary-length multi-app workflows
2. Web search → video play pipelines
3. Colony MoE with reviewer participation
4. self_modify improving outcomes in production runs
5. Recovery from UIA-blind pages without human Chrome flags
6. Sub-90s act+verify latency

---

## How to reproduce

```powershell
# Quick win
python server.py --run "open notepad and write hello"

# Isolated circuits
python probe_circuits.py probe_fixtures/shakira_clean.json unified

# Full goal (budget 8+ min)
python run_single_rod_test.py "open chrome and play shakira waka waka on youtube" 480

# Analyze
# state.json → step, plan, reasoning, screen, last_error
# single_rod_run.log → plan_ready, acted, step_confirmed, step_denied, replan
```

---

## Self-criticism

Tests labeled “PASS” use simple goals on native Windows UI. **Do not** extrapolate to web/video goals. The system is architecturally sound at wiring separation; **operationally immature** for human replacement on long arbitrary tasks.