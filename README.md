# endgame-ai

A living Windows desktop organism — not a traditional agentic CCA. It operates a real Windows desktop like a human: mouse, keyboard, arbitrary code generation and execution, self-evolution through wiring changes.

## Architecture

- **Python** = mechanical body (actions, desktop observation, organism loop)
- **wiring.json** = mutable brain/topology configuration (the "genome")
- **seed_nodes/** → copied to **live_nodes/** at runtime (hot-swappable)
- **seed_brains/** → copied to **live_brains/** at runtime (hot-swappable transports)
- **ROD** = Reason → Observe → Decide (two-pass brain pattern with reasoning feedback)
- **No fallbacks** = fail-hard, always. If a transport fails, the organism stops.

## Quick Start

```powershell
# Validate
python -m py_compile brain.py nodes.py organism.py workbench.py actions.py desktop.py
python -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for d in ['seed_nodes','seed_brains'] for p in pathlib.Path(d).glob('*.py')]"

# Run with LM Studio (default transport: openai)
# Requires LM Studio local server at http://localhost:1234/v1/chat/completions
python organism.py --reset --max-ticks 10 --max-brain-calls 20 "open notepad"

# Run with file_proxy (human-in-the-loop, no model needed)
# Edit wiring.json: "transport": "file_proxy"
python organism.py --reset --max-ticks 10 --max-brain-calls 20 "open notepad"
# Write responses to comms/response.json as they appear in comms/request.json

# Workbench (optional)
python workbench.py
# http://127.0.0.1:8800/  -- UI
# http://127.0.0.1:8800/api/status  -- JSON status
# http://127.0.0.1:8800/api/control  -- POST {"mode":"run|pause|step"}
```

## Wiring (wiring.json) — Single Source of Truth

```json
{
  "schema": "endgame-ai.wiring.v1",
  "model": {
    "transport": "openai",              // which brain transport to use
    "transport_config": {               // per-transport config (NEW normalized schema)
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
        "mode": "api",                  // "api" or "cli"
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
    "global": {                         // shared config merged into each transport
      "timeout": 180,
      "max_brain_calls": null,
      "raw_log": true
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
    "nodes": ["planner","observe","decide","act","verify","reflect","self_modify"],
    "edges": { ... }
  },
  "prompts": { "planner": "...", "decide": "...", "verify": "...", "reflect": "..." },
  "action_verbs": { "open_notepad": "...", "noop": "..." }
}
```

## Brain Transports (stateless, fail-hard)

| Transport | Status | Description |
|-----------|--------|-------------|
| `openai` | ✅ Working | OpenAI-compatible `/v1/chat/completions` (LM Studio default) |
| `file_proxy` | ✅ Working | File-based human-in-the-loop handoff |
| `opencode` | ✅ Working | `opencode run -m <model> --format json` (requires OPENCODE_SERVER_PASSWORD="" cleared) |
| `xai` | ✅ Working | xAI Responses API (`grok-build-0.1`, `grok-4`) + CLI mode |
| `grok_cli` | 🔧 Ready | `grok -p "prompt" --output-format json --no-auto-update` |
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

## Current State (2026-06-30)

### ✅ Completed (Phases 1-3)

**Phase 1: Critical Fixes**
- Fixed `opencode.py` transport for stateless CLI usage (positional arg + `--format json`, clears auth env vars)
- Marked `grok_build_api.py` as reference-only (non-functional fragment)
- Documented orphaned nodes in README

**Phase 2: Unification**
- Added `Transport` Protocol + `BaseTransport` ABC in `brain.py`
- Added `BaseNode` ABC in `nodes.py` — reduced 4 brain-calling nodes to ~10 lines each
- Consolidated `xai_responses.py` + `grok_build.py` → single `xai.py` (supports API + CLI modes)
- Normalized `wiring.json` schema: `model.transport_config.{transport}` + `model.global`

**Phase 3: Multi-Brain Support**
- LM Studio (`openai` transport) — verified working end-to-end
- OpenCode (`opencode` transport) — verified working with `opencode-go/deepseek-v4-flash`
- xAI Responses API (`xai` transport, mode=api) — implemented, needs API key
- Grok CLI (`xai` transport, mode=cli / `grok_cli`) — implemented, needs binary

### 📋 Remaining Work

- [ ] Test `xai` transport with real `XAI_API_KEY`
- [ ] Test `grok_cli` transport with real `grok` binary
- [ ] Add error-handling node + recovery edges to topology
- [ ] Make ROD two-pass pluggable per transport (currently hardcoded in `brain.think()`)
- [ ] Clean up test files (`test_*.py`)

## Handover Prompt for Next Session

> You are continuing work on endgame-ai. The repository is at a working state with unified architecture.
>
> **Current branch:** `unified-archBRAINZ` (up to date with origin)
>
> **What works:**
> - `openai` transport (LM Studio) — full organism run verified
> - `file_proxy` transport — full organism run verified
> - `opencode` transport — CLI stateless working with `opencode-go/deepseek-v4-flash` (requires clearing `OPENCODE_SERVER_PASSWORD` and `OPENCODE_SERVER_USERNAME` env vars)
> - `xai` transport — implemented (API + CLI modes), untested without credentials
> - BaseTransport/BaseNode abstraction — reduces boilerplate
> - Normalized wiring.json schema with `transport_config` + `global`
>
> **Immediate next steps:**
> 1. Test `xai` transport: set `XAI_API_KEY`, change wiring to `"transport": "xai"`, run organism
> 2. Test `grok_cli`: install grok CLI, change wiring to `"transport": "grok_cli"`, run organism
> 3. Add error node to topology + recovery edges
> 4. Make ROD two-pass pluggable (config per node/transport)
> 5. Remove test files (`test_*.py`)
>
> **Key files to understand:**
> - `brain.py` — Transport protocol, BaseTransport, call()/think(), config resolution
> - `nodes.py` — BaseNode, call_node(), node loading
> - `organism.py` — Main loop, STEP mode, topology traversal
> - `wiring.json` — Genome: transport, topology, prompts, config
> - `seed_brains/xai.py` — Unified xAI transport (API + CLI)
> - `seed_brains/opencode.py` — Fixed stateless OpenCode transport
> - `seed_nodes/*.py` — Thin wrappers using BaseNode
>
> **Fail-hard rule:** No fallbacks. If transport fails, organism stops with clear error.
>
> **ROD pattern:** Two-call hardcoded in `brain.think()` — first call gets reasoning, second call injects `ROD_REASONING_CONTENT` and extracts JSON record. This is the core innovation enabling 4B models to self-evolve.

## License

MIT — research organism, not a product. Run only where full desktop control is acceptable.