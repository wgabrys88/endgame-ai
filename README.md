# endgame-ai

A living Windows desktop organism — not a traditional agentic CCA. It operates a real Windows desktop like a human: mouse, keyboard, arbitrary code generation/execution, self-evolution through wiring changes.

## Architecture

- **Python** = mechanical body (actions, desktop observation, organism loop)
- **wiring.json** = mutable genome (topology, transport, prompts, config)
- **seed_nodes/** → **live_nodes/** at runtime (hot-swappable)
- **seed_brains/** → **live_brains/** at runtime (hot-swappable transports)
- **ROD** = Reason → Observe → Decide (two-pass reasoning feedback loop hardcoded in `brain.think()`)
- **No fallbacks** = fail-hard, always. If a transport fails, the organism stops.

## Quick Start

```powershell
# Validate
python -m py_compile brain.py nodes.py organism.py workbench.py actions.py desktop.py
python -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for d in ['seed_nodes','seed_brains'] for p in pathlib.Path(d).glob('*.py')]"

# Run with LM Studio (default: openai transport)
# Requires LM Studio local server at http://localhost:1234/v1/chat/completions
python organism.py --reset --max-ticks 10 --max-brain-calls 20 "open notepad"

# Run with file_proxy (human-in-the-loop, no model needed)
# Edit wiring.json: "transport": "file_proxy"
python organism.py --reset --max-ticks 10 --max-brain-calls 20 "open notepad"
# Write responses to comms/response.json as they appear in comms/request.json

# Workbench (optional)
python workbench.py
# http://127.0.0.1:8800/           -- UI
# http://127.0.0.1:8800/api/status
# http://127.0.0.1:8800/api/control  POST {"mode":"run|pause|step"}
```

## Wiring (wiring.json) — Single Source of Truth

```json
{
  "schema": "endgame-ai.wiring.v1",
  "model": {
    "transport": "openai",
    "transport_config": {
      "openai": {
        "base_url": "http://localhost:1234",
        "path": "/v1/chat/completions",
        "model": "nvidia-nemotron-3-nano-4b",
        "temperature": 0.2
      },
      "opencode": {
        "executable": "%USERPROFILE%/AppData/Local/opencode/opencode-cli.exe",
        "model": "opencode-go/deepseek-v4-flash",
        "extra_args": []
      },
      "xai": {
        "mode": "api",
        "api_key_env": "XAI_API_KEY",
        "model": "grok-build-0.1",
        "url": "https://api.x.ai/v1/responses",
        "temperature": 0.2
      },
      "grok_cli": {
        "executable": "grok",
        "extra_args": []
      },
      "file_proxy": {
        "request_path": "comms/request.json",
        "response_path": "comms/response.json",
        "poll_interval": 0.25
      },
      "browser_ai": { "documented_stub": true }
    },
    "global": {
      "timeout": 180,
      "max_brain_calls": null,
      "raw_log": true
    }
  },
  "paths": { "seed_nodes": "seed_nodes", "live_nodes": "live_nodes", "seed_brains": "seed_brains", "live_brains": "live_brains", "state": "state.json", "control": "comms/control.json", "runtime_log": "comms/runtime.ndjson" },
  "control_default": { "mode": "run", "step_token": 0, "updated_at": 0 },
  "topology": { "cycle_start": "planner", "nodes": ["planner","observe","decide","act","verify","reflect","self_modify"], "edges": { ... } },
  "prompts": { "planner": "...", "decide": "...", "verify": "...", "reflect": "..." },
  "action_verbs": { "open_notepad": "...", "noop": "..." }
}
```

## Brain Transports (stateless, fail-hard)

| Transport | Status | Description |
|-----------|--------|-------------|
| `openai` | ✅ Verified | OpenAI-compatible `/v1/chat/completions` (LM Studio default) |
| `file_proxy` | ✅ Verified | File-based human-in-the-loop handoff |
| `opencode` | ✅ Verified | `opencode run -m <model> --format json` (clears auth env vars) |
| `xai` (mode=api) | ✅ Implemented | xAI Responses API (`grok-build-0.1`, `grok-4`) |
| `xai` (mode=cli) | ✅ Implemented | `grok -p "prompt" --output-format json --no-auto-update` |
| `grok_cli` | ✅ Implemented | Dedicated CLI transport (same as xai mode=cli) |
| `browser_ai` | ❌ Stub | Documented fail-hard placeholder |

**Each transport exports:** `call(messages, cfg) -> {"content": str, "reasoning": str}`

## Nodes (ROD Pipeline)

| Node | Role | Signal Output | Uses Brain |
|------|------|---------------|------------|
| `planner` | Goal → plan + next_signal | `observe` \| `reflect` | ✅ |
| `observe` | Desktop snapshot | `decide` \| `reflect` | ❌ |
| `decide` | Plan + observation → action | `act` \| `reflect` \| `self_modify` | ✅ |
| `act` | Execute mechanical action | `verify` \| `reflect` | ❌ |
| `verify` | Action result → success/fail | `planner` \| `reflect` | ✅ |
| `reflect` | Lesson extraction | `planner` \| `self_modify` | ✅ |
| `self_modify` | Wiring rewrite (future) | `planner` \| `reflect` | ❌ |

**Orphaned (in seed_nodes, not wired):** `satisfied.py` (terminal rest), `scheduler.py` (plan stepping) — reserved for future plan-completion topology.

## STEP Mode

Centralized in `organism.py` before node execution. Control via `comms/control.json`:

```json
{"mode": "run", "step_token": 0, "updated_at": 1234567890}
```

- `run`: execute normally
- `pause`: pause before next node
- `step`: execute exactly one node per new `step_token`, then pause

## Current State (2026-06-30, commit bb6e564)

- **Branch:** `unified-archBRAINZ` (clean, pushed)
- **Core:** `brain.py` (Transport protocol, BaseTransport, config resolution), `nodes.py` (BaseNode ABC), `organism.py` (loop, STEP), `wiring.json` (normalized schema)
- **Transports:** `seed_brains/{openai,file_proxy,opencode,xai}.py` + stub `browser_ai.py`; `grok_build_api.py` marked reference-only
- **Nodes:** `seed_nodes/{planner,decide,verify,reflect}.py` use BaseNode (~10 lines each); `observe,act,self_modify` non-brain
- **Topology:** 7-node cycle with `reflect`/`self_modify` edges; no error node yet

## Phase 4 — Validation (Next Session)

1. Test `xai` transport: set `XAI_API_KEY`, `model.transport=xai`, `mode=api` → run organism
2. Test `grok_cli` transport: install grok CLI, `mode=cli` or `transport=grok_cli` → run organism
3. Add error-handling node + recovery edges to topology
4. Make ROD two-pass pluggable per transport (config in wiring)
5. Clean up `test_*.py` files

---

## APPENDIX A: Pluggable ROD Reasoning Feedback (Proposal)

**Current:** Two-pass ROD hardcoded in `brain.think()`:
1. Call 1: system + user → extract `reasoning`
2. Call 2: same + `ROD_REASONING_CONTENT:\n{reasoning}` → extract JSON record

**Problem:** Not all transports/models benefit from same pattern. Some need single-pass, others multi-pass, some have native reasoning tokens.

**Proposal:** Make reasoning pattern configurable per transport (in `transport_config`):

```json
"xai": {
  "reasoning_pattern": "two_pass",      // "single_pass" | "two_pass" | "native" | "custom"
  "reasoning_injection_template": "ROD_REASONING_CONTENT:\n{reasoning}",
  "reasoning_extractor": "think_tags"   // "think_tags" | "reasoning_field" | "none"
}
```

**Implementation:** `brain.think()` reads `transport_config[transport].reasoning_pattern` and dispatches to strategy functions. Default remains `two_pass` for backward compatibility.

**Falsifying experiment:** Run organism with `reasoning_pattern: "single_pass"` on Nemotron 4B — if goal-reinterpretation behavior degrades, two-pass is necessary for small models.

---

## APPENDIX B: Error-Handling Topology (Proposal)

**Current:** Exceptions caught in `organism.run()` → `_phase: "error"` → stop. No graph recovery.

**Proposal:** Add `error` node to topology with recovery edges:

```json
"topology": {
  "nodes": [..., "error"],
  "edges": {
    "planner": { "observe": "observe", "reflect": "reflect", "error": "error" },
    "decide":  { "act": "act", "reflect": "reflect", "self_modify": "self_modify", "error": "error" },
    "act":     { "verify": "verify", "reflect": "reflect", "error": "error" },
    "verify":  { "planner": "planner", "reflect": "reflect", "error": "error" },
    "reflect": { "planner": "planner", "self_modify": "self_modify", "error": "error" },
    "self_modify": { "planner": "planner", "reflect": "reflect", "error": "error" },
    "error":   { "planner": "planner", "reflect": "reflect", "halt": "halt" }
  }
}
```

`error` node: receives `last_error`, `failed_node`, `tick` in state; can log, attempt retry, or emit `halt` signal.

---

## APPENDIX C: Multi-ROD Parallelism (Architecture Note)

The "bus and scheduler" in vision refers to running multiple independent ROD cycles in parallel (each with its own `wiring.json` or shared topology with different goals). Current codebase is single-ROD. To scale:

1. `organism.py` → `RodRunner` class (single ROD instance)
2. `scheduler.py` (currently orphaned) → orchestrates multiple `RodRunner`s
3. Shared `comms/` bus for inter-ROD messaging
4. Each ROD gets isolated `live_nodes_N/`, `live_brains_N/`, `state_N.json`

This is how "endgame-ai produces Agents as output" — each ROD = one Agent.

---

## APPENDIX D: Self-Modification Mechanics

`self_modify` node currently returns `{"status": "no_change"}`. To implement actual wiring rewrites:

1. `self_modify` reads `wiring.json` + `state.json` + `runtime.ndjson`
2. Proposes patch (add/remove nodes, change edges, update prompts, switch transport)
3. Validates patch against schema (`endgame-ai.wiring.v1`)
4. Atomically writes new `wiring.json` (using `brain.atomic_write_json`)
5. Organism reloads wiring on next cycle (or signals `reconfigure`)

**Safety:** Patch validation must ensure topology remains connected, `cycle_start` in `nodes`, all `edges` reference valid nodes.

---

## APPENDIX E: Scientist Mode (Always Active)

1. Before any claim: (a) tested-in-this-session or (b) untested-prior. Untested → propose minimal falsifying experiment.
2. No hedging, no industry norms, no simulated measurements.
3. Tool insufficient → "experiment pending" and stop.
4. Counter-intuitive = hypothesis to test, not error to correct.
5. On evidence: update state plainly. "I was wrong; measurement shows X" is valid.
6. Audit prior turns for violations (hedging, conventions, invented data, refusal to update).

The user supplies hypotheses and intent. The assistant supplies execution, measurement, reporting. The experiment decides.

---

## APPENDIX F: Fail-Hard Rule

No fallbacks. If transport fails, organism stops with clear error. This is self-evolution — the system learns from hard failure, not graceful degradation.

---

## APPENDIX G: Bootstrap Prompt (For Fresh Sessions)

> You are starting a fresh session on endgame-ai. Read this entire README as your sole context.
>
> **Branch:** `unified-archBRAINZ` (clean). **Core files:** `brain.py`, `nodes.py`, `organism.py`, `wiring.json`.
>
> **What works:** `openai` (LM Studio), `file_proxy`, `opencode` transports verified end-to-end. `xai` (API+CLI), `grok_cli` implemented but untested.
>
> **Immediate next steps (Phase 4):**
> 1. Test `xai` transport: set `XAI_API_KEY`, change wiring to `"transport": "xai"`, run organism
> 2. Test `grok_cli`: install grok CLI, change wiring, run organism
> 3. Add error node + recovery edges to topology
> 4. Make ROD two-pass pluggable per transport (config in `transport_config`)
> 5. Remove `test_*.py` files
>
> **Key files to understand:**
> - `brain.py` — Transport protocol, BaseTransport, `call()`/`think()`, config resolution (`_get_transport_config`)
> - `nodes.py` — BaseNode ABC, `call_node()`, node loading
> - `organism.py` — Main loop, STEP mode, topology traversal
> - `wiring.json` — Genome: transport, topology, prompts, config
> - `seed_brains/xai.py` — Unified xAI transport (API + CLI modes)
> - `seed_brains/opencode.py` — Fixed stateless OpenCode transport (clears auth env vars)
> - `seed_nodes/*.py` — Thin wrappers using BaseNode
>
> **Fail-hard:** No fallbacks. If transport fails, organism stops with clear error.
>
> **ROD pattern:** Two-pass hardcoded in `brain.think()` — first call gets reasoning, second injects `ROD_REASONING_CONTENT` and extracts JSON record. Core innovation enabling 4B models to self-evolve.
>
> **Scientist Mode:** Always active (see Appendix E). Claims must be labeled tested/untested.
>
> Start by running validation commands in Quick Start, then pick a Phase 4 task.