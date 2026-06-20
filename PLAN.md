# Plan — experiment/endgame

**Date:** 2026-06-20 · **Tag:** `WIRING-SEPARATION`

---

## North star

Replace a human for **arbitrary-length desktop tasks** by wiring dumb specialists into a self-correcting loop — not by scaling one monolithic agent prompt.

---

## Done (verified or implemented)

### Wiring separation (`WIRING-SEPARATION`)

- [x] Policy in `wiring.json`: limits, errors, runtime, node_circuits, act, moe, reasoning
- [x] Request blocks assemble user messages; system prompts static in `prompts/*.txt`
- [x] `reasoning_content` capture + feed-forward through wiring
- [x] `expected_record_type` gate in `parse_circuit_response()`
- [x] No screen/history truncation in `server.py`
- [x] Task-agnostic prompt rewrite (all 5 circuits)
- [x] `validate_stack.py`, `probe_circuits.py`
- [x] `wiring-editor.html` port auto-discovery, pipe edge matching, reasoning in init state
- [x] Documentation rewrite with honest gaps

### Execution loop

- [x] Colony: `reactor.py` POST `/run` wakes implementor
- [x] Act rejects DONE; verify confirms steps
- [x] Single-rod: Notepad “hello” end-to-end
- [x] Graph engine, state persistence, SSE, hot-reload wiring

---

## Not done (honest gaps)

### P0 — blocks “replacement for human”

| Gap | Why it matters |
|-----|----------------|
| Complex web goals fail (YouTube, etc.) | UIA + planner + LLM latency |
| Colony port mismatch | `reactor.py` COLONY vs `runtime.http_port_*` |
| Reviewer rod idle | No verification delegation wired |
| 90–120s per act+verify | 2 min tests always lie |

### P1 — wiring purity

| Gap | Fix direction |
|-----|----------------|
| `COLONY` in `reactor.py` | Move to `colony.json` or `wiring.colony` |
| `model.json` outside wiring | Merge into wiring or document as sibling config |
| `NODES` registry in Python | Acceptable — handlers are muscles; document as boundary |
| `_resolve_value` in Python | New state sources need code — rare |

### P2 — intelligence quality

| Gap | Fix direction |
|-----|----------------|
| Reasoning poisoning | Stronger prompts + record_type gate (done); monitor chain_depth |
| Planner skips prerequisites | Planner prompt + verify strictness |
| self_modify underused | Escalate path rarely reached in tests |

---

## Next experiments (ordered)

1. **Fix colony ports** — single source: `wiring.runtime` or `colony.json`
2. **Shakira / web goal** — 8+ min run, analyze `state.json` reasoning chain + SCREEN
3. **Wire reviewer rod** — bus delegation for verify step
4. **Merge model.json** into wiring `llm` section (optional)
5. **Long-horizon task** — multi-app workflow (30+ min budget)

---

## Success criteria (ultimate goal)

| Criterion | Status |
|-----------|--------|
| Runs without browser | ✓ |
| Multi-step plan + verify loop | ✓ |
| Reasoning fed via wiring | ✓ |
| Arbitrary goal length | ✗ |
| Web/video tasks | ✗ |
| Colony MoE fully utilized | ✗ |
| Human-level recovery from stuck | Partial |

---

## Architecture decisions (current)

| Decision | Choice |
|----------|--------|
| Brain | `prompts/wiring.json` |
| Circuits | 5 LLM roles + static `.txt` |
| Feedback | `reasoning_content` not JSON `reason` strings |
| Verify | Fresh observe inside verify node |
| Bus | `bus.json` file |
| Colony | `reactor.py` spawns rods with per-rod wiring copy |
| Desktop | Windows UIA via `desktop.py` |