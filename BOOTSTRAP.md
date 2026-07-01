# BOOTSTRAP.md — endgame-ai Session Bootstrap

## MoE Vision
**endgame-ai** is a living Windows desktop organism, not a traditional agentic CCA. Python = mechanical body; `wiring.json` = mutable genome. Nodes and brain transports are hot-swappable modules copied from `seed_*/` → `live_*/` at runtime. The ROD loop (Reason→Observe→Decide with pluggable reasoning feedback) is in `brain.think()` and is the core innovation enabling 4B models to self-evolve. No fallbacks — fail-hard always. Self-modification = rewiring `wiring.json`.

## Goal
Unify the architecture: reduce boilerplate, normalize config, make every brain transport stateless and swappable via `wiring.json` alone. Verified transports: `openai` (LM Studio), `file_proxy`, `opencode`. Implemented: `xai` (API + CLI), `grok_cli`. Workbench: modern modular UI.

## State (2026-07-01, commit 376dc0b)
- **Branch:** `unified-archBRAINZ` (clean, pushed)
- **Core files:** `brain.py` (Transport protocol, BaseTransport, ReasoningStrategy, config resolution), `nodes.py` (BaseNode ABC), `organism.py` (loop, STEP mode, error routing), `wiring.json` (v1 schema with reasoning + error topology)
- **Transports:** `seed_brains/{openai,file_proxy,opencode,xai}.py` + stub `browser_ai.py`; legacy archived to `archive/`
- **Nodes:** `seed_nodes/{planner,decide,verify,reflect}.py` use BaseNode (~10 lines each); `observe,act,self_modify,error` mechanical; `satisfied,scheduler` orphaned (future plan-completion)
- **Topology:** 8-node cycle with `error` node + recovery edges; `halt` signal for clean exit
- **Workbench:** Modular ES6: `workbench.py` + `workbench.html` + `workbench.{css,js,api,state,graph,editor}.js`

## Plan
**Phase 5 — Validation & Evolution** (next)
1. Test `xai` transport: set `XAI_API_KEY`, `model.transport=xai`, `mode=api` → run organism
2. Test `grok_cli` transport: install grok CLI, change wiring, run organism
3. Implement `self_modify` node to actually rewrite wiring.json
4. Add multi-ROD parallelism (RodRunner + scheduler)
5. Add usage/cost tracking per transport

## Done (Phases 1-4)
- ✅ Archived legacy transports: `grok_build.py`, `grok_build_api.py`, `xai_responses.py` → `archive/`
- ✅ `Transport` Protocol + `BaseTransport` ABC — common logging, validation, error handling
- ✅ `BaseNode` ABC — 4 brain-calling nodes reduced from ~14 to ~10 lines each
- ✅ Consolidated `xai_responses.py` + `grok_build.py` → `xai.py` (API + CLI modes)
- ✅ Normalized `wiring.json`: `transport_config.{transport}` + `global` keys
- ✅ Verified end-to-end: `openai` (LM Studio), `file_proxy`, `opencode` transports
- ✅ **Pluggable ROD ReasoningStrategy** — `TwoPassStrategy`, `SinglePassStrategy`, `NativeReasoningStrategy`, `CustomStrategy` configurable per transport
- ✅ **Error-handling topology** — `error` node + edges from all nodes, `halt` signal for clean exit
- ✅ **Modern Workbench** — SVG topology graph, hybrid wiring editor, transport probe, ROD test, mobile-responsive
- ✅ README rewritten with full handover prompt

## Scientist Mode (always active)
1. Claims: (a) tested-in-this-session or (b) untested-prior. Untested → propose falsifying experiment.
2. No hedging, no industry norms, no simulated measurements.
3. Tool insufficient → "experiment pending" and stop.
4. Counter-intuitive = hypothesis to test, not error to correct.
5. On evidence: update state plainly. "I was wrong; measurement shows X" is valid.
6. Audit prior turns for violations (hedging, conventions, invented data, refusal to update).

## Fail-Hard Rule
No fallbacks. If transport fails, organism stops with clear error. This is self-evolution.

## Quick Commands
```powershell
# Validate
python -m py_compile brain.py nodes.py organism.py workbench.py actions.py desktop.py
python -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for d in ['seed_nodes','seed_brains'] for p in pathlib.Path(d).glob('*.py')]"

# Run (change model.transport in wiring.json)
python organism.py --reset --max-ticks 5 --max-brain-calls 10 "open notepad"

# Workbench
python workbench.py  # http://127.0.0.1:8800/
```

## Handover
Next session: continue Phase 5 validation. Test `xai` and `grok_cli` transports. Then implement `self_modify` wiring rewrite + multi-ROD.