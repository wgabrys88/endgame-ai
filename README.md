# endgame-ai — Operational Ledger

> One Windows rod replaces a human for long desktop tasks.
> Intelligence = wiring topology + reasoning loop + verify gate.

## Status: 🟡 WIRING EDITOR PHASE

### ✅ DONE

| # | What | Files |
|---|------|-------|
| 1 | Core server — stdlib-only Python, ThreadingHTTPServer, node handler registry, graph engine (run loop), SSE broadcast | `server.py` |
| 2 | Wiring topology — 11 nodes, 18 edges, full reasoning/prompts/guards/verbs config | `prompts/wiring.json` |
| 3 | JSON Schema for wiring validation | `prompts/wiring-schema.json` |
| 4 | Server-side POST /wiring validation gate (rejects bad topology before writing) | `server.py` |
| 5 | GET /schema endpoint (editor fetches schema at startup) | `server.py` |
| 6 | Desktop automation — UIA hover-probe, verb dispatch (click/write/press/hotkey/scroll/focus) | `desktop.py`, `actions.py` |
| 7 | LLM integration — LM Studio local inference, reasoning channels | `server.py` |
| 8 | Chrome UIA accessibility (--force-renderer-accessibility + native toolbar) | `wiring-editor.html` |
| 9 | Autonomous self-test proven (observe → click Step → goal → execute) | session-state |
| 10 | Wiring editor — Cytoscape + dagre, responsive layout, schema-driven add-node | `wiring-editor.html` |
| 11 | Editor node colors auto-derived from wiring (no hardcoded types in JS) | `wiring-editor.html` |
| 12 | Live execution in editor — Step/Run/Auto buttons drive real graph traversal | `wiring-editor.html` |
| 13 | SSE events — node_fire, node_result, rod_stop, wiring_modified | `server.py` |

### 🔲 TODO (priority order)

| # | What | Blocker | Notes |
|---|------|---------|-------|
| 1 | **Hot-reload node handlers** — scan `nodes/` dir, load .py modules at runtime | None | Use `importlib.util.spec_from_file_location` + mtime polling. New nodes appear without restart. |
| 2 | **Editor rewrites wiring.json** — add-node/add-edge in HTML posts to POST /wiring which validates + hot-reloads | #1 | Visual editing → persistent topology mutation |
| 3 | **Minimal modern CSS** — container queries, dvh, @media orientation, no legacy | None | Chrome 120+ / Opera 100+ only. Remove all polyfills. |
| 4 | **WSL2 + PowerShell launch** — `python3 server.py` from WSL, accessible at 0.0.0.0:9077 on LAN | None | Already works (http_bind: 0.0.0.0). Need launcher script. |
| 5 | **Step button advances diagram visually** — SSE node event → Cytoscape glow + edge animation | Partially done | Need edge-active animation + smoother transitions |
| 6 | **Add-edge UI in editor** — click source → click target → enter signal name | None | |
| 7 | **Delete node/edge** — select + delete key or button | None | |
| 8 | **Validate before layout changes** — prevent orphan nodes, ensure cycle_start reachable | #2 | |

### 🔮 FUTURE

- Multi-rod (slot > 0): bus_post/bus_check inter-rod messaging
- Self-modify circuit: LLM proposes topology changes at runtime
- Prompt hot-editing: change LLM prompts from editor, see results immediately
- Record/replay: log files visualized on timeline
- Manager rod: orchestrates student rods

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  wiring-editor.html (browser, 0.0.0.0:9077)        │
│  Cytoscape.js + dagre, SSE /events, POST /wiring   │
└────────────────────┬────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────┐
│  server.py (Python 3.13 stdlib only)                │
│  ThreadingHTTPServer · graph engine · SSE broadcast │
│  ┌──────────────┐  ┌─────────────────────────────┐  │
│  │ NODES dict   │  │ nodes/ dir (hot-loaded .py) │  │
│  │ type→handler │◄─┤ each file exports handler() │  │
│  └──────────────┘  └─────────────────────────────┘  │
│  ┌──────────────┐                                   │
│  │ wiring.json  │ ← POST /wiring (validated)        │
│  └──────────────┘                                   │
└─────────────────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
 desktop.py     LM Studio       bus.json
 (UIA probe)    (local LLM)    (inter-rod)
```

## How to Run

```powershell
# From PowerShell (Windows) or WSL2:
cd C:\Users\ewojgab\Downloads\endgame-ai
python server.py

# Open in Chrome:
# http://localhost:9077
# Click "Step" → enter a goal → watch nodes advance
```

## Hot-Reload Node Handlers

Drop a `.py` file in `nodes/` directory:

```python
# nodes/my_gate.py
def handler(state, config):
    """Return signals and state patch."""
    if state.get("some_condition"):
        return {"signals": ["yes"], "patch": {"checked": True}}
    return {"signals": ["no"], "patch": {}}
```

Then add a node in the editor with `type: "my_gate"` — it auto-loads.

## File Map

```
endgame-ai/
├── server.py              # HTTP + graph engine + node handlers (599 LOC)
├── desktop.py             # UIA hover-probe automation
├── actions.py             # Verb dispatch (click/write/hotkey/...)
├── wiring-editor.html     # Visual topology editor (single file)
├── prompts/
│   ├── wiring.json        # THE BRAIN — topology + prompts + config
│   ├── wiring-schema.json # JSON Schema for validation
│   ├── model.json         # LM Studio model config
│   └── *.txt              # Prompt templates
├── nodes/                 # Hot-loaded handler modules (TODO)
├── state.json             # Persisted execution state
└── bus.json               # Inter-rod message bus
```

## Key Decisions

1. **Zero pip** — stdlib only. No dependencies to break.
2. **Single wiring.json** — all config in one place. Schema-validated.
3. **Editor IS the server** — same port serves API + HTML. No build step.
4. **Chrome 120+ only** — enables container queries, dvh, popover, :has() without fallbacks.
5. **Hot-reload over restart** — new node types load from `nodes/` dir at runtime.
6. **Topology = code** — wiring.json edges are the program. Python handlers are pure functions.
