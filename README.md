# endgame-ai

**Real local Windows desktop organism.** Observes via UIA, acts via GUI/helpers/Python/process, verifies evidence, reflects on failures, evolves via git. Bus-routed organ graph, not a linear chain.

## What Was Proven (2026-07-07)

| Capability | Status | Evidence |
|------------|--------|----------|
| **UIA whole-screen observation** | ✅ Working | `node_observe` produces structured `desktop_tree_text` (1.3KB, 33 lines) |
| **Focused filtering** | ✅ Working | Consolidated `filter_raw()`: 500 elements max, 30/window, 200 chars/text |
| **GUI control (click, type, open_url)** | ✅ Working | `node_execute` emits `open_url`, `click_node`, helpers execute |
| **Python/process execution** | ✅ Working | Subprocess, filesystem, imports available in execute runtime |
| **Bus-routed organ graph** | ✅ Working | 7 organs, 10 topology edges, deterministic signal flow |
| **Verification with evidence** | ✅ Working | `node_verify` denies/confirms based on `done_when` + observation |
| **Structured failure routing** | ✅ Working | `last_failure.kind` + `contract_repair_allowed` gates escalation |
| **Self-modify surgery gate** | ✅ Enforced | Only `reflect.escalate` → `node_self_modify`; folklore wiring blocked |
| **xAI transport (grok-4.3)** | ✅ Working | 15-tick run completed, 0 token errors, reasoning=none |
| **Git known-good ref** | ✅ Working | `refs/endgame/known_good` updated and pushed |

## What Failed Before (Root Causes Fixed)

| Failure | Root Cause | Fix |
|---------|------------|-----|
| **Token overflow (3M+ chars)** | Full desktop tree (800+ elements) sent to LLM | `filter_raw()` consolidated: 3 params (`max_elements=500`, `max_per_window=30`, `max_text=200`) |
| **Verify with stale observation** | `open_url` async → verify ran before page load | Pipeline gap: no Verify→Observe edge; Execute must `FRAME` after navigation |
| **Execute emitted code with FRAME** | LLM misunderstood `FRAME` = "emit framing code" | Prompt: explicit PATTERNS showing `FRAME` = empty code |
| **Planner amputated obligations** | LLM dropped completed steps on replan | `node_planner.py` validation: `len(intent) >= remaining_root_obligations` |
| **Escalation on ordinary errors** | Reflect matched error strings (NameError, etc.) | Reflect now routes from `last_failure.kind` + `contract_repair_allowed` |

## Architecture (V6 Doctrine)

```
Goal → Planner (semantic steps) → Scheduler (next step)
                                    ↓
Observe (UIA scan) → Execute (Python) → Verify (evidence)
                                    ↓
                              Reflect (routing)
                                    ↓
                        retry / replan / frame / escalate
                                    ↓
                            Self-Modify (surgery only)
```

**Organs (7):**
- `node_planner` — Architect: semantic steps with `done_when`
- `node_scheduler` — Selector: exposes next step
- `node_observe` — Eye: mechanical UIA scan, no LLM
- `node_frame_action` — Framer: narrows route for execute
- `node_execute` — Actor: emits Python, **no self-modify**
- `node_verify` — Witness: judges `done_when` from evidence
- `node_reflect` — Judge: routes from structured `last_failure`
- `node_self_modify` — Surgeon: rare surgery only
- `node_satisfied` — Halt gate: completion or honest give-up
- `node_error` — Mechanical failure router

## Key Invariants (Enforced in Code)

1. **Execute is narrow actuator** — Cannot emit `self_modify`, cannot write firmware files, `FRAME`/`CANNOT` = empty code
2. **Reflect is strict router** — Escalates only for `contract_repair_allowed=true` (topology, record, capability, observation, wiring, self_modify contracts)
3. **Planner preserves root intent** — Replan must emit ALL remaining obligations
4. **Observation is filtered** — Single `filter_raw()` with 3 coherent limits, per-window safe fuse (30 interactive)
5. **Known-good is Git ref** — `refs/endgame/known_good` updated on successful self-modify
6. **Prompts are runtime law** — STONE LAW in wiring.json, not documentation

## Wiring.json (Single Source of Truth)

```json
{
  "model": {
    "transport": "transport_xai",
    "transport_config": {
      "transport_xai": {
        "model": "grok-4.3",
        "temperature": 0.4,
        "reasoning": {"enabled": false, "effort": "none"}
      }
    },
    "organs": {
      "plan": {"reasoning_effort": "none", "max_output_tokens": 6144},
      "execution": {"reasoning_effort": "none", "max_output_tokens": 4096},
      "verification": {"reasoning_effort": "none", "max_output_tokens": 1024},
      "reflection": {"reasoning_effort": "none", "max_output_tokens": 2048}
    }
  },
  "observe_config": {
    "hover_cache": {
      "scan": {"step_px": 64, "max_subtree_nodes_per_point": 2000, "max_total_nodes": 10000},
      "filter": {
        "max_elements": 500,
        "max_per_window": 30,
        "max_text": 200,
        "require_interactive": true
      }
    }
  }
}
```

## Running

```powershell
# Reset state, enable evolution, 3-minute run
python core_organism.py --reset --duration-seconds 180 "Your goal here"

# Check status
cat runtime_state.json | jq ._phase
cat runtime_events.jsonl | python check_events.py
```

## Scientific Log (What We Know)

| Date | Run | Ticks | Outcome | Learning |
|------|-----|-------|---------|----------|
| 2026-07-07 | Job search Krakow | 14 | Duration expiry | Execute FRAME violation, Planner amputation, Verify timing gap |
| 2026-07-07 | Analysis run | 15 | **Halted (success)** | Filtering works (1.3KB obs), xAI transport stable, pipeline complete |

## What Remains Unproven

- [ ] Multi-step goal with GUI + Python composition
- [ ] Self-modify triggered by real contract failure (not task-route)
- [ ] Focused observation (`observe_area`) used by Execute
- [ ] Long-running unattended workflow (job application end-to-end)
- [ ] Recovery from `refs/endgame/known_good` hot-swap

## Elimination Candidates (Next Reduction)

- `core_observation.py`: ~400 lines → split RAW/FILTER/MAP or consolidate
- `core_brain.py`: transport abstraction + reasoning patterns + stable prefix → separate modules
- `core_nodes.py`: wiring patches + git ops + capability manifest → separate
- Duplicate `max_*` configs → single `filter` object (done)
- `node_frame_action` → inline into execute or eliminate if unused

---

**The organism is real. The doctrine is enforced. The pipeline completes.**