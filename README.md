# endgame-ai

A living Windows desktop organism — not a traditional agentic CCA. It operates a real Windows desktop like a human: mouse, keyboard, arbitrary code generation/execution, self-evolution through wiring changes.

## Architecture

- **Python** = mechanical body (actions, desktop observation, organism loop)
- **wiring.json** = mutable genome (topology, transport, prompts, config)
- **seed_nodes/** → **live_nodes/** at runtime (hot-swappable)
- **seed_brains/** → **live_brains/** at runtime (hot-swappable transports)
- **ROD** = Reason → Observe → Decide (pluggable reasoning feedback loop in `brain.think()`)
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

# Run with opencode (requires opencode CLI installed)
# Edit wiring.json: "transport": "opencode"
python organism.py --reset --max-ticks 10 --max-brain-calls 20 "open notepad"

# Workbench (optional) - modern responsive UI with SVG topology graph
python workbench.py
# http://127.0.0.1:8800/           -- UI
# http://127.0.0.1:8800/api/status -- JSON status
# http://127.0.0.1:8800/api/control POST {"mode":"run|pause|step"}
```

## Wiring (wiring.json) — Single Source of Truth

```json
{
  "schema": "endgame-ai.wiring.v1",
  "model": {
    "transport": "opencode",
    "transport_config": {
      "openai": {
        "base_url": "http://localhost:1234",
        "path": "/v1/chat/completions",
        "model": "nvidia-nemotron-3-nano-4b",
        "temperature": 0.2,
        "reasoning": {
          "enabled": true,
          "pattern": "two_pass",
          "injection_template": "ROD_REASONING_CONTENT:\n{reasoning}",
          "extractor": "think_tags"
        }
      },
      "opencode": {
        "executable": "%USERPROFILE%/AppData/Local/opencode/opencode-cli.exe",
        "model": "opencode-go/deepseek-v4-flash",
        "extra_args": [],
        "reasoning": { "enabled": false }
      },
      "xai": {
        "mode": "api",
        "api_key_env": "XAI_API_KEY",
        "model": "grok-build-0.1",
        "url": "https://api.x.ai/v1/responses",
        "temperature": 0.2,
        "reasoning": {
          "enabled": true,
          "pattern": "native",
          "extractor": "reasoning_field"
        }
      },
      "grok_cli": {
        "executable": "grok",
        "extra_args": [],
        "reasoning": {
          "enabled": true,
          "pattern": "native",
          "extractor": "reasoning_field"
        }
      },
      "file_proxy": {
        "request_path": "comms/request.json",
        "response_path": "comms/response.json",
        "poll_interval": 0.25,
        "reasoning": {
          "enabled": true,
          "pattern": "two_pass",
          "injection_template": "ROD_REASONING_CONTENT:\n{reasoning}",
          "extractor": "think_tags"
        }
      },
      "browser_ai": {
        "documented_stub": true,
        "reasoning": { "enabled": false }
      }
    },
    "global": {
      "timeout": 180,
      "max_brain_calls": null,
      "raw_log": true,
      "reasoning_enabled": true
    }
  },
  "paths": {
    "seed_nodes": "seed_nodes",
    "live_nodes": "live_nodes",
    "seed_brains": "seed_brains",
    "live_brains": "live_brains",
    "state": "state.json",
    "control": "comms/control.json",
    "runtime_log": "comms/runtime.ndjson"
  },
  "control_default": { "mode": "run", "step_token": 0, "updated_at": 0 },
  "topology": {
    "cycle_start": "planner",
    "nodes": ["planner","observe","decide","act","verify","reflect","self_modify","error"],
    "edges": {
      "planner": { "observe": "observe", "reflect": "reflect", "error": "error" },
      "observe": { "decide": "decide", "reflect": "reflect", "error": "error" },
      "decide": { "act": "act", "reflect": "reflect", "self_modify": "self_modify", "error": "error" },
      "act": { "verify": "verify", "reflect": "reflect", "error": "error" },
      "verify": { "planner": "planner", "reflect": "reflect", "error": "error" },
      "reflect": { "planner": "planner", "self_modify": "self_modify", "error": "error" },
      "self_modify": { "planner": "planner", "reflect": "reflect", "error": "error" },
      "error": { "planner": "planner", "reflect": "reflect", "halt": "halt" }
    }
  },
  "prompts": {
    "planner": "You are the planner node of endgame-ai. Return one JSON object with record_type='plan', data.next_signal (must be 'observe' or 'reflect'), and data.intent (your plan).",
    "decide": "You are the decide node of endgame-ai. Return one JSON object with record_type='decision', data.next_signal (must be 'act', 'reflect', or 'self_modify'), and data.action (object with verb, e.g. {\"verb\": \"open_notepad\"} or {\"verb\": \"noop\"}). Available verbs: open_notepad, noop.",
    "verify": "You are the verify node of endgame-ai. Return one JSON object with record_type='verification', data.next_signal (must be 'planner' or 'reflect'), and data.success (boolean).",
    "reflect": "You are the reflect node of endgame-ai. Return one JSON object with record_type='reflection', data.next_signal (must be 'planner' or 'self_modify'), and data.lesson (what you learned)."
  },
  "action_verbs": {
    "open_notepad": "Open Windows Notepad using the mechanical body.",
    "noop": "Record no operation."
  }
}
```

### Reasoning Configuration (Per-Transport)

Each transport can have its own reasoning strategy:

| Pattern | Description | Use Case |
|---------|-------------|----------|
| `two_pass` | Call 1: reasoning, Call 2: inject + extract JSON | Small models (Nemotron 4B) |
| `single_pass` | One call, extract JSON directly | Smart models, file_proxy |
| `native` | Use model's native reasoning field | xAI grok, OpenAI o1 |
| `custom` | Configurable template + extractor | Experimental |

**Global toggle**: `model.global.reasoning_enabled` (default: true) — when false, all nodes use single_pass.

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

**Legacy transports archived**: `grok_build.py`, `grok_build_api.py`, `xai_responses.py` → `archive/`

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
| `error` | Error recovery | `planner` \| `reflect` \| `halt` | ❌ |

**Orphaned (in seed_nodes, not wired):** `satisfied.py` (terminal rest), `scheduler.py` (plan stepping) — reserved for future plan-completion topology.

## STEP Mode

Centralized in `organism.py` before node execution. Control via `comms/control.json`:

```json
{"mode": "run", "step_token": 0, "updated_at": 1234567890}
```

- `run`: execute normally
- `pause`: pause before next node
- `step`: execute exactly one node per new `step_token`, then pause

## Workbench (Optional)

Modern responsive UI built with ES modules, CSS Grid/Flexbox, SVG topology graph.

**Files:**
- `workbench.py` — Minimal HTTP server with API endpoints
- `workbench.html` — Semantic HTML5, mobile-first responsive
- `workbench.css` — CSS custom properties, dark theme
- `workbench.js` — Main app (ES module)
- `workbench-api.js` — API client with abort/timeout
- `workbench-state.js` — Reactive state (pub/sub)
- `workbench-graph.js` — SVG topology visualization
- `workbench-editor.js` — Hybrid form/JSON wiring editor

**API Endpoints:**
- `GET /api/status` — State, control, runtime tail, wiring summary
- `GET /api/control` — Current control mode
- `POST /api/control` — `{mode: "run|pause|step"}`
- `GET /api/wiring` — Full wiring.json
- `POST /api/wiring` — Hot-reload wiring (atomic write)
- `GET /api/state/raw` — Raw state.json
- `GET /api/logs/tail?lines=100` — Runtime NDJSON tail
- `GET /api/transport/probe` — Probe current transport health
- `POST /api/brain/test` — ROD falsification test (2 calls)

## Current State (2026-07-01, commit 376dc0b)

- **Branch:** `unified-archBRAINZ` (clean)
- **Core:** `brain.py` (Transport protocol, BaseTransport, ReasoningStrategy, config resolution), `nodes.py` (BaseNode ABC), `organism.py` (loop, STEP, error routing), `wiring.json` (v1 schema with reasoning + error topology)
- **Transports:** `seed_brains/{openai,file_proxy,opencode,xai}.py` + stub `browser_ai.py`; legacy archived to `archive/`
- **Nodes:** `seed_nodes/{planner,decide,verify,reflect}.py` use BaseNode (~10 lines); `observe,act,self_modify,error` mechanical
- **Topology:** 8-node cycle with `error` node + recovery edges; `halt` signal for clean exit
- **Workbench:** Modern modular UI with SVG graph, hybrid wiring editor, transport probe, ROD test

## Phase 5 — Next Steps

1. Test `xai` transport: set `XAI_API_KEY`, `model.transport=xai`, `mode=api` → run organism
2. Test `grok_cli` transport: install grok CLI, change wiring, run organism
3. Implement `self_modify` node to actually rewrite wiring.json
4. Add multi-ROD parallelism (RodRunner + scheduler)
5. Add usage/cost tracking per transport

---

## APPENDIX A: Pluggable ROD Reasoning (Implemented)

**Before:** Two-pass ROD hardcoded in `brain.think()`.

**Now:** `ReasoningStrategy` protocol with 4 implementations:

```python
# brain.py
class ReasoningStrategy(Protocol):
    def execute(self, system_prompt, payload, wiring, transport, cfg) -> dict: ...

TwoPassStrategy      # reasoning → inject → JSON
SinglePassStrategy   # direct JSON
NativeReasoningStrategy  # transport.reasoning field
CustomStrategy       # configurable template + extractor
```

**Config (per transport in wiring.json):**
```json
"reasoning": {
  "enabled": true,
  "pattern": "two_pass|single_pass|native|custom",
  "injection_template": "ROD_REASONING_CONTENT:\n{reasoning}",
  "extractor": "think_tags|reasoning_field"
}
```

**Global toggle:** `model.global.reasoning_enabled`

---

## APPENDIX B: Error-Handling Topology (Implemented)

**New topology edges** from every node → `error`, and `error` → `planner|reflect|halt`.

**`seed_nodes/error.py`** — Mechanical node (no brain call):
- Receives `last_error`, `failed_node`, `tick`, `signal` in state
- Logs error, returns recovery signal (default: `planner`)

**`organism.py`** — Exception routing:
- Catches exceptions → sets `last_error` → emits `error` signal
- Topology routes to `error` node automatically
- `halt` signal → clean exit (`_phase: "halted"`), no zombie processes

---

## APPENDIX C: Multi-ROD Parallelism (Architecture Note)

The "bus and scheduler" refers to running multiple independent ROD cycles in parallel. Current codebase is single-ROD. To scale:

1. `organism.py` → `RodRunner` class (single ROD instance)
2. `scheduler.py` (orphaned) → orchestrates multiple `RodRunner`s
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
> **Key files to understand:**
> - `brain.py` — Transport protocol, BaseTransport, ReasoningStrategy, `call()`/`think()`, config resolution (`_get_transport_config`)
> - `nodes.py` — BaseNode ABC, `call_node()`, node loading
> - `organism.py` — Main loop, STEP mode, topology traversal, error routing
> - `wiring.json` — Genome: transport, topology, prompts, reasoning config, error topology
> - `seed_brains/xai.py` — Unified xAI transport (API + CLI modes)
> - `seed_brains/opencode.py` — Fixed stateless OpenCode transport (clears auth env vars)
> - `seed_nodes/*.py` — Thin wrappers using BaseNode (planner/decide/verify/reflect) or mechanical (observe/act/self_modify/error)
> - `workbench.py` + `workbench.html` + `workbench*.js` — Optional modern UI
>
> **Fail-hard:** No fallbacks. If transport fails, organism stops with clear error.
>
> **ROD pattern:** Pluggable via `ReasoningStrategy` — default `TwoPassStrategy` for Nemotron 4B, configurable per transport in wiring.json.
>
> **Error handling:** `error` node in topology with `halt` signal for clean exit (no zombie processes).
>
> **Scientist Mode:** Always active (see Appendix E). Claims must be labeled tested/untested.
>
> **Workbench:** Optional. Run `python workbench.py` → http://127.0.0.1:8800/ for SVG topology graph, hybrid wiring editor, transport probe, ROD test.
>
> Start by running validation commands in Quick Start, then pick a Phase 5 task.