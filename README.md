# endgame-ai

`endgame-ai` is a living Windows desktop organism — not a traditional agentic CCA. It operates a real Windows desktop like a human: mouse, keyboard, arbitrary code generation and execution, self-evolution through wiring changes.

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

# Run with LM Studio (default 'openai' transport)
python organism.py --reset --max-ticks 5 --max-brain-calls 10 "open notepad"
```

## Wiring (wiring.json)

The single source of truth for topology and transport:

```json
{
  "model": {
    "transport": "openai",
    "transport_config": {
      "openai": { "base_url": "http://localhost:1234", "model": "nvidia-nemotron-3-nano-4b" },
      "opencode": { "executable": "%USERPROFILE%/AppData/Local/opencode/opencode-cli.exe", "model": "opencode-go/deepseek-v4-flash" },
      "xai": { "mode": "api", "api_key_env": "XAI_API_KEY", "model": "grok-build-0.1" },
      "grok_cli": { "executable": "grok" },
      "file_proxy": { "request_path": "comms/request.json", "response_path": "comms/response.json" }
    },
    "global": { "timeout": 180, "max_brain_calls": null, "raw_log": true }
  },
  "topology": { "cycle_start": "planner", "nodes": [...], "edges": {...} },
  "prompts": { "planner": "...", "decide": "...", "verify": "...", "reflect": "..." }
}
```

## Brain Transports (stateless, fail-hard)

| Transport | Status | Description |
|-----------|--------|-------------|
| `openai` | ✅ Verified | OpenAI-compatible `/v1/chat/completions` (LM Studio default) |
| `file_proxy` | ✅ Verified | File-based human-in-the-loop handoff |
| `opencode` | ✅ Verified | `opencode run -m <model> --format json` (clears auth env vars) |
| `xai` | 🔧 Implemented | xAI Responses API (`grok-build-0.1`, `grok-4`) + CLI `grok -p --output-format json` |
| `grok_cli` | 🔧 Implemented | `grok -p "prompt" --output-format json --no-auto-update` |
| `browser_ai` | ❌ Stub | Documented fail-hard placeholder |

**Each transport exports:** `call(messages, cfg) -> {"content": str, "reasoning": str}`

## Nodes (ROD Pipeline)

| Node | Role | Signal Output |
|------|------|---------------|
| `planner` | Goal → plan + next_signal | `observe` \| `reflect` |
| `observe` | Desktop snapshot | `decide` \| `reflect` |
| `decide` | Plan + observation → action | `act` \| `reflect` \| `self_modify` |
| `act` | Execute mechanical action | `verify` \| `reflect` |
| `verify` | Action result → success/fail | `planner` \| `reflect` |
| `reflect` | Lesson extraction | `planner` \| `self_modify` |
| `self_modify` | Wiring rewrite (future) | `planner` \| `reflect` |

**Orphaned (in seed_nodes, not wired):** `satisfied.py` (terminal rest), `scheduler.py` (plan stepping) — reserved for future plan-completion topology.

## Workbench (optional)

```powershell
python workbench.py
# http://127.0.0.1:8800/
# API: /api/status, /api/control (run/pause/step)
```

## STEP Mode

Centralized in `organism.py` before node execution. Control via `comms/control.json`:

```json
{"mode": "run"|"pause"|"step", "step_token": 0, "updated_at": 1234567890}
```

## Current State (2026-06-30)

### ✅ Completed (Phases 1-3)
- **Transport Protocol + BaseTransport** in `brain.py` — common logging, validation, error handling
- **BaseNode ABC** in `nodes.py` — 4 brain-calling nodes reduced to ~10 lines each
- **Consolidated xAI transports** — `xai.py` supports both API (`mode: api`) and CLI (`mode: cli`)
- **Normalized wiring.json** — `transport_config.{transport}` + `global` keys
- **Fixed opencode transport** — stateless CLI, clears `OPENCODE_SERVER_PASSWORD/USERNAME` to avoid "Session not found"
- **Marked `grok_build_api.py`** as reference-only (non-functional fragment)
- **Verified working:** `openai` (LM Studio), `file_proxy`, `opencode` transports

### 🔧 In Progress (Phase 3 remaining)
- Test `xai` transport (API mode requires `XAI_API_KEY`, CLI mode requires `grok` binary)
- Test `grok_cli` transport

### 🧪 Validation (Phase 4)
```powershell
# Each transport:
python organism.py --reset --max-ticks 5 --max-brain-calls 10 "open notepad"
# With wiring.json model.transport = openai | file_proxy | opencode | xai | grok_cli
```

## Fail-Hard Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `WinError 10061` (openai) | LM Studio server not running | Start LM Studio Local Server or change `model.transport` |
| OpenCode executable missing | Path wrong or not installed | Fix `transport_config.opencode.executable` or install |
| `XAI_API_KEY` missing | Env var not set | `set XAI_API_KEY=...` or change transport |
| `opencode exited 1: Session not found` | Auth env vars inherited | Transport now clears them; update if regressed |

## Research Notes

- **ROD two-pass** hardcoded in `brain.think()` — innovative, proven with 4B models. Pluggability noted for future.
- **No live dirs symlinks** — explicit copy is debuggable and fail-hard.
- **Stateless guarantee** — every transport call independent; no session continuity unless explicitly built (e.g., `opencode --continue`).
- **Windows 11 body** — `actions.py` fails hard on non-Windows; `desktop.py` returns platform evidence.

## License

MIT — research organism, not a product. Run only where full desktop control is acceptable.